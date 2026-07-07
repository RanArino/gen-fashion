import 'package:cloud_firestore/cloud_firestore.dart' show Timestamp;
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gen_fashion_web/api/api_client.dart';
import 'package:gen_fashion_web/closet/closet_item.dart';
import 'package:gen_fashion_web/closet/closet_screen.dart';
import 'package:gen_fashion_web/closet/thumbnail.dart' show DownloadUrlCache;

import 'test_app.dart';

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
      localizedTestApp(
        ClosetGrid(
          items: items,
          cache: cache,
          thumbnailBuilder: (_, item) =>
              Container(key: ValueKey('thumb-${item.id}')),
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

  testWidgets('renders ownership chips for Owned and Interesting items',
      (tester) async {
    final cache = DownloadUrlCache(ApiClient());
    final items = [
      ClosetItem(
        id: 'own1',
        status: ItemStatus.ready,
        category: 'tops',
        createdAt: DateTime.now(),
      ),
      ClosetItem(
        id: 'int1',
        status: ItemStatus.ready,
        ownership: ItemOwnership.interesting,
        origin: 'RAKUTEN',
        category: 'hat',
        createdAt: DateTime.now(),
      ),
    ];

    await tester.pumpWidget(
      localizedTestApp(
        ClosetGrid(
          items: items,
          cache: cache,
          thumbnailBuilder: (_, item) =>
              Container(key: ValueKey('thumb-${item.id}')),
        ),
      ),
    );
    await tester.pump();

    expect(find.text('Owned'), findsOneWidget);
    expect(find.text('Interesting'), findsOneWidget);
    // Both items stay READY regardless of ownership.
    expect(find.text('READY'), findsNWidgets(2));
  });

  testWidgets('localizes canonical season and color metadata on closet cards',
      (tester) async {
    final item = ClosetItem(
      id: 'localized',
      status: ItemStatus.ready,
      category: 'pants',
      colors: const ['grey', 'blue'],
      season: 'all season',
      createdAt: DateTime.now(),
    );

    await tester.pumpWidget(
      localizedTestApp(
        ClosetCard(
          item: item,
          thumbnail: const SizedBox.shrink(),
        ),
        locale: const Locale('ja'),
      ),
    );
    await tester.pump();

    expect(find.textContaining('通年'), findsOneWidget);
    expect(find.textContaining('グレー/青'), findsOneWidget);

    await tester.pumpWidget(
      localizedTestApp(
        ClosetCard(
          item: item,
          thumbnail: const SizedBox.shrink(),
        ),
        locale: const Locale('en'),
      ),
    );
    await tester.pump();

    expect(find.textContaining('all season'), findsOneWidget);
    expect(find.textContaining('gray/blue'), findsOneWidget);
  });

  testWidgets(
      'shows a Rakuten product link only for Interesting items with a URL',
      (tester) async {
    final cache = DownloadUrlCache(ApiClient());
    final items = [
      ClosetItem(
        id: 'int-linked',
        status: ItemStatus.ready,
        ownership: ItemOwnership.interesting,
        origin: 'RAKUTEN',
        category: 'hat',
        affiliateUrl: 'https://hb.afl.rakuten.co.jp/hgc/xyz',
        createdAt: DateTime.now(),
      ),
      ClosetItem(
        id: 'int-no-url',
        status: ItemStatus.ready,
        ownership: ItemOwnership.interesting,
        category: 'shoes',
        createdAt: DateTime.now(),
      ),
      ClosetItem(
        id: 'owned',
        status: ItemStatus.ready,
        category: 'tops',
        createdAt: DateTime.now(),
      ),
    ];

    await tester.pumpWidget(
      localizedTestApp(
        ClosetGrid(
          items: items,
          cache: cache,
          thumbnailBuilder: (_, item) =>
              Container(key: ValueKey('thumb-${item.id}')),
        ),
      ),
    );
    await tester.pump();

    expect(find.byIcon(Icons.open_in_new), findsOneWidget);
  });

  test('ClosetItem.fromFirestore parses ownership and external fields', () {
    final imported = ClosetItem.fromFirestore('id1', {
      'status': 'READY',
      'ownershipStatus': 'INTERESTING',
      'origin': 'RAKUTEN',
      'externalUrl': 'https://item.rakuten.co.jp/shop/1001',
      'affiliateUrl': 'https://hb.afl.rakuten.co.jp/hgc/xyz',
      'price': 2980,
    });
    expect(imported.status, ItemStatus.ready);
    expect(imported.ownership, ItemOwnership.interesting);
    expect(imported.origin, 'RAKUTEN');
    expect(imported.externalUrl, 'https://item.rakuten.co.jp/shop/1001');
    expect(imported.affiliateUrl, 'https://hb.afl.rakuten.co.jp/hgc/xyz');
    expect(imported.productUrl, 'https://hb.afl.rakuten.co.jp/hgc/xyz');
    expect(imported.price, 2980);

    // Pre-MK documents without ownershipStatus default to Owned.
    final legacy = ClosetItem.fromFirestore('id2', {'status': 'READY'});
    expect(legacy.ownership, ItemOwnership.owned);
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

    final processing =
        ClosetItem.fromFirestore('id2', {'status': 'PROCESSING'});
    expect(processing.status, ItemStatus.processing);
    expect(processing.tags, isEmpty);

    final unknown = ClosetItem.fromFirestore('id3', {'status': 'WAT'});
    expect(unknown.status, ItemStatus.unknown);
  });
}
