import 'dart:convert';
import 'dart:math';

import 'package:flutter/foundation.dart';
import 'package:http/http.dart' as http;

/// No token, signed session or password is persisted to device storage.
/// Backend checks RBAC/SoD, version and idempotency for every command.
class EasApiException implements Exception {
  final String code;
  final int status;
  final String correlationId;
  EasApiException(this.code, this.status, [this.correlationId = '']);
  @override
  String toString() => '$code (HTTP $status)${correlationId.isEmpty ? '' : ' · $correlationId'}';
}

class EasApi {
  EasApi(String server) : base = Uri.parse(server.replaceAll(RegExp(r'/+$'), '')) {
    if (!base.hasScheme || !['https', 'http'].contains(base.scheme) || base.host.isEmpty) {
      throw ArgumentError('EAS_API_BASE_URL phải là địa chỉ máy chủ HTTP(S).');
    }
    final local = {'localhost', '127.0.0.1', '10.0.2.2'}.contains(base.host);
    if (base.scheme != 'https' && (!kDebugMode || !local)) {
      throw ArgumentError('Chỉ cho phép HTTPS; HTTP local chỉ dùng trong debug.');
    }
  }

  final Uri base;
  final http.Client _client = http.Client();
  final Map<String, String> _cookies = {};
  String? get _csrf => _cookies['csrftoken'];

  void _captureCookies(http.Response response) {
    final header = response.headers['set-cookie'];
    if (header == null) return;
    // Multiple Set-Cookie fields can be combined by HTTP adapters. Do not
    // split on the comma in an Expires date (e.g. Wed, 21 Oct ...).
    for (final headerCookie in header.split(RegExp(r',(?=\s*[^\s;,=]+=)'))) {
      final nameValue = headerCookie.trim().split(';').first;
      final equal = nameValue.indexOf('=');
      if (equal < 1) continue;
      final name = nameValue.substring(0, equal).trim();
      final value = nameValue.substring(equal + 1).trim();
      if (!{'csrftoken', 'eas_session'}.contains(name)) continue;
      if (value.isEmpty || RegExp(r'max-age=0', caseSensitive: false).hasMatch(headerCookie)) {
        _cookies.remove(name);
      } else {
        _cookies[name] = value;
      }
    }
  }

  static String newIdempotencyKey() {
    final random = Random.secure();
    final bytes = List<int>.generate(16, (_) => random.nextInt(256));
    bytes[6] = (bytes[6] & 0x0f) | 0x40;
    bytes[8] = (bytes[8] & 0x3f) | 0x80;
    String hex(List<int> x) => x.map((v) => v.toRadixString(16).padLeft(2, '0')).join();
    return '${hex(bytes.sublist(0, 4))}-${hex(bytes.sublist(4, 6))}-${hex(bytes.sublist(6, 8))}-${hex(bytes.sublist(8, 10))}-${hex(bytes.sublist(10))}';
  }

  Future<Map<String, dynamic>> call(
    String path, {
    String method = 'GET',
    Map<String, dynamic>? data,
    bool command = false,
  }) async {
    final headers = <String, String>{'Accept': 'application/json'};
    if (_cookies.isNotEmpty) {
      headers['Cookie'] = _cookies.entries.map((e) => '${e.key}=${e.value}').join('; ');
    }
    if (method != 'GET') {
      headers['Content-Type'] = 'application/json';
      if (_csrf != null) headers['X-CSRFToken'] = Uri.decodeComponent(_csrf!);
      if (command) headers['Idempotency-Key'] = newIdempotencyKey();
    }
    final uri = base.resolve(path); // keep query parameters intact
    http.Response response;
    try {
      response = await _client.send(http.Request(method, uri)
        ..headers.addAll(headers)
        ..body = method == 'GET' ? '' : jsonEncode(data ?? <String, dynamic>{}))
          .then(http.Response.fromStream)
          .timeout(const Duration(seconds: 20));
    } catch (_) {
      throw EasApiException('NETWORK_UNAVAILABLE', 0);
    }
    _captureCookies(response);
    Map<String, dynamic>? parsed;
    try {
      parsed = jsonDecode(response.body) as Map<String, dynamic>;
    } catch (_) {
      // Django can return HTML for proxy errors; no HTML will enter a widget.
    }
    if (response.statusCode < 200 || response.statusCode >= 300) {
      final error = parsed?['error'];
      final code = error is Map ? '${error['code'] ?? 'HTTP_${response.statusCode}'}' : 'HTTP_${response.statusCode}';
      throw EasApiException(code, response.statusCode, '${parsed?['correlation_id'] ?? ''}');
    }
    if (parsed == null) throw EasApiException('INVALID_RESPONSE', response.statusCode);
    return parsed;
  }

  Future<void> initialize() async => call('/api/v1/auth/csrf');
  Future<Map<String, dynamic>> login(String user, String password) async {
    await initialize();
    final result = await call('/api/v1/auth/login',
        method: 'POST', data: {'username': user, 'password': password});
    final loginUser = result['user'] as Map<String, dynamic>;
    // SRS UC01: /auth/me is forbidden until a temporary password changes.
    // The login response has the flag needed to render the change form.
    if (loginUser['must_change_password'] == true) return loginUser;
    return me();
  }

  Future<Map<String, dynamic>> me() async =>
      (await call('/api/v1/auth/me'))['user'] as Map<String, dynamic>;

  Future<void> logout() async {
    try {
      await call('/api/v1/auth/logout', method: 'POST');
    } finally {
      _cookies.clear();
    }
  }

  Future<void> changePassword(String oldPassword, String newPassword) async {
    await call('/api/v1/auth/password', method: 'POST',
        data: {'current_password': oldPassword, 'new_password': newPassword});
  }

  Future<List<dynamic>> worklist(String tab) async =>
      (await call('/api/v1/requests?tab=$tab&limit=100'))['items'] as List<dynamic>;

  Future<Map<String, dynamic>> detail(String id) async =>
      (await call('/api/v1/requests/$id'))['request'] as Map<String, dynamic>;

  Future<Map<String, dynamic>> notifications() async => call('/api/v1/notifications?limit=100');
  Future<void> markRead(String id) async =>
      call('/api/v1/notifications/$id/read', method: 'PATCH');

  Future<void> requestAction(
      Map<String, dynamic> record, String action, String reason) async {
    final requestId = record['id'];
    final version = record['lock_version'];
    final prefix = '/api/v1/requests/$requestId';
    final body = <String, dynamic>{'expected_version': version};
    String path;
    switch (action) {
      case 'APPROVE':
      case 'REJECT':
      case 'NEEDS_INFO':
        path = '$prefix/approval-decisions';
        body.addAll({'outcome': action, 'reason': action == 'APPROVE' ? null : reason});
        break;
      case 'ACCEPT':
      case 'REWORK':
        path = '$prefix/acceptance-decisions';
        body.addAll({'outcome': action, 'reason': action == 'ACCEPT' ? null : reason});
        break;
      case 'CLAIM':
        path = '$prefix/execution/start';
        break;
      case 'CANCEL':
        path = '$prefix/cancel';
        body['reason'] = reason;
        break;
      case 'UNABLE_TO_CLAIM':
      case 'BLOCKED':
        path = '$prefix/issues';
        body.addAll({'kind': action, 'reason': reason});
        break;
      default:
        throw ArgumentError('Unsupported action $action');
    }
    await call(path, method: 'POST', data: body, command: true);
  }

  void close() {
    _cookies.clear();
    _client.close();
  }
}
