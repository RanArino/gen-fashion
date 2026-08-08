import 'package:flutter_test/flutter_test.dart';
import 'package:gen_fashion_web/closet/closet_item.dart';
import 'package:gen_fashion_web/closet/closet_screen.dart';

void main() {
  test('toggling an unselected id below the cap adds it', () {
    final result = toggleIntentSelection({'CONFIDENT'}, 'PROTECTED');
    expect(result, {'CONFIDENT', 'PROTECTED'});
  });

  test('toggling an already-selected id removes it', () {
    final result = toggleIntentSelection({'CONFIDENT', 'PROTECTED'}, 'PROTECTED');
    expect(result, {'CONFIDENT'});
  });

  test('rejects a 4th selection rather than evicting the 1st', () {
    const atCap = {'CONFIDENT', 'PROTECTED', 'BLEND_IN'};
    final result = toggleIntentSelection(atCap, 'AT_EASE');
    // Unchanged: still exactly the original three, in particular still
    // containing the first-selected id, not silently evicted to make room.
    expect(result, atCap);
    expect(result, contains('CONFIDENT'));
    expect(result.length, kMaxIntentTags);
  });

  test('removing while at the cap is still allowed', () {
    const atCap = {'CONFIDENT', 'PROTECTED', 'BLEND_IN'};
    final result = toggleIntentSelection(atCap, 'BLEND_IN');
    expect(result, {'CONFIDENT', 'PROTECTED'});
  });

  test('skip path: an item with no selections round-trips as empty', () {
    // Simulates never opening the selector / dismissing without choosing
    // anything: the selection set stays empty, matching a skipped item.
    var selected = <String>{};
    expect(selected, isEmpty);
    // No toggle calls at all is the skip path itself; nothing to assert
    // beyond the set remaining empty and, in the real dialog, that Save
    // sends an empty `intentTags` list rather than being blocked.
    selected = toggleIntentSelection(selected, 'CONFIDENT');
    selected = toggleIntentSelection(selected, 'CONFIDENT');
    expect(selected, isEmpty);
  });

  test('ClosetItem.fromFirestore parses intentTags, defaulting to empty', () {
    final tagged = ClosetItem.fromFirestore('id1', {
      'status': 'READY',
      'intentTags': ['CONFIDENT', 'PROTECTED'],
    });
    expect(tagged.intentTags, ['CONFIDENT', 'PROTECTED']);

    final untagged = ClosetItem.fromFirestore('id2', {'status': 'READY'});
    expect(untagged.intentTags, isEmpty);
  });
}
