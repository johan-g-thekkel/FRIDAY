import 'dart:convert';
import 'dart:io';

import 'package:path_provider/path_provider.dart';

class FridaySettings {
  const FridaySettings({
    this.apiBaseUrl = 'http://127.0.0.1:8000',
    this.backendProjectPath = '',
    this.autoStartBackend = true,
    this.modelRoute = 'auto',
    this.autoResumeListening = true,
    this.voiceLocale = 'en-IN',
  });

  final String apiBaseUrl;
  final String backendProjectPath;
  final bool autoStartBackend;
  final String modelRoute;
  final bool autoResumeListening;
  final String voiceLocale;

  FridaySettings copyWith({
    String? apiBaseUrl,
    String? backendProjectPath,
    bool? autoStartBackend,
    String? modelRoute,
    bool? autoResumeListening,
    String? voiceLocale,
  }) {
    return FridaySettings(
      apiBaseUrl: apiBaseUrl ?? this.apiBaseUrl,
      backendProjectPath: backendProjectPath ?? this.backendProjectPath,
      autoStartBackend: autoStartBackend ?? this.autoStartBackend,
      modelRoute: modelRoute ?? this.modelRoute,
      autoResumeListening: autoResumeListening ?? this.autoResumeListening,
      voiceLocale: voiceLocale ?? this.voiceLocale,
    );
  }

  Map<String, Object?> toJson() => {
        'api_base_url': apiBaseUrl,
        'backend_project_path': backendProjectPath,
        'auto_start_backend': autoStartBackend,
        'model_route': modelRoute,
        'auto_resume_listening': autoResumeListening,
        'voice_locale': voiceLocale,
      };

  factory FridaySettings.fromJson(Map<String, dynamic> json) {
    return FridaySettings(
      apiBaseUrl: _string(json['api_base_url'], 'http://127.0.0.1:8000'),
      backendProjectPath: _string(json['backend_project_path'], ''),
      autoStartBackend: json['auto_start_backend'] is bool ? json['auto_start_backend'] as bool : true,
      modelRoute: _string(json['model_route'], 'auto'),
      autoResumeListening: json['auto_resume_listening'] is bool ? json['auto_resume_listening'] as bool : true,
      voiceLocale: _string(json['voice_locale'], 'en-IN'),
    );
  }

  static String _string(Object? value, String fallback) {
    if (value is! String || value.trim().isEmpty) return fallback;
    return value.trim();
  }
}

class FridaySettingsStore {
  static Future<File> _file() async {
    final root = await getApplicationSupportDirectory();
    final folder = Directory('${root.path}${Platform.pathSeparator}FRIDAY');
    await folder.create(recursive: true);
    return File('${folder.path}${Platform.pathSeparator}connection.json');
  }

  static Future<FridaySettings> load() async {
    try {
      final file = await _file();
      if (!await file.exists()) return const FridaySettings();
      final decoded = jsonDecode(await file.readAsString());
      if (decoded is Map<String, dynamic>) return FridaySettings.fromJson(decoded);
    } catch (_) {
      // Corrupt or absent settings are recovered with safe local defaults.
    }
    return const FridaySettings();
  }

  static Future<void> save(FridaySettings settings) async {
    final file = await _file();
    await file.writeAsString(
      const JsonEncoder.withIndent('  ').convert(settings.toJson()),
      flush: true,
    );
  }

  static Future<String> settingsPath() async => (await _file()).path;
}
