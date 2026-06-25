import 'package:cloud_firestore/cloud_firestore.dart' show Timestamp;
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gen_fashion_web/api/api_client.dart';
import 'package:gen_fashion_web/closet/closet_item.dart';
import 'package:gen_fashion_web/closet/closet_screen.dart';
import 'package:gen_fashion_web/closet/thumbnail.dart'
    show DownloadUrlCache;

void main() {
  testWidgets('renders PROCESSING and READY badges and the empty state',
      (tester) async {
    final cache = DownloadUrlCache(ApiClient());

    // Empty state.
    await tester.pumpWidget(
      const MaterialApp(
        home: Scaffold(
          body: Center(
            child: Column(
              key: ValueKey('empty-state'),
              children: [Text('Add your first item to get started.')],
            ),
          ),
        ),
      ),
    );
    expect(find.text('Add your first item to get started.'), findsOneWidget);

    // Grid with PROCESSING + READY.
    final items = [
      ClosetItem(
        id: 'p1',
        status: ItemStatus.processing,
        createdAt: DateTime.now(),
      ),
      ClosetItem(
        id: 'r1',
        status: ItemStatus.ready,
        category: 'tops',
        tags: const ['casual', 'cotton'],
        createdAt: DateTime.now(),
      ),
    ];
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: ClosetGrid(
            items: items,
            cache: cache,
            thumbnailBuilder: (_, item) =>
                Container(key: ValueKey('thumb-${item.id}')),
          ),
        ),
      ),
    );
    await tester.pump();

    expect(find.text('PROCESSING'), findsOneWidget);
    expect(find.text('READY'), findsOneWidget);
    expect(find.text('tops'), findsOneWidget);
    expect(find.text('casual, cotton'), findsOneWidget);
    expect(find.byKey(const ValueKey('thumb-p1')), findsOneWidget);
    expect(find.byKey(const ValueKey('thumb-r1')), findsOneWidget);
  });

  test('ClosetItem.fromFirestore parses statuses and tags', () {
    final item = ClosetItem.fromFirestore('id1', {
      'status': 'READY',
      'category': 'tops',
      'tags': ['casual', 'summer'],
      'colors': ['blue'],
      'season': 'summer',
      'createdAt': Timestamp.fromDate(DateTime(2026, 6, 6)),
    });
    expect(item.status, ItemStatus.ready);
    expect(item.category, 'tops');
    expect(item.tags, ['casual', 'summer']);
    expect(item.colors, ['blue']);
    expect(item.season, 'summer');
    expect(item.createdAt, DateTime(2026, 6, 6));

    final processing = ClosetItem.fromFirestore('id2', {'status': 'PROCESSING'});
    expect(processing.status, ItemStatus.processing);
    expect(processing.tags, isEmpty);

    final unknown = ClosetItem.fromFirestore('id3', {'status': 'WAT'});
    expect(unknown.status, ItemStatus.unknown);
  });
}
