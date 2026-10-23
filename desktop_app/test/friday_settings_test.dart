import 'package:flutter_test/flutter_test.dart';
import 'package:friday_desktop/services/friday_settings.dart';

void main() {
  group('FridaySettings', () {
    test('uses safe local defaults', () {
      const settings = FridaySettings();
      expect(settings.apiBaseUrl, 'http://127.0.0.1:8000');
      expect(settings.backendProjectPath, isEmpty);
      expect(settings.autoStartBackend, isTrue);
      expect(settings.modelRoute, 'auto');
      expect(settings.autoResumeListening, isTrue);
    });

    test('round-trips the connection file format', () {
      final original = const FridaySettings(
        apiBaseUrl: 'http://127.0.0.1:8000',
        backendProjectPath: r'C:\FRIDAY',
        autoStartBackend: false,
        modelRoute: 'ollama_qwen2_5_1_5b',
        autoResumeListening: false,
        voiceLocale: 'en-GB',
      );
      final decoded = FridaySettings.fromJson(original.toJson());
      expect(decoded.apiBaseUrl, original.apiBaseUrl);
      expect(decoded.backendProjectPath, original.backendProjectPath);
      expect(decoded.autoStartBackend, isFalse);
      expect(decoded.modelRoute, original.modelRoute);
      expect(decoded.autoResumeListening, isFalse);
      expect(decoded.voiceLocale, original.voiceLocale);
    });

    test('recovers from missing or incorrectly typed settings', () {
      final settings = FridaySettings.fromJson({
        'api_base_url': 42,
        'auto_start_backend': 'yes',
        'model_route': null,
      });
      expect(settings.apiBaseUrl, 'http://127.0.0.1:8000');
      expect(settings.autoStartBackend, isTrue);
      expect(settings.modelRoute, 'auto');
    });
  });
}
