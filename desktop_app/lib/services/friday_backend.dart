import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:http/http.dart' as http;

import 'friday_settings.dart';

class BackendException implements Exception {
  const BackendException(this.message, {this.statusCode});
  final String message;
  final int? statusCode;
  @override
  String toString() => message;
}

class FridayBackend {
  FridayBackend(this.settings);

  final FridaySettings settings;
  final http.Client _client = http.Client();
  Process? _ownedProcess;
  Process? _ollamaProcess;
  String _lastProcessOutput = '';

  String get baseUrl => _withoutTrailingSlash(settings.apiBaseUrl);
  String? get lastProcessOutput => _lastProcessOutput.isEmpty ? null : _lastProcessOutput;

  static String _withoutTrailingSlash(String value) {
    var result = value.trim();
    while (result.endsWith('/')) {
      result = result.substring(0, result.length - 1);
    }
    return result;
  }

  Uri _uri(String path) => Uri.parse('$baseUrl$path');

  Future<Map<String, dynamic>> _get(
    String path, {
    Duration timeout = const Duration(seconds: 3),
  }) async {
    try {
      final response = await _client.get(_uri(path)).timeout(timeout);
      return _decode(response);
    } on TimeoutException {
      throw const BackendException('The backend did not respond before the timeout.');
    } on SocketException {
      throw const BackendException('The backend is not reachable at the configured address.');
    } on http.ClientException {
      throw const BackendException('Cannot connect to the local FRIDAY API.');
    } on FormatException {
      throw const BackendException('The backend returned invalid JSON.');
    }
  }

  Map<String, dynamic> _decode(http.Response response) {
    dynamic body;
    try {
      body = jsonDecode(response.body);
    } catch (_) {
      body = {'detail': response.body};
    }
    if (response.statusCode < 200 || response.statusCode >= 300) {
      final detail = body is Map && body['detail'] is String
          ? body['detail'] as String
          : 'API request failed (${response.statusCode}).';
      throw BackendException(detail, statusCode: response.statusCode);
    }
    if (body is! Map<String, dynamic>) {
      throw const BackendException('The backend returned an unexpected response format.');
    }
    return body;
  }

  Future<Map<String, dynamic>> health() =>
      _get('/health', timeout: const Duration(seconds: 2));

  Future<Map<String, dynamic>> voiceStatus() => _get('/api/v1/voice/status');

  Future<List<Map<String, dynamic>>> models() async {
    final response = await _get('/api/v1/models');
    final raw = response['routes'];
    if (raw is! List) return const [];
    return raw.whereType<Map>().map((item) => Map<String, dynamic>.from(item)).toList();
  }

  /// Starts Ollama if the user installed it locally but its HTTP server is not running.
  /// Model downloads are intentionally left to the setup script.
  Future<void> ensureOllama({void Function(String message)? onStatus}) async {
    final configured = _withoutTrailingSlash(settings.ollamaBaseUrl);
    final tagsUri = Uri.tryParse('$configured/api/tags');
    if (tagsUri == null || !_isLoopbackUri(tagsUri)) return;
    try {
      final response = await _client.get(tagsUri).timeout(const Duration(seconds: 2));
      if (response.statusCode == 200) return;
    } catch (_) {
      // The local model server isn't listening yet.
    }
    try {
      onStatus?.call('Starting local Ollama runtime…');
      final executable = Platform.environment['FRIDAY_OLLAMA_BIN'] ?? 'ollama';
      _ollamaProcess = await Process.start(
        executable,
        const ['serve'],
        runInShell: Platform.isWindows,
      );
      _ollamaProcess!.stdout.transform(utf8.decoder).listen((value) => _appendLog('ollama: $value'));
      _ollamaProcess!.stderr.transform(utf8.decoder).listen((value) => _appendLog('ollama: $value'));
      for (var attempt = 0; attempt < 16; attempt++) {
        await Future<void>.delayed(const Duration(milliseconds: 500));
        try {
          final response = await _client.get(tagsUri).timeout(const Duration(seconds: 1));
          if (response.statusCode == 200) return;
        } catch (_) {
          // Wait briefly for the local runtime to start.
        }
      }
    } catch (_) {
      // Ollama may be missing; the readiness endpoint will expose that state.
    }
  }

  Future<void> ensureBackend({void Function(String message)? onStatus}) async {
    try {
      await health();
      onStatus?.call('Backend connected');
      return;
    } catch (_) {
      // Try to launch it from this repository if the connection is local.
    }
    if (!settings.autoStartBackend) {
      throw const BackendException(
        'Backend is offline. Enable automatic start or run the local launcher from the FRIDAY repository.',
      );
    }
    final apiUri = _uri('/health');
    if (!_isLoopbackUri(apiUri)) {
      throw const BackendException(
        'Automatic backend launch is only supported for a local loopback address.',
      );
    }
    if (apiUri.port != 8000) {
      throw const BackendException(
        'The automatic launcher uses port 8000. Set the API address to http://127.0.0.1:8000 or start your custom server manually.',
      );
    }

    final root = await _findRepositoryRoot();
    if (root == null) {
      throw const BackendException(
        'Could not find backend/main.py. Choose the repository folder in Settings, or run scripts/run_friday_windows.ps1 from the FRIDAY repo.',
      );
    }
    final candidates = <String>[
      Platform.environment['FRIDAY_PYTHON'] ?? '',
      '${root.path}${Platform.pathSeparator}.venv${Platform.pathSeparator}Scripts${Platform.pathSeparator}python.exe',
      '${root.path}${Platform.pathSeparator}.venv${Platform.pathSeparator}bin${Platform.pathSeparator}python',
      'python',
    ].where((value) => value.isNotEmpty).toList();

    Object? lastError;
    for (final python in candidates) {
      if (python != 'python' && !await File(python).exists()) continue;
      try {
        onStatus?.call('Starting local FRIDAY backend…');
        _ownedProcess = await Process.start(
          python,
          const ['-m', 'uvicorn', 'backend.main:app', '--host', '127.0.0.1', '--port', '8000'],
          workingDirectory: root.path,
          runInShell: Platform.isWindows,
          environment: {
            'ENABLE_LOCAL_DESKTOP_ACTIONS': 'true',
            'OLLAMA_BASE_URL': settings.ollamaBaseUrl,
            'PYTHONUTF8': '1',
          },
        );
        _ownedProcess!.stdout.transform(utf8.decoder).listen(_appendLog);
        _ownedProcess!.stderr.transform(utf8.decoder).listen(_appendLog);
        for (var attempt = 0; attempt < 35; attempt++) {
          await Future<void>.delayed(const Duration(milliseconds: 700));
          try {
            await health();
            onStatus?.call('Local backend connected');
            return;
          } catch (_) {
            // Allow time for imports and SQLite initialization.
          }
        }
        lastError = BackendException('Backend process started but did not become healthy. $_lastProcessOutput');
        _ownedProcess?.kill();
        _ownedProcess = null;
      } catch (error) {
        lastError = error;
      }
    }
    throw BackendException(lastError?.toString() ?? 'Could not start the FRIDAY backend.');
  }

  static bool _isLoopbackUri(Uri uri) =>
      uri.host == '127.0.0.1' || uri.host == 'localhost' || uri.host == '::1';

  Future<Directory?> _findRepositoryRoot() async {
    final candidates = <String>[
      settings.backendProjectPath,
      Platform.environment['FRIDAY_PROJECT_ROOT'] ?? '',
      Directory.current.path,
      Directory.current.parent.path,
      '${File(Platform.resolvedExecutable).parent.path}${Platform.pathSeparator}..',
      '${File(Platform.resolvedExecutable).parent.path}${Platform.pathSeparator}..${Platform.pathSeparator}..',
    ].where((value) => value.trim().isNotEmpty).toList();

    final seen = <String>{};
    for (final candidate in candidates) {
      var dir = Directory(candidate).absolute;
      for (var depth = 0; depth < 5; depth++) {
        final path = dir.path;
        if (seen.add(path) &&
            await File('$path${Platform.pathSeparator}backend${Platform.pathSeparator}main.py').exists() &&
            await File('$path${Platform.pathSeparator}requirements.txt').exists()) {
          return dir;
        }
        final parent = dir.parent;
        if (parent.path == dir.path) break;
        dir = parent;
      }
    }
    return null;
  }

  void _appendLog(String value) {
    _lastProcessOutput += value;
    if (_lastProcessOutput.length > 6000) {
      _lastProcessOutput = _lastProcessOutput.substring(_lastProcessOutput.length - 6000);
    }
  }

  Future<Map<String, dynamic>> transcribeAudio(String audioPath) async {
    final request = http.MultipartRequest('POST', _uri('/api/v1/voice/transcribe'));
    request.files.add(await http.MultipartFile.fromPath('audio', audioPath));
    try {
      final streamed = await _client.send(request).timeout(const Duration(minutes: 4));
      final response = await http.Response.fromStream(streamed);
      return _decode(response);
    } on TimeoutException {
      throw const BackendException(
        'Local transcription timed out. The first run may need to download the Whisper model.',
      );
    } on SocketException {
      throw const BackendException('Lost connection to FRIDAY while transcribing.');
    } on http.ClientException {
      throw const BackendException('Could not upload the microphone recording to FRIDAY.');
    }
  }

  Future<Map<String, dynamic>> chat(
    List<Map<String, String>> messages, {
    String modelRoute = 'auto',
  }) async {
    final request = <String, Object?>{
      'messages': messages,
      'model_route': modelRoute,
    };
    try {
      final response = await _client
          .post(
            _uri('/api/v1/chat'),
            headers: const {'Content-Type': 'application/json', 'Accept': 'application/json'},
            body: jsonEncode(request),
          )
          .timeout(const Duration(minutes: 2));
      return _decode(response);
    } on TimeoutException {
      throw const BackendException('The model took too long to answer.');
    } on SocketException {
      throw const BackendException('Lost connection to FRIDAY during inference.');
    } on http.ClientException {
      throw const BackendException('Could not send the conversation to FRIDAY.');
    }
  }

  void dispose() {
    _client.close();
    _ownedProcess?.kill();
    _ownedProcess = null;
    _ollamaProcess?.kill();
    _ollamaProcess = null;
  }
}
