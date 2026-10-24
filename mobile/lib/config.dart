import 'package:flutter/foundation.dart';

import 'models.dart';

/// Production API (HTTPS). Release builds talk to this unless overridden.
const String kProdApiBase = 'https://carecompass.145-223-21-27.sslip.io';

/// Debug default: the Android emulator's alias for the laptop running the API.
const String kDebugApiBase = 'http://10.0.2.2:8000';

const String _apiBaseOverride = String.fromEnvironment('API_BASE');

/// Base URL of the CareCompass REST API.
/// Override at build time: `--dart-define=API_BASE=https://...`.
String get apiBase {
  final raw = _apiBaseOverride.isNotEmpty ? _apiBaseOverride : (kReleaseMode ? kProdApiBase : kDebugApiBase);
  return raw.endsWith('/') ? raw.substring(0, raw.length - 1) : raw;
}

/// Follow-up policy the web app uses: "safety" adds a breathing check for
/// fever and cough cases.
const String kTriagePolicy = 'safety';

/// Fixed demo location (same as the web app): Okhla, New Delhi.
const LatLng kDemoLocation = LatLng(28.5459, 77.2732);

const Duration kRequestTimeout = Duration(seconds: 20);
