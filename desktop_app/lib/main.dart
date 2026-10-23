import 'dart:async';
import 'dart:io';

import 'package:file_selector/file_selector.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_tts/flutter_tts.dart';
import 'package:path_provider/path_provider.dart';
import 'package:record/record.dart';

import 'services/friday_backend.dart';
import 'services/friday_settings.dart';
import 'widgets/holographic_orb.dart';

const _ink = Color(0xFF080C18);
const _panel = Color(0xCC111A30);
const _line = Color(0xFF273654);
const _cyan = Color(0xFF77E9F4);
const _violet = Color(0xFFA99CFF);
const _muted = Color(0xFF92A4C8);

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(const FridayDesktopApp());
}

class FridayDesktopApp extends StatelessWidget {
  const FridayDesktopApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'FRIDAY',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        useMaterial3: true,
        brightness: Brightness.dark,
        scaffoldBackgroundColor: _ink,
        colorScheme: ColorScheme.fromSeed(seedColor: _cyan, brightness: Brightness.dark),
        fontFamily: 'Segoe UI',
        snackBarTheme: const SnackBarThemeData(
          backgroundColor: Color(0xFF18233A),
          contentTextStyle: TextStyle(color: Color(0xFFEAF3FF)),
          behavior: SnackBarBehavior.floating,
        ),
      ),
      home: const FridayHome(),
    );
  }
}

class FridayHome extends StatefulWidget {
  const FridayHome({super.key});

  @override
  State<FridayHome> createState() => _FridayHomeState();
}

class _FridayHomeState extends State<FridayHome> with TickerProviderStateMixin {
  final AudioRecorder _recorder = AudioRecorder();
  final FlutterTts _tts = FlutterTts();
  final ScrollController _conversationScroll = ScrollController();
  StreamSubscription<Amplitude>? _amplitudeSubscription;
  AnimationController? _backgroundAnimation;
  FridaySettings _settings = const FridaySettings();
  FridayBackend? _backend;
  Map<String, dynamic> _voiceStatus = const {};
  List<Map<String, dynamic>> _routes = const [];
  final List<Map<String, String>> _messages = [];
  final List<String> _events = [];

  String _connectionLabel = 'Starting FRIDAY…';
  String _status = 'Preparing local runtime';
  String _mode = 'idle';
  String _lastTranscript = '';
  String _lastResponse = '';
  String _providerLabel = 'LOCAL-FIRST';
  String? _lastError;
  bool _backendReady = false;
  bool _booting = true;
  bool _voiceSession = false;
  bool _processingTurn = false;
  bool _speechDetected = false;
  bool _disposed = false;
  DateTime? _speechStartedAt;
  DateTime? _lastVoiceAt;
  String? _activeRecordingPath;
  Offset _orbOffset = const Offset(0, 0);
  bool _orbMoved = false;
  final Map<String, Offset> _chipOffsets = {};

  bool get _whisperReady => _voiceStatus['transcription_ready'] == true;
  List<String> get _installedModels => (_voiceStatus['models'] is List)
      ? (_voiceStatus['models'] as List).whereType<String>().toList()
      : const <String>[];
  String get _selectedModelName {
    for (final route in _routes) {
      if (route['id'] == _settings.modelRoute && route['model'] is String) {
        return route['model'] as String;
      }
    }
    return _voiceStatus['default_model'] is String
        ? _voiceStatus['default_model'] as String
        : 'No local model detected';
  }

  @override
  void initState() {
    super.initState();
    _backgroundAnimation = AnimationController(vsync: this, duration: const Duration(seconds: 24))..repeat();
    _tts.setLanguage(_settings.voiceLocale);
    _tts.setSpeechRate(0.47);
    _tts.setPitch(0.94);
    _tts.setVolume(1.0);
    _initialize();
  }

  @override
  void dispose() {
    _disposed = true;
    _stopVoiceSession(updateUi: false);
    _amplitudeSubscription?.cancel();
    _recorder.dispose();
    _tts.stop();
    _conversationScroll.dispose();
    _backgroundAnimation?.dispose();
    _backend?.dispose();
    super.dispose();
  }

  void _setStateSafe(VoidCallback fn) {
    if (mounted && !_disposed) setState(fn);
  }

  void _log(String text) {
    _events.insert(0, '${TimeOfDay.now().format(context)}  $text');
    if (_events.length > 18) _events.removeLast();
  }

  Future<void> _initialize() async {
    _setStateSafe(() {
      _booting = true;
      _connectionLabel = 'Reading connection settings';
      _status = 'Looking for the local FRIDAY API';
      _lastError = null;
    });
    _settings = await FridaySettingsStore.load();
    _backend?.dispose();
    _backend = FridayBackend(_settings);
    await _tts.setLanguage(_settings.voiceLocale);
    try {
      await _backend!.ensureBackend(onStatus: (message) {
        _setStateSafe(() => _connectionLabel = message);
      });
      await _backend!.ensureOllama(onStatus: (message) {
        _setStateSafe(() => _connectionLabel = message);
      });
      final status = await _backend!.voiceStatus();
      final routes = await _backend!.models();
      _setStateSafe(() {
        _backendReady = true;
        _voiceStatus = status;
        _routes = routes;
        _connectionLabel = 'FRIDAY API connected';
        _booting = false;
        _lastError = null;
        _status = _installedModels.isEmpty
            ? 'Install a local Ollama model to enable inference'
            : !_whisperReady
                ? 'Install the local Whisper speech package to enable voice input'
                : 'Ready for a voice session';
      });
      _log('Connected to ${_settings.apiBaseUrl}');
      if (_installedModels.isNotEmpty) _log('Found ${_installedModels.length} local model(s)');
    } catch (error) {
      _setStateSafe(() {
        _backendReady = false;
        _booting = false;
        _connectionLabel = 'Backend offline';
        _status = error.toString();
        _lastError = error.toString();
      });
      _log('Connection failed');
    }
  }


  Future<void> _startVoiceSession() async {
    if (_voiceSession) {
      await _stopVoiceSession();
      return;
    }
    if (!_backendReady) {
      await _initialize();
      if (!_backendReady) {
        _showMessage(_lastError ?? 'FRIDAY backend is not available.');
        return;
      }
    }
    if (!_whisperReady) {
      _showMessage('Offline Whisper is not installed. Run the Windows setup script, then restart FRIDAY.');
      _setStateSafe(() => _status = 'Local speech recognition needs setup');
      return;
    }
    try {
      // The record plugin documents its permission-check API as unsupported on Windows.
      // Windows manages microphone access through its privacy settings and Media Foundation.
      final hasPermission = Platform.isWindows ? true : await _recorder.hasPermission();
      if (!hasPermission) {
        _showMessage('Microphone permission was not granted.');
        return;
      }
      _setStateSafe(() {
        _voiceSession = true;
        _processingTurn = false;
        _mode = 'listening';
        _status = 'Listening. Speak naturally, then pause.';
        _lastError = null;
      });
      _log('Voice session activated');
      await _beginRecording();
    } catch (error) {
      _setStateSafe(() {
        _voiceSession = false;
        _mode = 'idle';
        _status = 'Microphone could not start: $error';
        _lastError = error.toString();
      });
    }
  }

  Future<void> _beginRecording() async {
    if (!_voiceSession || _processingTurn || _disposed) return;
    final temp = await getTemporaryDirectory();
    final path = '${temp.path}${Platform.pathSeparator}friday-${DateTime.now().microsecondsSinceEpoch}.wav';
    _activeRecordingPath = path;
    _speechDetected = false;
    _speechStartedAt = null;
    _lastVoiceAt = null;
    await _recorder.start(
      const RecordConfig(
        encoder: AudioEncoder.wav,
        sampleRate: 16000,
        numChannels: 1,
        autoGain: true,
        echoCancel: true,
        noiseSuppress: true,
      ),
      path: path,
    );
    await _amplitudeSubscription?.cancel();
    _amplitudeSubscription = _recorder
        .onAmplitudeChanged(const Duration(milliseconds: 160))
        .listen(_onAmplitude, onError: (Object error) {
      _setStateSafe(() {
        _status = 'Microphone meter error: $error';
        _lastError = error.toString();
      });
    });
    _setStateSafe(() {
      _mode = 'listening';
      _status = 'Listening… pause after your request.';
    });
  }

  void _onAmplitude(Amplitude amplitude) {
    if (!_voiceSession || _processingTurn) return;
    final now = DateTime.now();
    // RMS-style dB threshold: reduce sensitivity slightly for room noise.
    if (amplitude.current > -43.0) {
      if (!_speechDetected) {
        _speechDetected = true;
        _speechStartedAt = now;
        _setStateSafe(() {
          _status = 'I hear you…';
          _mode = 'listening';
        });
      }
      _lastVoiceAt = now;
      return;
    }
    final started = _speechStartedAt;
    final last = _lastVoiceAt;
    if (_speechDetected &&
        started != null &&
        last != null &&
        now.difference(started) > const Duration(milliseconds: 550) &&
        now.difference(last) > const Duration(milliseconds: 1250)) {
      unawaited(_finishRecordingAndProcess());
    }
  }

  Future<void> _finishRecordingAndProcess() async {
    if (!_voiceSession || _processingTurn) return;
    _processingTurn = true;
    _speechDetected = false;
    await _amplitudeSubscription?.cancel();
    _amplitudeSubscription = null;
    _setStateSafe(() {
      _mode = 'thinking';
      _status = 'Transcribing locally…';
    });
    String? path;
    try {
      path = await _recorder.stop();
      path ??= _activeRecordingPath;
      _activeRecordingPath = null;
      if (path == null || !await File(path).exists() || await File(path).length() < 1800) {
        _setStateSafe(() => _status = 'I did not catch enough speech. Listening again…');
        return;
      }
      final transcription = await _backend!.transcribeAudio(path);
      final transcript = (transcription['text'] ?? '').toString().trim();
      if (transcript.isEmpty) {
        _setStateSafe(() => _status = 'No clear speech detected. Try speaking closer to the microphone.');
        return;
      }
      _setStateSafe(() {
        _lastTranscript = transcript;
        _status = 'Thinking with the local model…';
      });
      _log('Heard: ${_truncate(transcript, 75)}');
      _messages.add({'role': 'user', 'content': transcript});
      while (_messages.length > 20) {
        _messages.removeAt(0);
        if (_messages.isNotEmpty && _messages.first['role'] == 'assistant') _messages.removeAt(0);
      }
      final response = await _backend!.chat(_messages, modelRoute: _settings.modelRoute);
      final answer = (response['answer'] ?? '').toString().trim();
      if (answer.isEmpty) throw const BackendException('The model returned an empty answer.');
      final assistantMessage = <String, String>{'role': 'assistant', 'content': answer};
      _messages.add(assistantMessage);
      _setStateSafe(() {
        _lastResponse = answer;
        final provider = response['provider']?.toString() ?? 'model';
        final model = response['model']?.toString();
        _providerLabel = model == null || model.isEmpty ? provider : '$provider · $model';
        _status = 'Speaking the response…';
        _mode = 'speaking';
      });
      _log('Answered with $_providerLabel');
      await _speak(answer);
    } catch (error) {
      _setStateSafe(() {
        _lastError = error.toString();
        _status = error.toString();
        _mode = 'error';
      });
      _log('Turn failed: ${_truncate(error.toString(), 110)}');
    } finally {
      if (path != null) {
        try {
          final file = File(path);
          if (await file.exists()) await file.delete();
        } catch (_) {}
      }
      _processingTurn = false;
      if (_voiceSession && _settings.autoResumeListening && !_disposed) {
        await Future<void>.delayed(const Duration(milliseconds: 400));
        try {
          await _beginRecording();
        } catch (error) {
          _setStateSafe(() {
            _mode = 'error';
            _status = 'Could not resume microphone: $error';
            _lastError = error.toString();
          });
        }
      } else if (mounted && !_disposed) {
        _setStateSafe(() => _mode = 'idle');
      }
    }
  }

  Future<void> _speak(String text) async {
    try {
      await _tts.awaitSpeakCompletion(true);
      await _tts.speak(text);
    } catch (_) {
      _showMessage('Text-to-speech failed. Check that a Windows speech voice is installed.');
    }
  }

  Future<void> _stopVoiceSession({bool updateUi = true}) async {
    _voiceSession = false;
    _speechDetected = false;
    await _amplitudeSubscription?.cancel();
    _amplitudeSubscription = null;
    try {
      if (await _recorder.isRecording()) await _recorder.stop();
    } catch (_) {}
    await _tts.stop();
    if (updateUi && mounted && !_disposed) {
      _setStateSafe(() {
        _mode = 'idle';
        _status = 'Voice session paused';
      });
      _log('Voice session stopped');
    }
  }

  Future<void> _settingsDialog() async {
    final apiController = TextEditingController(text: _settings.apiBaseUrl);
    final pathController = TextEditingController(text: _settings.backendProjectPath);
    final ollamaController = TextEditingController(text: _settings.ollamaBaseUrl);
    var autoStart = _settings.autoStartBackend;
    var autoResume = _settings.autoResumeListening;
    var locale = _settings.voiceLocale;
    var modelRoute = _settings.modelRoute;
    final folders = await showDialog<bool>(
      context: context,
      barrierDismissible: false,
      builder: (dialogContext) {
        return StatefulBuilder(builder: (context, setDialogState) {
          final availableRoutes = _routes.isEmpty
              ? <Map<String, dynamic>>[
                  {'id': 'auto', 'name': 'Automatic (local-only)', 'available': true},
                ]
              : _routes;
          final routeIds = availableRoutes.map((r) => r['id']?.toString()).whereType<String>().toSet();
          if (!routeIds.contains(modelRoute)) modelRoute = 'auto';
          return AlertDialog(
            backgroundColor: const Color(0xFF111A30),
            title: const Text('FRIDAY connection settings', style: TextStyle(fontWeight: FontWeight.w700)),
            content: SizedBox(
              width: 560,
              child: SingleChildScrollView(
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text('Backend API address', style: TextStyle(color: _muted, fontSize: 12)),
                    const SizedBox(height: 7),
                    TextField(controller: apiController, decoration: const InputDecoration(prefixIcon: Icon(Icons.link), hintText: 'http://127.0.0.1:8000')),
                    const SizedBox(height: 18),
                    const Text('Ollama local model server', style: TextStyle(color: _muted, fontSize: 12)),
                    const SizedBox(height: 7),
                    TextField(controller: ollamaController, decoration: const InputDecoration(prefixIcon: Icon(Icons.memory_outlined), hintText: 'http://127.0.0.1:11434')),
                    const SizedBox(height: 18),
                    const Text('FRIDAY repository folder (contains backend/main.py)', style: TextStyle(color: _muted, fontSize: 12)),
                    const SizedBox(height: 7),
                    Row(children: [
                      Expanded(child: TextField(controller: pathController, decoration: const InputDecoration(prefixIcon: Icon(Icons.folder_open), hintText: 'Auto-detect or choose a folder'))),
                      const SizedBox(width: 8),
                      IconButton(
                        tooltip: 'Choose repository folder',
                        onPressed: () async {
                          final chosen = await getDirectoryPath(confirmButtonText: 'Use this FRIDAY folder');
                          if (chosen != null) pathController.text = chosen;
                        },
                        icon: const Icon(Icons.drive_folder_upload_outlined),
                      ),
                    ]),
                    const SizedBox(height: 18),
                    const Text('Model route', style: TextStyle(color: _muted, fontSize: 12)),
                    const SizedBox(height: 7),
                    DropdownButtonFormField<String>(
                      value: routeIds.contains(modelRoute) ? modelRoute : 'auto',
                      isExpanded: true,
                      decoration: const InputDecoration(prefixIcon: Icon(Icons.hub_outlined)),
                      items: availableRoutes.map((route) {
                        final id = route['id']?.toString() ?? 'auto';
                        final name = route['name']?.toString() ?? id;
                        final ready = route['available'] == true;
                        return DropdownMenuItem<String>(value: id, enabled: ready, child: Text(name, overflow: TextOverflow.ellipsis));
                      }).toList(),
                      onChanged: (value) => setDialogState(() => modelRoute = value ?? 'auto'),
                    ),
                    const SizedBox(height: 10),
                    SwitchListTile(
                      contentPadding: EdgeInsets.zero,
                      title: const Text('Start local Python backend automatically'),
                      subtitle: const Text('Looks for backend/main.py and uses the repo virtual environment when present.', style: TextStyle(fontSize: 11, color: _muted)),
                      value: autoStart,
                      onChanged: (value) => setDialogState(() => autoStart = value),
                    ),
                    SwitchListTile(
                      contentPadding: EdgeInsets.zero,
                      title: const Text('Resume listening after each answer'),
                      subtitle: const Text('Continuous hands-free turns; you can stop the session at any time.', style: TextStyle(fontSize: 11, color: _muted)),
                      value: autoResume,
                      onChanged: (value) => setDialogState(() => autoResume = value),
                    ),
                    const SizedBox(height: 6),
                    const Text('Voice language', style: TextStyle(color: _muted, fontSize: 12)),
                    const SizedBox(height: 7),
                    DropdownButtonFormField<String>(
                      value: locale,
                      decoration: const InputDecoration(prefixIcon: Icon(Icons.record_voice_over_outlined)),
                      items: const [
                        DropdownMenuItem(value: 'en-IN', child: Text('English (India)')),
                        DropdownMenuItem(value: 'en-US', child: Text('English (US)')),
                        DropdownMenuItem(value: 'en-GB', child: Text('English (UK)')),
                      ],
                      onChanged: (value) => setDialogState(() => locale = value ?? 'en-IN'),
                    ),
                  ],
                ),
              ),
            ),
            actions: [
              TextButton(onPressed: () => Navigator.pop(dialogContext, false), child: const Text('Cancel')),
              FilledButton.icon(
                onPressed: () => Navigator.pop(dialogContext, true),
                icon: const Icon(Icons.save_outlined),
                label: const Text('Save and reconnect'),
              ),
            ],
          );
        });
      },
    );
    if (folders == true) {
      var api = apiController.text.trim();
      if (!api.startsWith('http://') && !api.startsWith('https://')) api = 'http://$api';
      _settings = _settings.copyWith(
        apiBaseUrl: api,
        ollamaBaseUrl: ollamaController.text.trim(),
        autoStartBackend: autoStart,
        autoResumeListening: autoResume,
        modelRoute: modelRoute,
        voiceLocale: locale,
      );
      await FridaySettingsStore.save(_settings);
      await _stopVoiceSession();
      await _initialize();
    }
    apiController.dispose();
    pathController.dispose();
    ollamaController.dispose();
  }

  Future<void> _showDiagnostics() async {
    final settingsPath = await FridaySettingsStore.settingsPath();
    if (!mounted) return;
    await showDialog<void>(
      context: context,
      builder: (context) => AlertDialog(
        backgroundColor: const Color(0xFF111A30),
        title: const Text('Runtime diagnostics'),
        content: SizedBox(
          width: 580,
          child: SingleChildScrollView(
            child: SelectableText([
              'API: ${_settings.apiBaseUrl}',
              'Project: ${_settings.backendProjectPath.isEmpty ? 'auto-detected' : _settings.backendProjectPath}',
              'Ollama: ${_settings.ollamaBaseUrl}',
              'Settings file: $settingsPath',
              'Selected model route: ${_settings.modelRoute}',
              'Ollama: ${_voiceStatus['ollama_reachable'] == true ? 'reachable' : 'not detected'}',
              'Installed models: ${_installedModels.isEmpty ? 'none detected' : _installedModels.join(', ')}',
              'Local speech: ${_whisperReady ? 'Whisper installed' : 'not installed'}',
              'Backend process output: ${_backend?.lastProcessOutput ?? 'no process log available'}',
              if (_lastError != null) 'Last error: $_lastError',
              ..._events,
            ].join('\n'), style: const TextStyle(fontFamily: 'Consolas', fontSize: 11, height: 1.5)),
          ),
        ),
        actions: [
          TextButton.icon(
            onPressed: () async {
              await Clipboard.setData(ClipboardData(text: settingsPath));
              if (context.mounted) Navigator.pop(context);
            },
            icon: const Icon(Icons.copy),
            label: const Text('Copy settings path'),
          ),
          TextButton(onPressed: () => Navigator.pop(context), child: const Text('Close')),
        ],
      ),
    );
  }

  void _showMessage(String message) {
    if (!mounted || _disposed) return;
    ScaffoldMessenger.of(context)
      ..hideCurrentSnackBar()
      ..showSnackBar(SnackBar(content: Text(message)));
  }

  String _truncate(String value, int max) => value.length <= max ? value : '${value.substring(0, max - 1)}…';

  void _onOrbPanUpdate(DragUpdateDetails details, Size stageSize) {
    final next = _orbOffset + details.delta;
    final maxX = (stageSize.width / 2) - 104;
    final maxY = (stageSize.height / 2) - 104;
    setState(() {
      _orbOffset = Offset(next.dx.clamp(-maxX, maxX), next.dy.clamp(-maxY, maxY));
      _orbMoved = true;
    });
  }

  Widget _statusDot({required bool active, Color color = _cyan}) => Container(
        width: 7,
        height: 7,
        decoration: BoxDecoration(
          color: active ? color : const Color(0xFF63718F),
          shape: BoxShape.circle,
          boxShadow: active ? [BoxShadow(color: color.withValues(alpha: .58), blurRadius: 9)] : null,
        ),
      );

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Stack(
        children: [
          Positioned.fill(
            child: AnimatedBuilder(
              animation: _backgroundAnimation!,
              builder: (context, _) => CustomPaint(painter: _BackgroundPainter(_backgroundAnimation!.value)),
            ),
          ),
          SafeArea(
            child: Column(
              children: [
                _buildTopBar(),
                Expanded(
                  child: LayoutBuilder(builder: (context, constraints) {
                    final wide = constraints.maxWidth >= 920;
                    if (wide) {
                      return Padding(
                        padding: const EdgeInsets.fromLTRB(30, 20, 30, 14),
                        child: Row(
                          crossAxisAlignment: CrossAxisAlignment.stretch,
                          children: [
                            Expanded(flex: 6, child: _buildStage()),
                            const SizedBox(width: 18),
                            Expanded(flex: 4, child: _buildConversationPanel()),
                          ],
                        ),
                      );
                    }
                    return Padding(
                      padding: const EdgeInsets.fromLTRB(16, 12, 16, 12),
                      child: Column(
                        children: [
                          Expanded(flex: 6, child: _buildStage(compact: true)),
                          const SizedBox(height: 12),
                          Expanded(flex: 5, child: _buildConversationPanel()),
                        ],
                      ),
                    );
                  }),
                ),
                _buildBottomStatus(),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildTopBar() {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 26, vertical: 17),
      decoration: const BoxDecoration(
        color: Color(0x66070B16),
        border: Border(bottom: BorderSide(color: Color(0x332F4164))),
      ),
      child: Row(children: [
        Container(
          width: 42,
          height: 42,
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(13),
            border: Border.all(color: _cyan.withValues(alpha: .5)),
            gradient: const LinearGradient(colors: [Color(0x3329DBF0), Color(0x33A99CFF)]),
            boxShadow: [BoxShadow(color: _cyan.withValues(alpha: .09), blurRadius: 24)],
          ),
          alignment: Alignment.center,
          child: const Text('F', style: TextStyle(fontSize: 23, fontWeight: FontWeight.w800, color: Color(0xFFC5FCFF))),
        ),
        const SizedBox(width: 12),
        const Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text('FRIDAY', style: TextStyle(fontWeight: FontWeight.w900, letterSpacing: 3, fontSize: 16)),
          SizedBox(height: 3),
          Text('PERSONAL INTELLIGENCE', style: TextStyle(fontSize: 8, color: _muted, letterSpacing: 1.8, fontWeight: FontWeight.w700)),
        ]),
        const Spacer(),
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 9),
          decoration: BoxDecoration(color: _panel, borderRadius: BorderRadius.circular(30), border: Border.all(color: _line)),
          child: Row(children: [
            _statusDot(active: _backendReady, color: _backendReady ? const Color(0xFF6AE6B6) : const Color(0xFFFF9BA8)),
            const SizedBox(width: 8),
            Text(_connectionLabel, style: const TextStyle(fontSize: 11, color: Color(0xFFD5E1FA))),
          ]),
        ),
        const SizedBox(width: 10),
        IconButton(
          tooltip: 'Refresh connections',
          onPressed: (_booting || _voiceSession || _processingTurn) ? null : _initialize,
          icon: const Icon(Icons.sync_rounded),
        ),
        IconButton(
          tooltip: 'Connection settings',
          onPressed: _settingsDialog,
          icon: const Icon(Icons.tune_rounded),
        ),
        IconButton(
          tooltip: 'Diagnostics',
          onPressed: _showDiagnostics,
          icon: const Icon(Icons.monitor_heart_outlined),
        ),
      ]),
    );
  }

  Widget _buildStage({bool compact = false}) {
    return ClipRRect(
      borderRadius: BorderRadius.circular(26),
      child: Container(
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(26),
          border: Border.all(color: _line.withValues(alpha: .82)),
          gradient: const LinearGradient(
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
            colors: [Color(0xB5121D36), Color(0xB5091021), Color(0x8810172C)],
          ),
        ),
        child: LayoutBuilder(builder: (context, constraints) {
          final size = Size(constraints.maxWidth, constraints.maxHeight);
          final topInset = compact ? 98.0 : 112.0;
          final bottomInset = compact ? 104.0 : 110.0;
          final innerHeight = (constraints.maxHeight - topInset - bottomInset).clamp(0.0, constraints.maxHeight);
          final orbSize = compact ? 190.0 : (innerHeight * .73).clamp(180.0, 300.0);
          final canMove = constraints.maxWidth > orbSize + 30 && innerHeight > orbSize + 20;
          return Stack(
            clipBehavior: Clip.hardEdge,
            children: [
              Positioned.fill(child: CustomPaint(painter: _StageGridPainter())),
              Positioned(
                top: 24,
                left: 25,
                right: 25,
                child: Row(children: [
                  const _Eyebrow(label: 'VOICE CORE / LOCAL INFERENCE'),
                  const Spacer(),
                  if (_orbMoved)
                    TextButton.icon(
                      onPressed: () => setState(() { _orbOffset = Offset.zero; _orbMoved = false; }),
                      icon: const Icon(Icons.center_focus_strong, size: 14),
                      label: const Text('Reset position', style: TextStyle(fontSize: 10)),
                    ),
                ]),
              ),
              Positioned(
                top: compact ? 62 : 66,
                left: 22,
                right: 22,
                child: Text(
                  _mode == 'listening' ? 'I’m listening.' : _mode == 'thinking' ? 'Working on it.' : _mode == 'speaking' ? 'Here’s what I found.' : 'Speak naturally.',
                  textAlign: TextAlign.center,
                  style: TextStyle(fontSize: compact ? 27 : 33, height: 1.1, fontWeight: FontWeight.w700, letterSpacing: -1.0, color: const Color(0xFFE8F5FF)),
                ),
              ),
              Positioned.fill(
                top: topInset,
                bottom: bottomInset,
                child: Stack(
                  clipBehavior: Clip.hardEdge,
                  children: [
                    Positioned(
                      left: size.width / 2 - orbSize / 2 + (canMove ? _orbOffset.dx : 0),
                      top: (innerHeight - orbSize) / 2 - (compact ? 6 : 0) + (canMove ? _orbOffset.dy : 0),
                      width: orbSize,
                      height: orbSize,
                      child: GestureDetector(
                        onPanUpdate: canMove ? (details) => _onOrbPanUpdate(details, Size(size.width, innerHeight)) : null,
                        child: HolographicOrb(mode: _mode, size: orbSize),
                      ),
                    ),
                    _buildFloatingChip(
                      stageSize: Size(size.width, innerHeight),
                      position: Offset(22, innerHeight * .29),
                      label: 'LOCAL MODEL',
                      value: _installedModels.isEmpty ? 'NOT FOUND' : _truncate(_selectedModelName, 21),
                      color: _installedModels.isEmpty ? const Color(0xFFFFA1AE) : _cyan,
                      icon: Icons.memory_rounded,
                    ),
                    _buildFloatingChip(
                      stageSize: Size(size.width, innerHeight),
                      position: Offset((constraints.maxWidth - 175).clamp(0.0, constraints.maxWidth), innerHeight * .68),
                      label: 'VOICE ENGINE',
                      value: _whisperReady ? 'OFFLINE WHISPER' : 'SETUP NEEDED',
                      color: _whisperReady ? const Color(0xFF85EDC3) : const Color(0xFFFFC17B),
                      icon: Icons.graphic_eq_rounded,
                    ),
                  ],
                ),
              ),
              Positioned(
                left: 24,
                right: 24,
                bottom: compact ? 17 : 22,
                child: Column(children: [
                  Text(_status, maxLines: 2, overflow: TextOverflow.ellipsis, textAlign: TextAlign.center, style: TextStyle(fontSize: 11, color: _mode == 'error' ? const Color(0xFFFFA8B1) : _muted)),
                  const SizedBox(height: 14),
                  Center(
                    child: FilledButton.icon(
                      onPressed: _booting ? null : _startVoiceSession,
                      style: FilledButton.styleFrom(
                        backgroundColor: _voiceSession ? const Color(0xFF3C2538) : const Color(0xFFB9F7FF),
                        foregroundColor: _voiceSession ? const Color(0xFFFFCBD5) : const Color(0xFF091427),
                        disabledBackgroundColor: const Color(0xFF30394F),
                        padding: const EdgeInsets.symmetric(horizontal: 23, vertical: 17),
                        shape: const StadiumBorder(),
                        elevation: 0,
                      ),
                      icon: Icon(_voiceSession ? Icons.stop_circle_outlined : Icons.mic_rounded, size: 19),
                      label: Text(_voiceSession ? 'End voice session' : _booting ? 'Connecting…' : 'Activate FRIDAY', style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w800, letterSpacing: .25)),
                    ),
                  ),
                  if (!_backendReady && !_booting) ...[
                    const SizedBox(height: 9),
                    TextButton.icon(
                      onPressed: _settingsDialog,
                      icon: const Icon(Icons.settings_ethernet, size: 14),
                      label: const Text('Configure local connection', style: TextStyle(fontSize: 10)),
                    ),
                  ],
                ]),
              ),
            ],
          );
        }),
      ),
    );
  }

  Widget _buildFloatingChip({
    required Size stageSize,
    required Offset position,
    required String label,
    required String value,
    required Color color,
    required IconData icon,
  }) {
    final offset = _chipOffsets[label] ?? position;
    final maxX = (stageSize.width - 174).clamp(0.0, stageSize.width);
    final maxY = (stageSize.height - 62).clamp(0.0, stageSize.height);
    return Positioned(
      left: offset.dx.clamp(0.0, maxX),
      top: offset.dy.clamp(0.0, maxY),
      child: GestureDetector(
        onPanUpdate: (details) {
          setState(() {
            final next = (_chipOffsets[label] ?? position) + details.delta;
            _chipOffsets[label] = Offset(next.dx.clamp(0.0, maxX), next.dy.clamp(0.0, maxY));
          });
        },
        child: MouseRegion(
          cursor: SystemMouseCursors.grab,
          child: _RuntimeChip(label: label, value: value, color: color, icon: icon),
        ),
      ),
    );
  }

  Widget _buildConversationPanel() {
    return Container(
      decoration: BoxDecoration(
        color: const Color(0xC90D1427),
        borderRadius: BorderRadius.circular(24),
        border: Border.all(color: _line),
      ),
      clipBehavior: Clip.antiAlias,
      child: Column(
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(20, 21, 16, 16),
            child: Row(children: [
              const Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                _Eyebrow(label: 'LIVE SESSION'),
                SizedBox(height: 7),
                Text('Conversation memory', style: TextStyle(fontSize: 17, fontWeight: FontWeight.w700)),
              ])),
              IconButton(
                tooltip: 'Clear conversation',
                onPressed: _voiceSession || _processingTurn ? null : () {
                  setState(() { _messages.clear(); _lastTranscript = ''; _lastResponse = ''; });
                },
                icon: const Icon(Icons.delete_sweep_outlined, size: 19),
              ),
            ]),
          ),
          const Divider(height: 1, color: _line),
          Expanded(
            child: ListView(
              controller: _conversationScroll,
              padding: const EdgeInsets.all(17),
              children: [
                _ConversationBubble(
                  label: 'YOU · LAST TRANSCRIPT',
                  text: _lastTranscript.isEmpty ? 'Your spoken words will appear here after local Whisper transcribes a turn.' : _lastTranscript,
                  color: _cyan,
                  empty: _lastTranscript.isEmpty,
                ),
                const SizedBox(height: 13),
                _ConversationBubble(
                  label: 'FRIDAY · RESPONSE',
                  text: _lastResponse.isEmpty ? 'The selected model’s actual answer appears here. FRIDAY will speak it aloud.' : _lastResponse,
                  color: _violet,
                  empty: _lastResponse.isEmpty,
                ),
                const SizedBox(height: 18),
                Row(children: [
                  const Icon(Icons.bolt_rounded, size: 14, color: _cyan),
                  const SizedBox(width: 7),
                  Text(_providerLabel, style: const TextStyle(fontSize: 9, color: _muted, letterSpacing: .7)),
                ]),
                const SizedBox(height: 19),
                Container(height: 1, color: _line),
                const SizedBox(height: 16),
                const _Eyebrow(label: 'RUNTIME READINESS'),
                const SizedBox(height: 12),
                _ReadinessRow(label: 'Backend API', detail: _backendReady ? _settings.apiBaseUrl : 'Not connected', ready: _backendReady),
                const SizedBox(height: 10),
                _ReadinessRow(label: 'Ollama model', detail: _installedModels.isEmpty ? 'No model detected' : _selectedModelName, ready: _installedModels.isNotEmpty),
                const SizedBox(height: 10),
                _ReadinessRow(label: 'Offline speech', detail: _whisperReady ? 'Whisper installed' : 'Requires requirements-voice.txt', ready: _whisperReady),
                const SizedBox(height: 18),
                if (_lastError != null) _ErrorCard(message: _lastError!, onSettings: _settingsDialog),
                if (_lastResponse.isNotEmpty) Align(
                  alignment: Alignment.centerLeft,
                  child: TextButton.icon(
                    onPressed: _voiceSession ? null : () => _speak(_lastResponse),
                    icon: const Icon(Icons.volume_up_outlined, size: 16),
                    label: const Text('Speak response again', style: TextStyle(fontSize: 11)),
                  ),
                ),
              ],
            ),
          ),
          Padding(
            padding: const EdgeInsets.fromLTRB(17, 10, 17, 16),
            child: Row(children: [
              Expanded(child: Text(_voiceSession ? 'Hands-free session active' : 'Microphone starts only when activated', style: const TextStyle(fontSize: 10, color: _muted))),
              TextButton(onPressed: _showDiagnostics, child: const Text('Diagnostics', style: TextStyle(fontSize: 10))),
            ]),
          ),
        ],
      ),
    );
  }

  Widget _buildBottomStatus() {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 26, vertical: 12),
      decoration: const BoxDecoration(border: Border(top: BorderSide(color: Color(0x332F4164))), color: Color(0x44070B16)),
      child: Row(children: [
        _statusDot(active: _voiceSession, color: _voiceSession ? _cyan : _muted),
        const SizedBox(width: 8),
        Text(_voiceSession ? 'MICROPHONE ACTIVE' : 'VOICE SESSION OFF', style: const TextStyle(fontSize: 9, letterSpacing: 1.4, fontWeight: FontWeight.w800, color: _muted)),
        const SizedBox(width: 18),
        Container(width: 1, height: 14, color: _line),
        const SizedBox(width: 18),
        const Icon(Icons.shield_outlined, color: Color(0xFF83E9C0), size: 14),
        const SizedBox(width: 7),
        const Expanded(child: Text('LOCAL-FIRST · NO HIDDEN CLOUD FALLBACK · USER-CONTROLLED MIC', maxLines: 1, overflow: TextOverflow.ellipsis, style: TextStyle(fontSize: 9, color: _muted, letterSpacing: .65))),
        IconButton(
          tooltip: 'Copy backend address',
          visualDensity: VisualDensity.compact,
          onPressed: () async {
            await Clipboard.setData(ClipboardData(text: _settings.apiBaseUrl));
            _showMessage('Backend address copied.');
          },
          icon: const Icon(Icons.content_copy_rounded, size: 14, color: _muted),
        ),
      ]),
    );
  }
}

class _BackgroundPainter extends CustomPainter {
  _BackgroundPainter(this.phase);
  final double phase;

  @override
  void paint(Canvas canvas, Size size) {
    final rect = Offset.zero & size;
    canvas.drawRect(rect, Paint()..shader = const LinearGradient(
      begin: Alignment.topLeft,
      end: Alignment.bottomRight,
      colors: [Color(0xFF0A1325), Color(0xFF070B16), Color(0xFF090D1C)],
    ).createShader(rect));
    final a = Offset(size.width * (.7 + .04 * (phase - .5)), size.height * .24);
    canvas.drawCircle(a, size.shortestSide * .37, Paint()..shader = RadialGradient(colors: [
      const Color(0xFF316EB6).withValues(alpha: .17),
      const Color(0xFF4C3C94).withValues(alpha: .06),
      Colors.transparent,
    ]).createShader(Rect.fromCircle(center: a, radius: size.shortestSide * .37)));
    final b = Offset(size.width * .1, size.height * (.8 - .04 * (phase - .5)));
    canvas.drawCircle(b, size.shortestSide * .25, Paint()..shader = RadialGradient(colors: [
      const Color(0xFF3E98A8).withValues(alpha: .09),
      Colors.transparent,
    ]).createShader(Rect.fromCircle(center: b, radius: size.shortestSide * .25)));
  }

  @override
  bool shouldRepaint(covariant _BackgroundPainter oldDelegate) => oldDelegate.phase != phase;
}

class _StageGridPainter extends CustomPainter {
  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()..color = const Color(0xFF6F91CB).withValues(alpha: .06)..strokeWidth = .65;
    const step = 28.0;
    for (var x = 0.0; x <= size.width; x += step) canvas.drawLine(Offset(x, 0), Offset(x, size.height), paint);
    for (var y = 0.0; y <= size.height; y += step) canvas.drawLine(Offset(0, y), Offset(size.width, y), paint);
  }

  @override
  bool shouldRepaint(covariant _StageGridPainter oldDelegate) => false;
}

class _Eyebrow extends StatelessWidget {
  const _Eyebrow({required this.label});
  final String label;

  @override
  Widget build(BuildContext context) => Row(mainAxisSize: MainAxisSize.min, children: [
        Container(width: 18, height: 1, color: _cyan),
        const SizedBox(width: 8),
        Text(label, style: const TextStyle(fontSize: 8, fontWeight: FontWeight.w800, letterSpacing: 1.5, color: _muted)),
      ]);
}

class _RuntimeChip extends StatelessWidget {
  const _RuntimeChip({required this.label, required this.value, required this.color, required this.icon});
  final String label;
  final String value;
  final Color color;
  final IconData icon;

  @override
  Widget build(BuildContext context) => Container(
        constraints: const BoxConstraints(maxWidth: 172),
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 9),
        decoration: BoxDecoration(color: const Color(0xEE101A2E), borderRadius: BorderRadius.circular(12), border: Border.all(color: color.withValues(alpha: .3)), boxShadow: [BoxShadow(color: Colors.black.withValues(alpha: .2), blurRadius: 12, offset: const Offset(0, 5))]),
        child: Row(mainAxisSize: MainAxisSize.min, children: [
          Icon(icon, color: color, size: 17),
          const SizedBox(width: 8),
          Flexible(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text(label, maxLines: 1, overflow: TextOverflow.ellipsis, style: const TextStyle(fontSize: 7, letterSpacing: 1, color: _muted, fontWeight: FontWeight.w800)),
            const SizedBox(height: 4),
            Text(value, maxLines: 1, overflow: TextOverflow.ellipsis, style: TextStyle(fontSize: 9, color: color, fontWeight: FontWeight.w700)),
          ])),
          const SizedBox(width: 5),
          Icon(Icons.drag_indicator, color: color.withValues(alpha: .4), size: 12),
        ]),
      );
}

class _ConversationBubble extends StatelessWidget {
  const _ConversationBubble({required this.label, required this.text, required this.color, required this.empty});
  final String label;
  final String text;
  final Color color;
  final bool empty;

  @override
  Widget build(BuildContext context) => Container(
        padding: const EdgeInsets.all(13),
        decoration: BoxDecoration(color: color.withValues(alpha: .045), border: Border(left: BorderSide(color: color.withValues(alpha: .75), width: 2)), borderRadius: const BorderRadius.only(topRight: Radius.circular(10), bottomRight: Radius.circular(10))),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text(label, style: TextStyle(fontSize: 8, fontWeight: FontWeight.w800, letterSpacing: 1.15, color: color)),
          const SizedBox(height: 8),
          SelectableText(text, style: TextStyle(height: 1.6, fontSize: 12, color: empty ? _muted : const Color(0xFFE4EEFF))),
        ]),
      );
}

class _ReadinessRow extends StatelessWidget {
  const _ReadinessRow({required this.label, required this.detail, required this.ready});
  final String label;
  final String detail;
  final bool ready;

  @override
  Widget build(BuildContext context) => Row(children: [
        Icon(ready ? Icons.check_circle_rounded : Icons.error_outline_rounded, size: 15, color: ready ? const Color(0xFF73E8B9) : const Color(0xFFFFBF7B)),
        const SizedBox(width: 9),
        SizedBox(width: 93, child: Text(label, style: const TextStyle(fontSize: 10, fontWeight: FontWeight.w650, color: Color(0xFFD3E0FA)))),
        Expanded(child: Text(detail, maxLines: 1, overflow: TextOverflow.ellipsis, style: const TextStyle(fontSize: 9, color: _muted))),
      ]);
}

class _ErrorCard extends StatelessWidget {
  const _ErrorCard({required this.message, required this.onSettings});
  final String message;
  final VoidCallback onSettings;

  @override
  Widget build(BuildContext context) => Container(
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(color: const Color(0x22FF7E91), borderRadius: BorderRadius.circular(11), border: Border.all(color: const Color(0x66FF7E91))),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          const Row(children: [Icon(Icons.warning_amber_rounded, color: Color(0xFFFFA8B1), size: 16), SizedBox(width: 7), Text('Needs attention', style: TextStyle(fontWeight: FontWeight.w750, fontSize: 11, color: Color(0xFFFFBBC3)))]),
          const SizedBox(height: 8),
          SelectableText(message, style: const TextStyle(fontSize: 10, height: 1.5, color: Color(0xFFE9CFD5))),
          Align(alignment: Alignment.centerRight, child: TextButton(onPressed: onSettings, child: const Text('Fix connection', style: TextStyle(fontSize: 10)))),
        ]),
      );
}
), ''),
        backendProjectPath: pathController.text.trim(),
        autoStartBackend: autoStart,
        autoResumeListening: autoResume,
        modelRoute: modelRoute,
        voiceLocale: locale,
      );
      await FridaySettingsStore.save(_settings);
      await _stopVoiceSession();
      await _initialize();
    }
    apiController.dispose();
    pathController.dispose();
  }

  Future<void> _showDiagnostics() async {
    final settingsPath = await FridaySettingsStore.settingsPath();
    if (!mounted) return;
    await showDialog<void>(
      context: context,
      builder: (context) => AlertDialog(
        backgroundColor: const Color(0xFF111A30),
        title: const Text('Runtime diagnostics'),
        content: SizedBox(
          width: 580,
          child: SingleChildScrollView(
            child: SelectableText([
              'API: ${_settings.apiBaseUrl}',
              'Project: ${_settings.backendProjectPath.isEmpty ? 'auto-detected' : _settings.backendProjectPath}',
              'Settings file: $settingsPath',
              'Selected model route: ${_settings.modelRoute}',
              'Ollama: ${_voiceStatus['ollama_reachable'] == true ? 'reachable' : 'not detected'}',
              'Installed models: ${_installedModels.isEmpty ? 'none detected' : _installedModels.join(', ')}',
              'Local speech: ${_whisperReady ? 'Whisper installed' : 'not installed'}',
              'Backend process output: ${_backend?.lastProcessOutput ?? 'no process log available'}',
              if (_lastError != null) 'Last error: $_lastError',
              ..._events,
            ].join('\n'), style: const TextStyle(fontFamily: 'Consolas', fontSize: 11, height: 1.5)),
          ),
        ),
        actions: [
          TextButton.icon(
            onPressed: () async {
              await Clipboard.setData(ClipboardData(text: settingsPath));
              if (context.mounted) Navigator.pop(context);
            },
            icon: const Icon(Icons.copy),
            label: const Text('Copy settings path'),
          ),
          TextButton(onPressed: () => Navigator.pop(context), child: const Text('Close')),
        ],
      ),
    );
  }

  void _showMessage(String message) {
    if (!mounted || _disposed) return;
    ScaffoldMessenger.of(context)
      ..hideCurrentSnackBar()
      ..showSnackBar(SnackBar(content: Text(message)));
  }

  String _truncate(String value, int max) => value.length <= max ? value : '${value.substring(0, max - 1)}…';

  void _onOrbPanUpdate(DragUpdateDetails details, Size stageSize) {
    final next = _orbOffset + details.delta;
    final maxX = (stageSize.width / 2) - 104;
    final maxY = (stageSize.height / 2) - 104;
    setState(() {
      _orbOffset = Offset(next.dx.clamp(-maxX, maxX), next.dy.clamp(-maxY, maxY));
      _orbMoved = true;
    });
  }

  Widget _statusDot({required bool active, Color color = _cyan}) => Container(
        width: 7,
        height: 7,
        decoration: BoxDecoration(
          color: active ? color : const Color(0xFF63718F),
          shape: BoxShape.circle,
          boxShadow: active ? [BoxShadow(color: color.withValues(alpha: .58), blurRadius: 9)] : null,
        ),
      );

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Stack(
        children: [
          Positioned.fill(
            child: AnimatedBuilder(
              animation: _backgroundAnimation!,
              builder: (context, _) => CustomPaint(painter: _BackgroundPainter(_backgroundAnimation!.value)),
            ),
          ),
          SafeArea(
            child: Column(
              children: [
                _buildTopBar(),
                Expanded(
                  child: LayoutBuilder(builder: (context, constraints) {
                    final wide = constraints.maxWidth >= 920;
                    if (wide) {
                      return Padding(
                        padding: const EdgeInsets.fromLTRB(30, 20, 30, 14),
                        child: Row(
                          crossAxisAlignment: CrossAxisAlignment.stretch,
                          children: [
                            Expanded(flex: 6, child: _buildStage()),
                            const SizedBox(width: 18),
                            Expanded(flex: 4, child: _buildConversationPanel()),
                          ],
                        ),
                      );
                    }
                    return Padding(
                      padding: const EdgeInsets.fromLTRB(16, 12, 16, 12),
                      child: Column(
                        children: [
                          Expanded(flex: 6, child: _buildStage(compact: true)),
                          const SizedBox(height: 12),
                          Expanded(flex: 5, child: _buildConversationPanel()),
                        ],
                      ),
                    );
                  }),
                ),
                _buildBottomStatus(),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildTopBar() {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 26, vertical: 17),
      decoration: const BoxDecoration(
        color: Color(0x66070B16),
        border: Border(bottom: BorderSide(color: Color(0x332F4164))),
      ),
      child: Row(children: [
        Container(
          width: 42,
          height: 42,
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(13),
            border: Border.all(color: _cyan.withValues(alpha: .5)),
            gradient: const LinearGradient(colors: [Color(0x3329DBF0), Color(0x33A99CFF)]),
            boxShadow: [BoxShadow(color: _cyan.withValues(alpha: .09), blurRadius: 24)],
          ),
          alignment: Alignment.center,
          child: const Text('F', style: TextStyle(fontSize: 23, fontWeight: FontWeight.w800, color: Color(0xFFC5FCFF))),
        ),
        const SizedBox(width: 12),
        const Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text('FRIDAY', style: TextStyle(fontWeight: FontWeight.w900, letterSpacing: 3, fontSize: 16)),
          SizedBox(height: 3),
          Text('PERSONAL INTELLIGENCE', style: TextStyle(fontSize: 8, color: _muted, letterSpacing: 1.8, fontWeight: FontWeight.w700)),
        ]),
        const Spacer(),
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 9),
          decoration: BoxDecoration(color: _panel, borderRadius: BorderRadius.circular(30), border: Border.all(color: _line)),
          child: Row(children: [
            _statusDot(active: _backendReady, color: _backendReady ? const Color(0xFF6AE6B6) : const Color(0xFFFF9BA8)),
            const SizedBox(width: 8),
            Text(_connectionLabel, style: const TextStyle(fontSize: 11, color: Color(0xFFD5E1FA))),
          ]),
        ),
        const SizedBox(width: 10),
        IconButton(
          tooltip: 'Refresh connections',
          onPressed: _booting ? null : _initialize,
          icon: const Icon(Icons.sync_rounded),
        ),
        IconButton(
          tooltip: 'Connection settings',
          onPressed: _settingsDialog,
          icon: const Icon(Icons.tune_rounded),
        ),
        IconButton(
          tooltip: 'Diagnostics',
          onPressed: _showDiagnostics,
          icon: const Icon(Icons.monitor_heart_outlined),
        ),
      ]),
    );
  }

  Widget _buildStage({bool compact = false}) {
    return ClipRRect(
      borderRadius: BorderRadius.circular(26),
      child: Container(
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(26),
          border: Border.all(color: _line.withValues(alpha: .82)),
          gradient: const LinearGradient(
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
            colors: [Color(0xB5121D36), Color(0xB5091021), Color(0x8810172C)],
          ),
        ),
        child: LayoutBuilder(builder: (context, constraints) {
          final size = Size(constraints.maxWidth, constraints.maxHeight);
          final topInset = compact ? 98.0 : 112.0;
          final bottomInset = compact ? 104.0 : 110.0;
          final innerHeight = (constraints.maxHeight - topInset - bottomInset).clamp(0.0, constraints.maxHeight);
          final orbSize = compact ? 190.0 : (innerHeight * .73).clamp(180.0, 300.0);
          final canMove = constraints.maxWidth > orbSize + 30 && innerHeight > orbSize + 20;
          return Stack(
            clipBehavior: Clip.hardEdge,
            children: [
              Positioned.fill(child: CustomPaint(painter: _StageGridPainter())),
              Positioned(
                top: 24,
                left: 25,
                right: 25,
                child: Row(children: [
                  const _Eyebrow(label: 'VOICE CORE / LOCAL INFERENCE'),
                  const Spacer(),
                  if (_orbMoved)
                    TextButton.icon(
                      onPressed: () => setState(() { _orbOffset = Offset.zero; _orbMoved = false; }),
                      icon: const Icon(Icons.center_focus_strong, size: 14),
                      label: const Text('Reset position', style: TextStyle(fontSize: 10)),
                    ),
                ]),
              ),
              Positioned(
                top: compact ? 62 : 66,
                left: 22,
                right: 22,
                child: Text(
                  _mode == 'listening' ? 'I’m listening.' : _mode == 'thinking' ? 'Working on it.' : _mode == 'speaking' ? 'Here’s what I found.' : 'Speak naturally.',
                  textAlign: TextAlign.center,
                  style: TextStyle(fontSize: compact ? 27 : 33, height: 1.1, fontWeight: FontWeight.w700, letterSpacing: -1.0, color: const Color(0xFFE8F5FF)),
                ),
              ),
              Positioned.fill(
                top: topInset,
                bottom: bottomInset,
                child: Stack(
                  clipBehavior: Clip.hardEdge,
                  children: [
                    Positioned(
                      left: size.width / 2 - orbSize / 2 + (canMove ? _orbOffset.dx : 0),
                      top: (innerHeight - orbSize) / 2 - (compact ? 6 : 0) + (canMove ? _orbOffset.dy : 0),
                      width: orbSize,
                      height: orbSize,
                      child: GestureDetector(
                        onPanUpdate: canMove ? (details) => _onOrbPanUpdate(details, Size(size.width, innerHeight)) : null,
                        child: HolographicOrb(mode: _mode, size: orbSize),
                      ),
                    ),
                    _buildFloatingChip(
                      stageSize: Size(size.width, innerHeight),
                      position: Offset(22, innerHeight * .29),
                      label: 'LOCAL MODEL',
                      value: _installedModels.isEmpty ? 'NOT FOUND' : _truncate(_selectedModelName, 21),
                      color: _installedModels.isEmpty ? const Color(0xFFFFA1AE) : _cyan,
                      icon: Icons.memory_rounded,
                    ),
                    _buildFloatingChip(
                      stageSize: Size(size.width, innerHeight),
                      position: Offset((constraints.maxWidth - 175).clamp(0.0, constraints.maxWidth), innerHeight * .68),
                      label: 'VOICE ENGINE',
                      value: _whisperReady ? 'OFFLINE WHISPER' : 'SETUP NEEDED',
                      color: _whisperReady ? const Color(0xFF85EDC3) : const Color(0xFFFFC17B),
                      icon: Icons.graphic_eq_rounded,
                    ),
                  ],
                ),
              ),
              Positioned(
                left: 24,
                right: 24,
                bottom: compact ? 17 : 22,
                child: Column(children: [
                  Text(_status, maxLines: 2, overflow: TextOverflow.ellipsis, textAlign: TextAlign.center, style: TextStyle(fontSize: 11, color: _mode == 'error' ? const Color(0xFFFFA8B1) : _muted)),
                  const SizedBox(height: 14),
                  Center(
                    child: FilledButton.icon(
                      onPressed: _booting ? null : _startVoiceSession,
                      style: FilledButton.styleFrom(
                        backgroundColor: _voiceSession ? const Color(0xFF3C2538) : const Color(0xFFB9F7FF),
                        foregroundColor: _voiceSession ? const Color(0xFFFFCBD5) : const Color(0xFF091427),
                        disabledBackgroundColor: const Color(0xFF30394F),
                        padding: const EdgeInsets.symmetric(horizontal: 23, vertical: 17),
                        shape: const StadiumBorder(),
                        elevation: 0,
                      ),
                      icon: Icon(_voiceSession ? Icons.stop_circle_outlined : Icons.mic_rounded, size: 19),
                      label: Text(_voiceSession ? 'End voice session' : _booting ? 'Connecting…' : 'Activate FRIDAY', style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w800, letterSpacing: .25)),
                    ),
                  ),
                  if (!_backendReady && !_booting) ...[
                    const SizedBox(height: 9),
                    TextButton.icon(
                      onPressed: _settingsDialog,
                      icon: const Icon(Icons.settings_ethernet, size: 14),
                      label: const Text('Configure local connection', style: TextStyle(fontSize: 10)),
                    ),
                  ],
                ]),
              ),
            ],
          );
        }),
      ),
    );
  }

  Widget _buildFloatingChip({
    required Size stageSize,
    required Offset position,
    required String label,
    required String value,
    required Color color,
    required IconData icon,
  }) {
    final offset = _chipOffsets[label] ?? position;
    final maxX = (stageSize.width - 174).clamp(0.0, stageSize.width);
    final maxY = (stageSize.height - 62).clamp(0.0, stageSize.height);
    return Positioned(
      left: offset.dx.clamp(0.0, maxX),
      top: offset.dy.clamp(0.0, maxY),
      child: GestureDetector(
        onPanUpdate: (details) {
          setState(() {
            final next = (_chipOffsets[label] ?? position) + details.delta;
            _chipOffsets[label] = Offset(next.dx.clamp(0.0, maxX), next.dy.clamp(0.0, maxY));
          });
        },
        child: MouseRegion(
          cursor: SystemMouseCursors.grab,
          child: _RuntimeChip(label: label, value: value, color: color, icon: icon),
        ),
      ),
    );
  }

  Widget _buildConversationPanel() {
    return Container(
      decoration: BoxDecoration(
        color: const Color(0xC90D1427),
        borderRadius: BorderRadius.circular(24),
        border: Border.all(color: _line),
      ),
      clipBehavior: Clip.antiAlias,
      child: Column(
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(20, 21, 16, 16),
            child: Row(children: [
              const Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                _Eyebrow(label: 'LIVE SESSION'),
                SizedBox(height: 7),
                Text('Conversation memory', style: TextStyle(fontSize: 17, fontWeight: FontWeight.w700)),
              ])),
              IconButton(
                tooltip: 'Clear conversation',
                onPressed: _voiceSession || _processingTurn ? null : () {
                  setState(() { _messages.clear(); _lastTranscript = ''; _lastResponse = ''; });
                },
                icon: const Icon(Icons.delete_sweep_outlined, size: 19),
              ),
            ]),
          ),
          const Divider(height: 1, color: _line),
          Expanded(
            child: ListView(
              controller: _conversationScroll,
              padding: const EdgeInsets.all(17),
              children: [
                _ConversationBubble(
                  label: 'YOU · LAST TRANSCRIPT',
                  text: _lastTranscript.isEmpty ? 'Your spoken words will appear here after local Whisper transcribes a turn.' : _lastTranscript,
                  color: _cyan,
                  empty: _lastTranscript.isEmpty,
                ),
                const SizedBox(height: 13),
                _ConversationBubble(
                  label: 'FRIDAY · RESPONSE',
                  text: _lastResponse.isEmpty ? 'The selected model’s actual answer appears here. FRIDAY will speak it aloud.' : _lastResponse,
                  color: _violet,
                  empty: _lastResponse.isEmpty,
                ),
                const SizedBox(height: 18),
                Row(children: [
                  const Icon(Icons.bolt_rounded, size: 14, color: _cyan),
                  const SizedBox(width: 7),
                  Text(_providerLabel, style: const TextStyle(fontSize: 9, color: _muted, letterSpacing: .7)),
                ]),
                const SizedBox(height: 19),
                Container(height: 1, color: _line),
                const SizedBox(height: 16),
                const _Eyebrow(label: 'RUNTIME READINESS'),
                const SizedBox(height: 12),
                _ReadinessRow(label: 'Backend API', detail: _backendReady ? _settings.apiBaseUrl : 'Not connected', ready: _backendReady),
                const SizedBox(height: 10),
                _ReadinessRow(label: 'Ollama model', detail: _installedModels.isEmpty ? 'No model detected' : _selectedModelName, ready: _installedModels.isNotEmpty),
                const SizedBox(height: 10),
                _ReadinessRow(label: 'Offline speech', detail: _whisperReady ? 'Whisper installed' : 'Requires requirements-voice.txt', ready: _whisperReady),
                const SizedBox(height: 18),
                if (_lastError != null) _ErrorCard(message: _lastError!, onSettings: _settingsDialog),
                if (_lastResponse.isNotEmpty) Align(
                  alignment: Alignment.centerLeft,
                  child: TextButton.icon(
                    onPressed: _voiceSession ? null : () => _speak(_lastResponse),
                    icon: const Icon(Icons.volume_up_outlined, size: 16),
                    label: const Text('Speak response again', style: TextStyle(fontSize: 11)),
                  ),
                ),
              ],
            ),
          ),
          Padding(
            padding: const EdgeInsets.fromLTRB(17, 10, 17, 16),
            child: Row(children: [
              Expanded(child: Text(_voiceSession ? 'Hands-free session active' : 'Microphone starts only when activated', style: const TextStyle(fontSize: 10, color: _muted))),
              TextButton(onPressed: _showDiagnostics, child: const Text('Diagnostics', style: TextStyle(fontSize: 10))),
            ]),
          ),
        ],
      ),
    );
  }

  Widget _buildBottomStatus() {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 26, vertical: 12),
      decoration: const BoxDecoration(border: Border(top: BorderSide(color: Color(0x332F4164))), color: Color(0x44070B16)),
      child: Row(children: [
        _statusDot(active: _voiceSession, color: _voiceSession ? _cyan : _muted),
        const SizedBox(width: 8),
        Text(_voiceSession ? 'MICROPHONE ACTIVE' : 'VOICE SESSION OFF', style: const TextStyle(fontSize: 9, letterSpacing: 1.4, fontWeight: FontWeight.w800, color: _muted)),
        const SizedBox(width: 18),
        Container(width: 1, height: 14, color: _line),
        const SizedBox(width: 18),
        const Icon(Icons.shield_outlined, color: Color(0xFF83E9C0), size: 14),
        const SizedBox(width: 7),
        const Expanded(child: Text('LOCAL-FIRST · NO HIDDEN CLOUD FALLBACK · USER-CONTROLLED MIC', maxLines: 1, overflow: TextOverflow.ellipsis, style: TextStyle(fontSize: 9, color: _muted, letterSpacing: .65))),
        IconButton(
          tooltip: 'Copy backend address',
          visualDensity: VisualDensity.compact,
          onPressed: () async {
            await Clipboard.setData(ClipboardData(text: _settings.apiBaseUrl));
            _showMessage('Backend address copied.');
          },
          icon: const Icon(Icons.content_copy_rounded, size: 14, color: _muted),
        ),
      ]),
    );
  }
}

class _BackgroundPainter extends CustomPainter {
  _BackgroundPainter(this.phase);
  final double phase;

  @override
  void paint(Canvas canvas, Size size) {
    final rect = Offset.zero & size;
    canvas.drawRect(rect, Paint()..shader = const LinearGradient(
      begin: Alignment.topLeft,
      end: Alignment.bottomRight,
      colors: [Color(0xFF0A1325), Color(0xFF070B16), Color(0xFF090D1C)],
    ).createShader(rect));
    final a = Offset(size.width * (.7 + .04 * (phase - .5)), size.height * .24);
    canvas.drawCircle(a, size.shortestSide * .37, Paint()..shader = RadialGradient(colors: [
      const Color(0xFF316EB6).withValues(alpha: .17),
      const Color(0xFF4C3C94).withValues(alpha: .06),
      Colors.transparent,
    ]).createShader(Rect.fromCircle(center: a, radius: size.shortestSide * .37)));
    final b = Offset(size.width * .1, size.height * (.8 - .04 * (phase - .5)));
    canvas.drawCircle(b, size.shortestSide * .25, Paint()..shader = RadialGradient(colors: [
      const Color(0xFF3E98A8).withValues(alpha: .09),
      Colors.transparent,
    ]).createShader(Rect.fromCircle(center: b, radius: size.shortestSide * .25)));
  }

  @override
  bool shouldRepaint(covariant _BackgroundPainter oldDelegate) => oldDelegate.phase != phase;
}

class _StageGridPainter extends CustomPainter {
  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()..color = const Color(0xFF6F91CB).withValues(alpha: .06)..strokeWidth = .65;
    const step = 28.0;
    for (var x = 0.0; x <= size.width; x += step) canvas.drawLine(Offset(x, 0), Offset(x, size.height), paint);
    for (var y = 0.0; y <= size.height; y += step) canvas.drawLine(Offset(0, y), Offset(size.width, y), paint);
  }

  @override
  bool shouldRepaint(covariant _StageGridPainter oldDelegate) => false;
}

class _Eyebrow extends StatelessWidget {
  const _Eyebrow({required this.label});
  final String label;

  @override
  Widget build(BuildContext context) => Row(mainAxisSize: MainAxisSize.min, children: [
        Container(width: 18, height: 1, color: _cyan),
        const SizedBox(width: 8),
        Text(label, style: const TextStyle(fontSize: 8, fontWeight: FontWeight.w800, letterSpacing: 1.5, color: _muted)),
      ]);
}

class _RuntimeChip extends StatelessWidget {
  const _RuntimeChip({required this.label, required this.value, required this.color, required this.icon});
  final String label;
  final String value;
  final Color color;
  final IconData icon;

  @override
  Widget build(BuildContext context) => Container(
        constraints: const BoxConstraints(maxWidth: 172),
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 9),
        decoration: BoxDecoration(color: const Color(0xEE101A2E), borderRadius: BorderRadius.circular(12), border: Border.all(color: color.withValues(alpha: .3)), boxShadow: [BoxShadow(color: Colors.black.withValues(alpha: .2), blurRadius: 12, offset: const Offset(0, 5))]),
        child: Row(mainAxisSize: MainAxisSize.min, children: [
          Icon(icon, color: color, size: 17),
          const SizedBox(width: 8),
          Flexible(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text(label, maxLines: 1, overflow: TextOverflow.ellipsis, style: const TextStyle(fontSize: 7, letterSpacing: 1, color: _muted, fontWeight: FontWeight.w800)),
            const SizedBox(height: 4),
            Text(value, maxLines: 1, overflow: TextOverflow.ellipsis, style: TextStyle(fontSize: 9, color: color, fontWeight: FontWeight.w700)),
          ])),
          const SizedBox(width: 5),
          Icon(Icons.drag_indicator, color: color.withValues(alpha: .4), size: 12),
        ]),
      );
}

class _ConversationBubble extends StatelessWidget {
  const _ConversationBubble({required this.label, required this.text, required this.color, required this.empty});
  final String label;
  final String text;
  final Color color;
  final bool empty;

  @override
  Widget build(BuildContext context) => Container(
        padding: const EdgeInsets.all(13),
        decoration: BoxDecoration(color: color.withValues(alpha: .045), border: Border(left: BorderSide(color: color.withValues(alpha: .75), width: 2)), borderRadius: const BorderRadius.only(topRight: Radius.circular(10), bottomRight: Radius.circular(10))),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text(label, style: TextStyle(fontSize: 8, fontWeight: FontWeight.w800, letterSpacing: 1.15, color: color)),
          const SizedBox(height: 8),
          SelectableText(text, style: TextStyle(height: 1.6, fontSize: 12, color: empty ? _muted : const Color(0xFFE4EEFF))),
        ]),
      );
}

class _ReadinessRow extends StatelessWidget {
  const _ReadinessRow({required this.label, required this.detail, required this.ready});
  final String label;
  final String detail;
  final bool ready;

  @override
  Widget build(BuildContext context) => Row(children: [
        Icon(ready ? Icons.check_circle_rounded : Icons.error_outline_rounded, size: 15, color: ready ? const Color(0xFF73E8B9) : const Color(0xFFFFBF7B)),
        const SizedBox(width: 9),
        SizedBox(width: 93, child: Text(label, style: const TextStyle(fontSize: 10, fontWeight: FontWeight.w650, color: Color(0xFFD3E0FA)))),
        Expanded(child: Text(detail, maxLines: 1, overflow: TextOverflow.ellipsis, style: const TextStyle(fontSize: 9, color: _muted))),
      ]);
}

class _ErrorCard extends StatelessWidget {
  const _ErrorCard({required this.message, required this.onSettings});
  final String message;
  final VoidCallback onSettings;

  @override
  Widget build(BuildContext context) => Container(
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(color: const Color(0x22FF7E91), borderRadius: BorderRadius.circular(11), border: Border.all(color: const Color(0x66FF7E91))),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          const Row(children: [Icon(Icons.warning_amber_rounded, color: Color(0xFFFFA8B1), size: 16), SizedBox(width: 7), Text('Needs attention', style: TextStyle(fontWeight: FontWeight.w750, fontSize: 11, color: Color(0xFFFFBBC3)))]),
          const SizedBox(height: 8),
          SelectableText(message, style: const TextStyle(fontSize: 10, height: 1.5, color: Color(0xFFE9CFD5))),
          Align(alignment: Alignment.centerRight, child: TextButton(onPressed: onSettings, child: const Text('Fix connection', style: TextStyle(fontSize: 10)))),
        ]),
      );
}
