// Voice in (speech_to_text) and voice out (flutter_tts). Degrades quietly:
// if the phone has no recogniser, the mic button explains and does nothing.
// Hindi and Hinglish use hi-IN (people speak Hindi words), English en-IN,
// the same choice as the web client.

import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:flutter_tts/flutter_tts.dart';
import 'package:speech_to_text/speech_recognition_error.dart';
import 'package:speech_to_text/speech_recognition_result.dart';
import 'package:speech_to_text/speech_to_text.dart';

import 'models.dart';

String localeFor(Lang lang) => lang == Lang.en ? 'en-IN' : 'hi-IN';

class Voice {
  final SpeechToText _stt = SpeechToText();
  FlutterTts? _tts;
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

  Future<FlutterTts> _ensureTts() async {
    final existing = _tts;
    if (existing != null) return existing;
    final tts = FlutterTts();
    tts.setCompletionHandler(() => speaking.value = null);
    tts.setCancelHandler(() => speaking.value = null);
    tts.setErrorHandler((_) => speaking.value = null);
    try {
      await tts.awaitSpeakCompletion(false);
    } catch (_) {}
    _tts = tts;
    return tts;
  }

  /// Reads [text] aloud in the voice for [lang] (slightly slow, like the web).
  Future<void> speak(String text, Lang lang, {String? id}) async {
    if (text.trim().isEmpty) return;
    try {
      final tts = await _ensureTts();
      await tts.stop();
      final locale = localeFor(lang);
      var ok = await tts.isLanguageAvailable(locale);
      if (ok == true) {
        await tts.setLanguage(locale);
      } else if (lang != Lang.en) {
        // Hinglish in Roman script reads acceptably with an Indian English voice.
        ok = await tts.isLanguageAvailable('en-IN');
        if (ok == true) await tts.setLanguage('en-IN');
      }
      await tts.setSpeechRate(0.45);
      speaking.value = id ?? text;
      await tts.speak(text);
    } catch (_) {
      speaking.value = null;
    }
  }

  Future<void> stopSpeaking() async {
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
