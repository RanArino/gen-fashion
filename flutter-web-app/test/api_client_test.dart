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

  test('listSessions parses completed history and sends limit', () async {
    final mock = MockClient((req) async {
      expect(req.url.path, '/sessions');
      expect(req.url.queryParameters['limit'], '5');
      expect(req.headers['Authorization'], 'Bearer fake-token');
      return http.Response(
        jsonEncode([
          {
            'session_id': 'session-1',
            'status': 'COMPLETED',
            'created_at': '2026-06-24T10:30:00',
            'completed_at': '2026-06-24T10:32:00',
            'source': 'SHARED_CLOSET',
            'shared_closet_id': 'adult-01',
            'selected_items': [
              {
                'item_id': 'item-1',
                'image_url': 'https://example.test/item.jpg',
                'category': 'top',
                'gender': 'common',
              }
            ],
            'style_result': {
              'coordinate_image_url': 'https://example.test/result.jpg',
            },
          }
        ]),
        200,
      );
    });

    final sessions = await _client(mock).listSessions(limit: 5);

    expect(sessions.single.sessionId, 'session-1');
    expect(
      sessions.single.coordinateImageUrl,
      'https://example.test/result.jpg',
    );
    expect(sessions.single.selectedItems.single.itemId, 'item-1');
  });

  test('getSession parses current session state and proposed candidates',
      () async {
    final mock = MockClient((req) async {
      expect(req.url.path, '/sessions/session-1');
      expect(req.headers['Authorization'], 'Bearer fake-token');
      return http.Response(
        jsonEncode({
          'session_id': 'session-1',
          'status': 'PROPOSING',
          'source': 'SHARED_CLOSET',
          'proposed_candidates': [
            {'item_id': 'item-1', 'image_url': 'https://example.test/item.jpg'}
          ],
          'selected_items': const [],
          'style_result': {
            'coordinate_image_url': 'https://example.test/result.jpg',
          },
        }),
        200,
      );
    });

    final session = await _client(mock).getSession('session-1');

    expect(session.status, 'PROPOSING');
    expect(session.proposedCandidates.single['item_id'], 'item-1');
    expect(session.coordinateImageUrl, 'https://example.test/result.jpg');
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

    final messages =
        await _client(mock).streamSessionEvents('session-1').toList();

    expect(messages.single.event, 'agent.event');
    expect(messages.single.data['agentName'], 'ClosetAgent');
  });

  test('assistSession posts anchors and preference to /assist', () async {
    late Map<String, dynamic> body;
    final mock = MockClient((req) async {
      body = jsonDecode(req.body) as Map<String, dynamic>;
      expect(req.url.path, '/sessions/session-1/assist');
      expect(req.headers['Content-Type'], contains('application/json'));
      return http.Response(
        jsonEncode({
          'session_id': 'session-1',
          'status': 'SEARCHING',
          'source': 'CLOSET',
        }),
        202,
      );
    });

    final selected = await _client(mock).assistSession(
      sessionId: 'session-1',
      anchorItemIds: ['anchor-1', 'anchor-2'],
      userPreference: {'style': 'clean'},
    );

    expect(body['anchorItemIds'], ['anchor-1', 'anchor-2']);
    expect(body['userPreference'], {'style': 'clean'});
    expect(selected.status, 'SEARCHING');
    expect(selected.source, 'CLOSET');
  });

  test('importSuggestedItem posts candidate and returns new item id', () async {
    late Map<String, dynamic> body;
    final mock = MockClient((req) async {
      body = jsonDecode(req.body) as Map<String, dynamic>;
      expect(req.url.path, '/closet/import-suggestion');
      return http.Response(
        jsonEncode({
          'item_id': 'new-item',
          'status': 'READY',
          'ownershipStatus': 'INTERESTING',
        }),
        200,
      );
    });

    final itemId = await _client(mock).importSuggestedItem(
      sessionId: 'session-1',
      candidateId: 'rakuten:shop:1001',
    );

    expect(body['sessionId'], 'session-1');
    expect(body['candidateId'], 'rakuten:shop:1001');
    expect(itemId, 'new-item');
  });

  test('importSuggestedItem surfaces API errors', () async {
    final mock = MockClient((req) async => http.Response('bad', 400));
    expect(
      () => _client(mock).importSuggestedItem(
        sessionId: 'session-1',
        candidateId: 'x',
      ),
      throwsA(isA<ApiException>()),
    );
  });

  test('selectCandidates posts the explicit item selection', () async {
    late Map<String, dynamic> body;
    final mock = MockClient((req) async {
      body = jsonDecode(req.body) as Map<String, dynamic>;
      expect(req.url.path, '/sessions/session-1/select');
      return http.Response(
        jsonEncode({
          'session_id': 'session-1',
          'status': 'PROPOSING',
          'source': 'SHARED_CLOSET',
        }),
        202,
      );
    });

    await _client(mock).selectCandidates(
      sessionId: 'session-1',
      selectedItemIds: ['item-1'],
    );

    expect(body['selectedItemIds'], ['item-1']);
  });
}
