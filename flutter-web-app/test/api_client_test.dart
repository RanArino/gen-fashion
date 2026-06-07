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
}
