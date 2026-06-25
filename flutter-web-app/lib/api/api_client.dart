import 'dart:convert';

import 'package:firebase_auth/firebase_auth.dart';
import 'package:http/http.dart' as http;

import '../config.dart';

class ClosetFullException implements Exception {
  const ClosetFullException();
  @override
  String toString() => 'Closet is full (20 items).';
}

class ApiException implements Exception {
  ApiException(this.statusCode, this.body);
  final int statusCode;
  final String body;
  @override
  String toString() => 'API error $statusCode: $body';
}

/// Thin wrapper around the FastAPI closet endpoints. Attaches the Firebase ID
/// token automatically; constructs object-key/URL operations the backend
/// expects. The token source is pluggable so unit tests can avoid initializing
/// Firebase.
class ApiClient {
  ApiClient({
    http.Client? httpClient,
    String? baseUrl,
    Future<String?> Function()? tokenProvider,
  })  : _http = httpClient ?? http.Client(),
        _baseUrl = baseUrl ?? AppConfig.apiBaseUrl,
        _tokenProvider = tokenProvider ?? _firebaseIdToken;

  final http.Client _http;
  final String _baseUrl;
  final Future<String?> Function() _tokenProvider;

  static Future<String?> _firebaseIdToken() async {
    final user = FirebaseAuth.instance.currentUser;
    if (user == null) {
      throw StateError('Not signed in');
    }
    return user.getIdToken();
  }

  Future<Map<String, String>> _authHeaders() async {
    final token = await _tokenProvider();
    if (token == null) {
      throw StateError('No ID token available');
    }
    return {'Authorization': 'Bearer $token'};
  }

  /// `GET /closet/upload-url?item_id=...`.
  /// Returns the signed PUT URL. Maps `429` to [ClosetFullException].
  Future<String> getUploadUrl(String itemId) async {
    final uri = Uri.parse('$_baseUrl/closet/upload-url')
        .replace(queryParameters: {'item_id': itemId});
    final res = await _http.get(uri, headers: await _authHeaders());
    if (res.statusCode == 429) {
      throw const ClosetFullException();
    }
    if (res.statusCode != 200) {
      throw ApiException(res.statusCode, res.body);
    }
    final body = jsonDecode(res.body) as Map<String, dynamic>;
    return body['upload_url'] as String;
  }

  /// `GET /closet/items/{id}/download-url` — 1h signed GET URL for thumbnails.
  Future<String> getDownloadUrl(String itemId) async {
    final uri = Uri.parse('$_baseUrl/closet/items/$itemId/download-url');
    final res = await _http.get(uri, headers: await _authHeaders());
    if (res.statusCode != 200) {
      throw ApiException(res.statusCode, res.body);
    }
    final body = jsonDecode(res.body) as Map<String, dynamic>;
    return body['download_url'] as String;
  }

  /// `POST /closet/items/{id}/complete` — backend writes PROCESSING doc and
  /// enqueues the analysis worker.
  Future<void> completeUpload(String itemId) async {
    final uri = Uri.parse('$_baseUrl/closet/items/$itemId/complete');
    final res = await _http.post(uri, headers: await _authHeaders());
    if (res.statusCode != 200) {
      throw ApiException(res.statusCode, res.body);
    }
  }

  /// `DELETE /closet/items/{id}` — treats `204` and `404` (already-deleted) as
  /// success.
  Future<void> deleteItem(String itemId) async {
    final uri = Uri.parse('$_baseUrl/closet/items/$itemId');
    final res = await _http.delete(uri, headers: await _authHeaders());
    if (res.statusCode == 204 || res.statusCode == 404) return;
    throw ApiException(res.statusCode, res.body);
  }
}
