import 'package:flutter_test/flutter_test.dart';
import 'package:gen_fashion_web/closet/closet_item.dart';
import 'package:gen_fashion_web/closet/closet_screen.dart';

void main() {
  final owned = ClosetItem(
    id: 'owned-tops',
    status: ItemStatus.ready,
    category: 'tops',
  );
  final interestingTops = ClosetItem(
    id: 'interesting-tops',
    status: ItemStatus.ready,
    ownership: ItemOwnership.interesting,
    category: 'tops',
  );
  final interestingShoes = ClosetItem(
    id: 'interesting-shoes',
    status: ItemStatus.ready,
    ownership: ItemOwnership.interesting,
    category: 'shoes',
  );
  final items = [owned, interestingTops, interestingShoes];

  test('filters by ownership only', () {
    final result = applyClosetFilters(items, ownership: ItemOwnership.owned);
    expect(result, [owned]);
  });

  test('filters by category only', () {
    final result = applyClosetFilters(items, category: 'tops');
    expect(result, [owned, interestingTops]);
  });

  test('filters by ownership and category combined', () {
    final result = applyClosetFilters(
      items,
      ownership: ItemOwnership.interesting,
      category: 'tops',
    );
    expect(result, [interestingTops]);
  });

  test('no filters returns the input unchanged', () {
    final result = applyClosetFilters(items);
    expect(result, items);
  });

  test('empty input returns empty', () {
    expect(applyClosetFilters(const []), isEmpty);
  });

  test('category not present in any item returns empty', () {
    expect(applyClosetFilters(items, category: 'hats'), isEmpty);
  });
}
