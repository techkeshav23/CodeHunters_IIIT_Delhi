// HTTP contract with the backend (docs/API.md). Thin client: no triage logic
// here, only requests and parsing. Mirrors web/src/api.ts (without mocks).

import 'dart:convert';

import 'package:http/http.dart' as http;

import 'config.dart';
import 'models.dart';

class ApiException implements Exception {
  final String message;
  final int? status;
  const ApiException(this.message, [this.status]);
  @override
  String toString() => 'ApiException($status): $message';
}

class ApiClient {
  ApiClient({String? base, http.Client? client}) : base = base ?? apiBase, _client = client ?? http.Client();

  final String base;
  final http.Client _client;

  static const _jsonHeaders = {'Content-Type': 'application/json; charset=utf-8', 'Accept': 'application/json'};

  Map<String, Object?> _decode(http.Response res) {
    // Always decode as UTF-8: Hindi text must survive whatever charset header.
    final body = utf8.decode(res.bodyBytes);
    final data = jsonDecode(body);
    if (data is! Map) throw const ApiException('Unexpected response shape');
    return data.cast<String, Object?>();
  }

  Future<TriageResponse> triage(TriageRequest req) async {
    final uri = Uri.parse('$base/v1/triage?explain=true&policy=$kTriagePolicy');
    final res = await _client.post(uri, headers: _jsonHeaders, body: jsonEncode(req.toJson())).timeout(kRequestTimeout);
    if (res.statusCode != 200) throw ApiException('Triage failed', res.statusCode);
    return TriageResponse.fromJson(_decode(res));
  }

  Future<BookingResponse> createBooking(BookingRequest req) async {
    final uri = Uri.parse('$base/v1/bookings');
    final res = await _client.post(uri, headers: _jsonHeaders, body: jsonEncode(req.toJson())).timeout(kRequestTimeout);
    if (res.statusCode != 201 && res.statusCode != 200) {
      throw ApiException('Booking failed', res.statusCode);
    }
    final b = BookingResponse.fromJson(_decode(res));
    if (b.bookingId.isEmpty) throw const ApiException('Booking id missing');
    return b;
  }

  Future<HealthResponse> health() async {
    final res = await _client.get(Uri.parse('$base/health')).timeout(const Duration(seconds: 8));
    if (res.statusCode != 200) throw ApiException('Health failed', res.statusCode);
    return HealthResponse.fromJson(_decode(res));
  }

  /// Red-flag labels and helplines for the SOS tab. Falls back to the same
  /// built-in numbers as the web client when the server is unreachable.
  Future<LabelsResponse> labels() async {
    try {
      final res = await _client.get(Uri.parse('$base/v1/labels')).timeout(const Duration(seconds: 8));
      if (res.statusCode != 200) return LabelsResponse.fallback;
      return LabelsResponse.fromJson(_decode(res));
    } catch (_) {
      return LabelsResponse.fallback;
    }
  }
}
