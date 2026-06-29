import 'dart:convert';

import 'package:firebase_auth/firebase_auth.dart';
import 'package:http/http.dart' as http;

import '../config.dart';
import '../history/history_item.dart';
import 'streaming_http_client.dart'
    if (dart.library.html) 'streaming_http_client_web.dart';

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
  })  : _http = httpClient ?? createStreamingClient(),
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

  Future<Map<String, String>> _jsonHeaders() async {
    return {
      ...await _authHeaders(),
      'Content-Type': 'application/json',
    };
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

  Future<StyleSessionResponse> createSession() async {
    final uri = Uri.parse('$_baseUrl/sessions');
    final res = await _http.post(uri, headers: await _authHeaders());
    if (res.statusCode != 200 && res.statusCode != 201) {
      throw ApiException(res.statusCode, res.body);
    }
    return StyleSessionResponse.fromJson(
      jsonDecode(res.body) as Map<String, dynamic>,
    );
  }

  Future<List<SessionHistoryItem>> listSessions({int limit = 20}) async {
    final uri = Uri.parse('$_baseUrl/sessions')
        .replace(queryParameters: {'limit': '$limit'});
    final res = await _http.get(uri, headers: await _authHeaders());
    if (res.statusCode != 200) {
      throw ApiException(res.statusCode, res.body);
    }
    final data = jsonDecode(res.body) as List<dynamic>;
    return data
        .map(
          (item) => SessionHistoryItem.fromJson(
            item as Map<String, dynamic>,
          ),
        )
        .toList();
  }

  Future<SessionHistoryItem> getSession(String sessionId) async {
    final uri = Uri.parse('$_baseUrl/sessions/$sessionId');
    final res = await _http.get(uri, headers: await _authHeaders());
    if (res.statusCode != 200) {
      throw ApiException(res.statusCode, res.body);
    }
    return SessionHistoryItem.fromJson(
      jsonDecode(res.body) as Map<String, dynamic>,
    );
  }

  Future<StyleSessionResponse> selectSource({
    required String sessionId,
    required String source,
    required Map<String, String> userPreference,
    String? sharedClosetId,
  }) async {
    final uri = Uri.parse('$_baseUrl/sessions/$sessionId/source');
    final res = await _http.post(
      uri,
      headers: await _jsonHeaders(),
      body: jsonEncode({
        'source': source,
        'sharedClosetId': sharedClosetId,
        'userPreference': userPreference,
      }),
    );
    if (res.statusCode != 200 && res.statusCode != 202) {
      throw ApiException(res.statusCode, res.body);
    }
    return StyleSessionResponse.fromJson(
      jsonDecode(res.body) as Map<String, dynamic>,
    );
  }

  Future<StyleSessionResponse> selectCandidates({
    required String sessionId,
    required List<String> selectedItemIds,
  }) async {
    final uri = Uri.parse('$_baseUrl/sessions/$sessionId/select');
    final res = await _http.post(
      uri,
      headers: await _jsonHeaders(),
      body: jsonEncode({'selectedItemIds': selectedItemIds}),
    );
    if (res.statusCode != 200 && res.statusCode != 202) {
      throw ApiException(res.statusCode, res.body);
    }
    return StyleSessionResponse.fromJson(
      jsonDecode(res.body) as Map<String, dynamic>,
    );
  }

  Future<void> updateItemMetadata(
    String itemId,
    Map<String, dynamic> metadata,
  ) async {
    final uri = Uri.parse('$_baseUrl/closet/items/$itemId');
    final res = await _http.patch(
      uri,
      headers: await _jsonHeaders(),
      body: jsonEncode(metadata),
    );
    if (res.statusCode != 200) {
      throw ApiException(res.statusCode, res.body);
    }
  }

  Future<List<Map<String, dynamic>>> listSharedClosets() async {
    final uri = Uri.parse('$_baseUrl/shared-closets');
    final res = await _http.get(uri, headers: await _authHeaders());
    if (res.statusCode != 200) throw ApiException(res.statusCode, res.body);
    final body = jsonDecode(res.body) as Map<String, dynamic>;
    return (body['closets'] as List).cast<Map<String, dynamic>>();
  }

  Future<List<Map<String, dynamic>>> listSharedClosetItems(
    String closetId,
  ) async {
    final uri = Uri.parse('$_baseUrl/shared-closets/$closetId/items');
    final res = await _http.get(uri, headers: await _authHeaders());
    if (res.statusCode != 200) throw ApiException(res.statusCode, res.body);
    final body = jsonDecode(res.body) as Map<String, dynamic>;
    return (body['items'] as List).cast<Map<String, dynamic>>();
  }

  Stream<SseMessage> streamSessionEvents(String sessionId) async* {
    final uri = Uri.parse('$_baseUrl/sessions/$sessionId/stream');
    final request = http.Request('GET', uri);
    request.headers.addAll(await _authHeaders());
    final response = await _http.send(request);
    if (response.statusCode != 200) {
      final body = await response.stream.bytesToString();
      throw ApiException(response.statusCode, body);
    }

    String? eventName;
    final dataLines = <String>[];
    await for (final line in response.stream
        .transform(utf8.decoder)
        .transform(const LineSplitter())) {
      if (line.isEmpty) {
        if (eventName != null && dataLines.isNotEmpty) {
          final name = eventName;
          yield SseMessage(
            event: name,
            data: jsonDecode(dataLines.join('\n')) as Map<String, dynamic>,
          );
        }
        eventName = null;
        dataLines.clear();
      } else if (line.startsWith('event:')) {
        eventName = line.substring(6).trim();
      } else if (line.startsWith('data:')) {
        dataLines.add(line.substring(5).trim());
      }
    }
  }
}

class StyleSessionResponse {
  const StyleSessionResponse({
    required this.sessionId,
    required this.status,
    required this.source,
  });

  final String sessionId;
  final String status;
  final String source;

  factory StyleSessionResponse.fromJson(Map<String, dynamic> json) {
    return StyleSessionResponse(
      sessionId: json['session_id'] as String,
      status: json['status'] as String,
      source: json['source'] as String,
    );
  }
}

class SseMessage {
  const SseMessage({required this.event, required this.data});

  final String event;
  final Map<String, dynamic> data;
}
