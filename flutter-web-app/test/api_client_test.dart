import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:gen_fashion_web/api/api_client.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

ApiClient _client(MockClient httpClient) => ApiClient(
      httpClient: httpClient,
      baseUrl: 'http://api.test',
      tokenProvider: () async => 'fake-token',
    );

void main() {
  test('getUploadUrl issues GET with item_id and bearer header', () async {
    http.BaseRequest? captured;
    final mock = MockClient((req) async {
      captured = req;
      return http.Response(
        jsonEncode({'upload_url': 'http://put/foo', 'item_id': 'abc'}),
        200,
        headers: {'content-type': 'application/json'},
      );
    });
    final res = await _client(mock).getUploadUrl('abc');
    expect(res, 'http://put/foo');
    expect(captured?.url.path, '/closet/upload-url');
    expect(captured?.url.queryParameters['item_id'], 'abc');
    expect(captured?.headers['Authorization'], 'Bearer fake-token');
  });

  test('getUploadUrl maps 429 to ClosetFullException', () async {
    final mock = MockClient((req) async => http.Response('cap', 429));
    expect(
      () => _client(mock).getUploadUrl('abc'),
      throwsA(isA<ClosetFullException>()),
    );
  });

  test('getDownloadUrl parses download_url', () async {
    final mock = MockClient((req) async => http.Response(
          jsonEncode({'download_url': 'http://get/foo'}),
          200,
        ));
    final res = await _client(mock).getDownloadUrl('abc');
    expect(res, 'http://get/foo');
  });

  test('deleteItem treats 204 and 404 as success and other codes as error',
      () async {
    final mock204 = MockClient((req) async => http.Response('', 204));
    await _client(mock204).deleteItem('abc');

    final mock404 = MockClient((req) async => http.Response('', 404));
    await _client(mock404).deleteItem('abc');

    final mock500 = MockClient((req) async => http.Response('oops', 500));
    expect(
      () => _client(mock500).deleteItem('abc'),
      throwsA(isA<ApiException>()),
    );
  });

  test('createSession and selectSource parse session responses', () async {
    final seen = <String>[];
    final mock = MockClient((req) async {
      seen.add('${req.method} ${req.url.path}');
      if (req.url.path == '/sessions') {
        return http.Response(
          jsonEncode({
            'session_id': 'session-1',
            'status': 'SOURCE_SELECTING',
            'source': 'UNSET',
          }),
          200,
        );
      }
      expect(req.headers['Content-Type'], contains('application/json'));
      return http.Response(
        jsonEncode({
          'session_id': 'session-1',
          'status': 'SEARCHING',
          'source': 'SHARED_CLOSET',
        }),
        202,
      );
    });

    final client = _client(mock);
    final created = await client.createSession();
    final selected = await client.selectSource(
      sessionId: created.sessionId,
      source: 'SHARED_CLOSET',
      sharedClosetId: 'adult-01',
      userPreference: {'style': 'clean'},
    );

    expect(seen, ['POST /sessions', 'POST /sessions/session-1/source']);
    expect(created.status, 'SOURCE_SELECTING');
    expect(selected.status, 'SEARCHING');
    expect(selected.source, 'SHARED_CLOSET');
  });

  test('streamSessionEvents parses SSE messages', () async {
    final mock = MockClient.streaming((req, bodyStream) async {
      expect(req.url.path, '/sessions/session-1/stream');
      return http.StreamedResponse(
        Stream.value(utf8.encode(
          'event: agent.event\n'
          'data: {"seq":1,"agentName":"ClosetAgent"}\n\n',
        )),
        200,
        headers: {'content-type': 'text/event-stream'},
      );
    });

    final messages = await _client(mock).streamSessionEvents('session-1').toList();

    expect(messages.single.event, 'agent.event');
    expect(messages.single.data['agentName'], 'ClosetAgent');
  });
}
