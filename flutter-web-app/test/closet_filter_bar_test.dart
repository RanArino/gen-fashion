import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gen_fashion_web/closet/closet_item.dart';
import 'package:gen_fashion_web/closet/closet_screen.dart';

import 'test_app.dart';

void main() {
  testWidgets('renders distinct categories as chips exactly once, plus All',
      (tester) async {
    await tester.pumpWidget(
      localizedTestApp(
        ClosetFilterBar(
          categories: const ['shoes', 'tops'],
          ownershipFilter: null,
          categoryFilter: null,
          onOwnershipChanged: (_) {},
          onCategoryChanged: (_) {},
        ),
      ),
    );

    expect(find.widgetWithText(FilterChip, 'tops'), findsOneWidget);
    expect(find.widgetWithText(FilterChip, 'shoes'), findsOneWidget);
    expect(find.widgetWithText(FilterChip, 'All'), findsOneWidget);
  });

  testWidgets('hides the category row when no categories are present',
      (tester) async {
    await tester.pumpWidget(
      localizedTestApp(
        ClosetFilterBar(
          categories: const [],
          ownershipFilter: null,
          categoryFilter: null,
          onOwnershipChanged: (_) {},
          onCategoryChanged: (_) {},
        ),
      ),
    );

    expect(find.byType(FilterChip), findsNothing);
  });

  testWidgets('tapping an ownership segment reports the selected value',
      (tester) async {
    ItemOwnership? changed;
    var called = false;
    await tester.pumpWidget(
      localizedTestApp(
        ClosetFilterBar(
          categories: const [],
          ownershipFilter: null,
          categoryFilter: null,
          onOwnershipChanged: (value) {
            called = true;
            changed = value;
          },
          onCategoryChanged: (_) {},
        ),
      ),
    );

    await tester.tap(find.text('Owned'));
    await tester.pump();

    expect(called, isTrue);
    expect(changed, ItemOwnership.owned);
  });

  testWidgets('tapping the selected category chip toggles back to All',
      (tester) async {
    String? changed;
    var called = false;
    await tester.pumpWidget(
      localizedTestApp(
        ClosetFilterBar(
          categories: const ['tops'],
          ownershipFilter: null,
          categoryFilter: 'tops',
          onOwnershipChanged: (_) {},
          onCategoryChanged: (value) {
            called = true;
            changed = value;
          },
        ),
      ),
    );

    await tester.tap(find.widgetWithText(FilterChip, 'tops'));
    await tester.pump();

    expect(called, isTrue);
    expect(changed, isNull);
  });

  testWidgets('tapping an unselected category chip selects it exclusively',
      (tester) async {
    String? changed;
    await tester.pumpWidget(
      localizedTestApp(
        ClosetFilterBar(
          categories: const ['tops', 'shoes'],
          ownershipFilter: null,
          categoryFilter: null,
          onOwnershipChanged: (_) {},
          onCategoryChanged: (value) => changed = value,
        ),
      ),
    );

    await tester.tap(find.widgetWithText(FilterChip, 'shoes'));
    await tester.pump();

    expect(changed, 'shoes');
  });
}
