// Voice in (speech_to_text) and voice out (flutter_tts). Degrades quietly:
// if the phone has no recogniser, the mic button explains and does nothing.
// Hindi and Hinglish use hi-IN (people speak Hindi words), English en-IN,
// the same choice as the web client. Read-aloud uses the API's trace.speech
// (Devanagari for Hindi and Hinglish), Google's TTS engine when installed, and
// the best installed voice for the locale rather than the engine default.

import 'dart:async';
import 'dart:io' show Platform;

import 'package:flutter/foundation.dart';
import 'package:flutter_tts/flutter_tts.dart';
import 'package:speech_to_text/speech_recognition_error.dart';
import 'package:speech_to_text/speech_recognition_result.dart';
import 'package:speech_to_text/speech_to_text.dart';

import 'models.dart';

String localeFor(Lang lang) => lang == Lang.en ? 'en-IN' : 'hi-IN';

/// The API's read-aloud text when it sent one, else the on-screen text.
Speech speechFor(Speech? spoken, String shown, Lang lang) => spoken != null
    ? Speech(spoken.text, spoken.locale, alt: shown)
    : Speech(shown, localeFor(lang), alt: lang == Lang.en ? null : shown);

const _googleTts = 'com.google.android.tts';
const _quality = {'very high': 5, 'high': 4, 'normal': 3, 'low': 2, 'very low': 1};

class Voice {
  final SpeechToText _stt = SpeechToText();
  FlutterTts? _tts;
  Future<FlutterTts>? _ttsInit;
  int _gen = 0; // bumped by every speak/stop, so a read-aloud still setting up can be cancelled
  final Map<String, Map<String, String>?> _voices = {};
  bool _sttReady = false;
  bool? _sttAvailable;

  /// Notifies true while the mic is listening.
  final ValueNotifier<bool> listening = ValueNotifier(false);

  /// Id of what is being read aloud right now (null when silent).
  final ValueNotifier<String?> speaking = ValueNotifier(null);

  void Function()? _onDone;

  /// Starts dictation. [onText] receives the live transcript (partial and
  /// final) so the user can fix it before sending. Returns false when speech
  /// recognition is not available on this phone or permission was refused.
  Future<bool> startListening(
    Lang lang,
    void Function(String text, bool isFinal) onText, {
    void Function()? onDone,
  }) async {
    try {
      if (!_sttReady) {
        _sttAvailable = await _stt.initialize(onStatus: _onStatus, onError: _onError);
        _sttReady = true;
      }
      if (_sttAvailable != true) return false;
      await stopSpeaking();
      _onDone = onDone;
      await _stt.listen(
        onResult: (SpeechRecognitionResult r) => onText(r.recognizedWords, r.finalResult),
        listenOptions: SpeechListenOptions(
          localeId: localeFor(lang),
          partialResults: true,
          cancelOnError: true,
          listenMode: ListenMode.dictation,
          listenFor: const Duration(seconds: 45),
          pauseFor: const Duration(seconds: 4),
        ),
      );
      listening.value = true;
      return true;
    } catch (_) {
      listening.value = false;
      return false;
    }
  }

  Future<void> stopListening() async {
    try {
      if (_stt.isListening) await _stt.stop();
    } catch (_) {}
    listening.value = false;
  }

  /// Stops and drops what is still being recognised (used on Send, so a late final result
  /// cannot refill the cleared text box).
  Future<void> cancelListening() async {
    try {
      if (_stt.isListening) await _stt.cancel();
    } catch (_) {}
    listening.value = false;
  }

  void _onStatus(String status) {
    if (status == 'done' || status == 'notListening') {
      if (listening.value) {
        listening.value = false;
        final cb = _onDone;
        _onDone = null;
        cb?.call();
      }
    }
  }

  void _onError(SpeechRecognitionError e) {
    listening.value = false;
    _onDone = null;
  }

  /// Sets up text-to-speech early (the engine switch and voice list take a
  /// second), so the first read-aloud starts at once.
  void warmUp() {
    if (kIsWeb || !Platform.isAndroid) return;
    unawaited(_ensureTts().then((_) {}, onError: (_) {}));
  }

  Future<FlutterTts> _ensureTts() => _ttsInit ??= _initTts().catchError((Object e) {
        _ttsInit = null;
        throw e;
      });

  Future<FlutterTts> _initTts() async {
    final tts = FlutterTts();
    tts.setCompletionHandler(() => speaking.value = null);
    tts.setCancelHandler(() => speaking.value = null);
    tts.setErrorHandler((_) => speaking.value = null);
    try {
      await tts.awaitSpeakCompletion(false);
    } catch (_) {}
    // Phone makers' own engines (Samsung, Xiaomi) often have weak Hindi voices;
    // Google's is kept only if its Hindi voice is installed on this phone.
    try {
      final engines = await tts.getEngines;
      final def = await tts.getDefaultEngine;
      if (engines is List && engines.contains(_googleTts) && def != _googleTts) {
        await tts.setEngine(_googleTts).timeout(const Duration(seconds: 4));
        final hindi = await _bestVoice(tts, 'hi-IN');
        if (hindi == null && def is String && def.isNotEmpty) {
          await tts.setEngine(def).timeout(const Duration(seconds: 4));
        } else {
          _voices['hi-IN'] = hindi;
        }
      }
    } catch (_) {}
    _tts = tts;
    return tts;
  }

  /// Best installed voice for [locale]: highest quality, the exact locale
  /// (Indian English over US English), and on-device over network voices.
  Future<Map<String, String>?> _bestVoice(FlutterTts tts, String locale) async {
    final want = locale.toLowerCase();
    Map<String, String>? best;
    var bestScore = -1;
    try {
      final list = await tts.getVoices;
      if (list is! List) return null;
      for (final raw in list) {
        if (raw is! Map) continue;
        final name = '${raw['name'] ?? ''}';
        final loc = '${raw['locale'] ?? ''}';
        final l = loc.toLowerCase().replaceAll('_', '-');
        if (name.isEmpty || !l.startsWith(want.substring(0, 2))) continue;
        if ('${raw['features'] ?? ''}'.contains('notInstalled')) continue;
        var s = (_quality['${raw['quality']}'] ?? 3) * 10;
        if (l == want) s += 15;
        if ('${raw['network_required']}' == '1') s -= 3;
        if (s > bestScore) {
          best = {'name': name, 'locale': loc};
          bestScore = s;
        }
      }
    } catch (_) {}
    return best;
  }

  /// Sets the voice for [locale]; false when the phone cannot speak it.
  Future<bool> _useLocale(FlutterTts tts, String locale) async {
    if (!_voices.containsKey(locale)) _voices[locale] = await _bestVoice(tts, locale);
    final v = _voices[locale];
    if (v != null && await tts.setVoice(v) == 1) return true;
    if (await tts.isLanguageAvailable(locale) == true) {
      await tts.setLanguage(locale);
      return true;
    }
    return false;
  }

  /// Reads [s] aloud (a touch slower than normal, like the web).
  Future<void> speak(Speech s, {String? id}) async {
    if (s.text.trim().isEmpty) return;
    final gen = ++_gen;
    try {
      final tts = await _ensureTts();
      if (gen != _gen) return; // stopped (or the mic opened) while setting up
      await tts.stop();
      var text = s.text;
      if (!await _useLocale(tts, s.locale)) {
        // No Hindi voice on this phone: the on-screen text with an Indian English voice.
        if (s.alt == null || !await _useLocale(tts, 'en-IN')) return;
        text = s.alt!;
      }
      await tts.setSpeechRate(0.47);
      await tts.setPitch(1.0);
      if (gen != _gen) return;
      speaking.value = id ?? text;
      await tts.speak(text);
    } catch (_) {
      if (gen == _gen) speaking.value = null;
    }
  }

  Future<void> stopSpeaking() async {
    _gen++;
    try {
      await _tts?.stop();
    } catch (_) {}
    speaking.value = null;
  }

  void dispose() {
    unawaited(stopListening());
    unawaited(stopSpeaking());
    listening.dispose();
    speaking.dispose();
  }
}
