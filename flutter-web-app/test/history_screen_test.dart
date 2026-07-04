import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gen_fashion_web/api/api_client.dart';
import 'package:gen_fashion_web/history/history_item.dart';
import 'package:gen_fashion_web/history/history_screen.dart';

import 'test_app.dart';

class FakeApiClient extends ApiClient {
  FakeApiClient(this.sessions);

  final List<SessionHistoryItem> sessions;

  @override
  Future<List<SessionHistoryItem>> listSessions({int limit = 20}) async {
    return sessions;
  }
}

void main() {
  testWidgets('renders a completed session image and formatted date',
      (tester) async {
    final session = SessionHistoryItem(
      sessionId: 'session-1',
      status: 'COMPLETED',
      createdAt: DateTime(2026, 6, 24, 10, 30),
      completedAt: DateTime(2026, 6, 24, 10, 32),
      source: 'SHARED_CLOSET',
      sharedClosetId: 'adult-01',
      coordinateImageUrl: 'https://example.test/result.jpg',
      selectedItems: const [
        HistorySelectedItem(
          itemId: 'item-1',
          imageUrl: 'https://example.test/item.jpg',
        ),
      ],
    );

    await tester.pumpWidget(
      localizedTestApp(HistoryScreen(apiClient: FakeApiClient([session]))),
    );
    await tester.pump();

    expect(
      find.byKey(const ValueKey('history-image-session-1')),
      findsOneWidget,
    );
    final image = tester.widget<Image>(
      find.byKey(const ValueKey('history-image-session-1')),
    );
    expect(
        (image.image as NetworkImage).url, 'https://example.test/result.jpg');
    expect(find.text('2026-06-24 10:32'), findsOneWidget);
    expect(find.text('adult-01'), findsOneWidget);
  });

  testWidgets(
      'renders Rakuten-sourced selected items via the HTML <img> strategy',
      (tester) async {
    const session = SessionHistoryItem(
      sessionId: 'session-2',
      status: 'COMPLETED',
      source: 'CLOSET',
      coordinateImageUrl: 'https://example.test/result.jpg',
      selectedItems: [
        HistorySelectedItem(
          itemId: 'closet-item',
          imageUrl: 'https://example.test/closet-item.jpg',
          source: 'CLOSET',
        ),
        HistorySelectedItem(
          itemId: 'rakuten-item',
          imageUrl: 'https://thumbnail.image.rakuten.co.jp/item.jpg',
          source: 'RAKUTEN',
        ),
      ],
    );

    await tester.pumpWidget(
      localizedTestApp(HistoryScreen(apiClient: FakeApiClient([session]))),
    );
    await tester.pump();

    final closetImage = tester.widget<Image>(
      find.byKey(const ValueKey('history-selected-item-closet-item')),
    );
    final rakutenImage = tester.widget<Image>(
      find.byKey(const ValueKey('history-selected-item-rakuten-item')),
    );

    expect(
      (closetImage.image as NetworkImage).webHtmlElementStrategy,
      WebHtmlElementStrategy.never,
    );
    expect(
      (rakutenImage.image as NetworkImage).webHtmlElementStrategy,
      WebHtmlElementStrategy.prefer,
    );
  });
}
