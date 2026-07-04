import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gen_fashion_web/api/api_client.dart';
import 'package:gen_fashion_web/closet/closet_item.dart';
import 'package:gen_fashion_web/coordination/coordination_screen.dart';
import 'package:gen_fashion_web/history/history_item.dart';

import 'test_app.dart';

List<ClosetItem> _readyItems(int count) => [
      for (var i = 0; i < count; i++)
        ClosetItem(id: 'item-$i', status: ItemStatus.ready, category: 'top'),
    ];

/// Fake backend for exercising the propose -> select -> generate flow
/// without real HTTP/SSE. First [streamSessionEvents] call (from `_start`)
/// yields the proposed candidates; the second (from `_generateSelected`)
/// yields the generated coordinate image.
class _FakeCoordinationApiClient extends ApiClient {
  _FakeCoordinationApiClient({required this.candidates});

  final List<Map<String, dynamic>> candidates;
  final List<String> importedCandidateIds = [];
  int _streamCalls = 0;
  bool _generated = false;

  static const _coordinateImageUrl = 'https://example.com/coordinate.jpg';

  @override
  Future<StyleSessionResponse> createSession() async {
    return const StyleSessionResponse(
      sessionId: 'session-1',
      status: 'PROPOSING',
      source: 'SHARED_CLOSET',
    );
  }

  @override
  Future<StyleSessionResponse> selectSource({
    required String sessionId,
    required String source,
    required Map<String, String> userPreference,
    String? sharedClosetId,
  }) async {
    return const StyleSessionResponse(
      sessionId: 'session-1',
      status: 'PROPOSING',
      source: 'SHARED_CLOSET',
    );
  }

  @override
  Future<StyleSessionResponse> selectCandidates({
    required String sessionId,
    required List<String> selectedItemIds,
  }) async {
    _generated = true;
    return const StyleSessionResponse(
      sessionId: 'session-1',
      status: 'GENERATING',
      source: 'SHARED_CLOSET',
    );
  }

  @override
  Future<String> importSuggestedItem({
    required String sessionId,
    required String candidateId,
  }) async {
    importedCandidateIds.add(candidateId);
    return 'closet-item-$candidateId';
  }

  @override
  Future<SessionHistoryItem> getSession(String sessionId) async {
    return SessionHistoryItem(
      sessionId: sessionId,
      status: _generated ? 'COMPLETED' : 'PROPOSING',
      selectedItems: const [],
      proposedCandidates: candidates,
      coordinateImageUrl: _generated ? _coordinateImageUrl : null,
    );
  }

  @override
  Stream<SseMessage> streamSessionEvents(String sessionId) async* {
    _streamCalls += 1;
    if (_streamCalls == 1) {
      yield SseMessage(
        event: 'session.proposed',
        data: {'candidates': candidates},
      );
      return;
    }
    yield const SseMessage(
      event: 'agent.event',
      data: {
        'seq': 1,
        'agentName': 'StylingAgent',
        'eventKind': 'tool_result',
        'toolName': 'style_synthesizer',
        'toolResult': {'coordinateImageUrl': _coordinateImageUrl},
      },
    );
  }
}

void main() {
  testWidgets('renders coordination controls and event accordion',
      (tester) async {
    await tester.pumpWidget(
      localizedTestApp(
        ListView(
          children: const [CoordinationScreen(uid: 'user-123')],
        ),
      ),
    );

    expect(find.text('Coordination'), findsOneWidget);
    expect(find.text('Closet Styling'), findsOneWidget);
    expect(find.text('Style & Shop'), findsOneWidget);
    expect(find.text('Shared'), findsOneWidget);
    expect(find.text('Mine'), findsOneWidget);
    expect(find.text('adult-01'), findsOneWidget);
  });

  testWidgets('assisted mode shows anchor picker and enforces max 3 anchors',
      (tester) async {
    await tester.pumpWidget(
      localizedTestApp(
        ListView(
          children: [
            CoordinationScreen(
              uid: 'user-123',
              anchorItemsStream: Stream.value(_readyItems(4)),
            ),
          ],
        ),
      ),
    );

    await tester.tap(find.text('Style & Shop'));
    await tester.pumpAndSettle();

    // Shared-closet selector is hidden in Assisted mode.
    expect(find.text('adult-01'), findsNothing);
    expect(find.text('Your clothes (up to 3)'), findsOneWidget);
    expect(find.byKey(const ValueKey('anchor-item-0')), findsOneWidget);

    for (var i = 0; i < 4; i++) {
      await tester.tap(find.byKey(ValueKey('anchor-item-$i')));
      await tester.pump();
    }

    // The 4th selection is rejected with a snackbar.
    expect(find.text('You can select up to 3 items.'), findsOneWidget);
    expect(find.byIcon(Icons.check_circle), findsNWidgets(3));
  });

  testWidgets('assisted mode shows a processing anchor as a loading tile',
      (tester) async {
    await tester.pumpWidget(
      localizedTestApp(
        ListView(
          children: [
            CoordinationScreen(
              uid: 'user-123',
              anchorItemsStream: Stream.value([
                ..._readyItems(1),
                ClosetItem(
                  id: 'item-new',
                  status: ItemStatus.processing,
                  category: 'top',
                ),
              ]),
            ),
          ],
        ),
      ),
    );

    await tester.tap(find.text('Style & Shop'));
    await tester.pump();
    await tester.pump();

    final processingTile = find.byKey(const ValueKey('anchor-item-new'));
    expect(processingTile, findsOneWidget);
    expect(
      find.descendant(
        of: processingTile,
        matching: find.byType(CircularProgressIndicator),
      ),
      findsWidgets,
    );

    // Tapping a processing tile must not select it.
    await tester.tap(processingTile);
    await tester.pump();
    expect(find.byIcon(Icons.check_circle), findsNothing);
  });

  testWidgets('assisted mode without ready items shows the empty hint',
      (tester) async {
    await tester.pumpWidget(
      localizedTestApp(
        ListView(
          children: [
            CoordinationScreen(
              uid: 'user-123',
              anchorItemsStream: Stream.value(const []),
            ),
          ],
        ),
      ),
    );

    await tester.tap(find.text('Style & Shop'));
    await tester.pumpAndSettle();

    expect(
      find.text('No ready closet items yet. Upload one to begin.'),
      findsOneWidget,
    );
  });

  testWidgets(
      'candidate panel marks recommended and anchor candidates', (tester) async {
    final candidates = [
      {'item_id': 'anchor-1', 'source': 'CLOSET', 'anchor': true},
      {
        'item_id': 'rakuten:1',
        'source': 'RAKUTEN',
        'name': 'White T-Shirt',
        'price': 2980,
        'external_url': 'https://item.rakuten.co.jp/shop/1001',
        'recommended': true,
      },
      {'item_id': 'rakuten:2', 'source': 'RAKUTEN', 'recommended': false},
    ];
    final selected = <String>{'anchor-1', 'rakuten:1'};

    await tester.pumpWidget(
      localizedTestApp(
        ListView(
          children: [
            CandidatePanel(
              candidates: candidates,
              selectedIds: selected,
              savedIds: const {},
              importingIds: const {},
              running: false,
              onChanged: (id, isSelected) {},
              onImport: (_) {},
              onGenerate: () {},
            ),
          ],
        ),
      ),
    );
    await tester.pump();

    final checkboxes = tester
        .widgetList<CheckboxListTile>(find.byType(CheckboxListTile))
        .toList();
    expect(checkboxes[0].value, isTrue);
    expect(checkboxes[1].value, isTrue);
    expect(checkboxes[2].value, isFalse);
    // Recommended label appears on the anchor and the recommended suggestion.
    expect(find.text('Recommended'), findsNWidgets(2));
  });

  testWidgets('rakuten card shows name, price, link, and import button state',
      (tester) async {
    final candidate = {
      'item_id': 'rakuten:1',
      'source': 'RAKUTEN',
      'name': 'White T-Shirt',
      'price': 2980,
      'external_url': 'https://item.rakuten.co.jp/shop/1001',
      'recommended': true,
    };

    await tester.pumpWidget(
      localizedTestApp(
        ListView(
          children: [
            CandidateCard(
              candidate: candidate,
              recommended: true,
              selected: true,
              onChanged: (_) {},
              onImport: () {},
            ),
          ],
        ),
      ),
    );
    await tester.pump();

    expect(find.text('White T-Shirt'), findsOneWidget);
    expect(find.text('¥2980'), findsOneWidget);
    expect(find.text('Rakuten'), findsOneWidget);
    expect(find.byIcon(Icons.open_in_new), findsOneWidget);
    expect(find.text('Add to closet'), findsOneWidget);

    // Saved state disables the import button and changes its label.
    await tester.pumpWidget(
      localizedTestApp(
        ListView(
          children: [
            CandidateCard(
              candidate: candidate,
              recommended: true,
              selected: true,
              saved: true,
              onChanged: (_) {},
              onImport: () {},
            ),
          ],
        ),
      ),
    );
    await tester.pump();

    expect(find.text('Saved as Interesting'), findsOneWidget);
    final button = tester.widget<OutlinedButton>(find.byType(OutlinedButton));
    expect(button.onPressed, isNull);
  });

  testWidgets('renders event accordion tile', (tester) async {
    await tester.pumpWidget(
      localizedTestApp(
        AgentEventTile(
          event: AgentEvent(
            seq: 1,
            agentName: 'ClosetAgent',
            eventKind: 'tool_call',
            toolName: 'search_closet',
            toolArgs: const {'source': 'SHARED_CLOSET'},
          ),
        ),
      ),
    );

    expect(find.text('ClosetAgent is searching the closet'), findsOneWidget);
  });

  testWidgets('search_rakuten call renders a Preview, not raw JSON',
      (tester) async {
    await tester.pumpWidget(
      localizedTestApp(
        AgentEventTile(
          event: AgentEvent(
            seq: 1,
            agentName: 'ClosetAgent',
            eventKind: 'tool_call',
            toolName: 'search_rakuten',
            toolArgs: const {
              'query': 'white t-shirt',
              'category': 'top',
              'colors': ['white'],
              'limit': 5,
            },
          ),
        ),
      ),
    );

    expect(find.text('ClosetAgent is searching Rakuten'), findsOneWidget);
    await tester.tap(find.text('ClosetAgent is searching Rakuten'));
    await tester.pumpAndSettle();

    expect(find.text('white t-shirt'), findsOneWidget);
    expect(find.text('top'), findsOneWidget);
    expect(find.text('white'), findsOneWidget);
    expect(find.textContaining('"query"'), findsNothing);
  });

  testWidgets('search_rakuten result renders item rows, not raw JSON',
      (tester) async {
    await tester.pumpWidget(
      localizedTestApp(
        AgentEventTile(
          event: AgentEvent(
            seq: 2,
            agentName: 'ClosetAgent',
            eventKind: 'tool_result',
            toolName: 'search_rakuten',
            toolResult: const {
              'result': [
                {
                  'item_id': 'rakuten:1',
                  'source': 'RAKUTEN',
                  'name': 'White T-Shirt',
                  'image_url': 'https://example.com/shirt.jpg',
                  'price': 2980,
                  'category': 'top',
                  'shop_name': 'Example Shop',
                  'tags': ['white'],
                },
              ],
            },
          ),
        ),
      ),
    );

    expect(
      find.text('ClosetAgent searched Rakuten - 1 candidates'),
      findsOneWidget,
    );
    await tester.tap(
      find.text('ClosetAgent searched Rakuten - 1 candidates'),
    );
    await tester.pumpAndSettle();

    expect(find.text('1 items found'), findsOneWidget);
    expect(find.text('White T-Shirt'), findsOneWidget);
    expect(find.text('¥2980'), findsOneWidget);
    expect(find.text('Shop: Example Shop'), findsOneWidget);
    expect(find.textContaining('"item_id"'), findsNothing);
  });

  test('AgentEvent parses backend payload', () {
    final event = AgentEvent.fromJson({
      'seq': 3,
      'agentName': 'StylingAgent',
      'eventKind': 'tool_result',
      'toolName': 'style_synthesizer',
      'toolResult': {'coordinateImageUrl': 'http://image'},
    });

    expect(event.seq, 3);
    expect(event.toolResult?['coordinateImageUrl'], 'http://image');
    expect(event.toJson()['toolName'], 'style_synthesizer');
  });

  testWidgets(
      'offers to save selected Rakuten items as Interesting after generation',
      (tester) async {
    final fakeApi = _FakeCoordinationApiClient(
      candidates: [
        {'item_id': 'closet-1', 'source': 'CLOSET'},
        {
          'item_id': 'rakuten:1',
          'source': 'RAKUTEN',
          'name': 'White T-Shirt',
          'price': 2980,
          'recommended': true,
        },
      ],
    );

    await tester.binding.setSurfaceSize(const Size(900, 2600));
    addTearDown(() => tester.binding.setSurfaceSize(null));

    await tester.pumpWidget(
      localizedTestApp(
        ListView(
          children: [CoordinationScreen(uid: 'user-1', api: fakeApi)],
        ),
      ),
    );

    await tester.tap(find.widgetWithText(FilledButton, 'Start'));
    await tester.pumpAndSettle();

    await tester.ensureVisible(find.text('Generate selected'));
    await tester.tap(find.text('Generate selected'));
    for (var i = 0; i < 10; i++) {
      await tester.pump(const Duration(milliseconds: 100));
    }

    expect(find.text('Save Rakuten items to your closet?'), findsOneWidget);
    expect(
      find.descendant(
        of: find.byType(AlertDialog),
        matching: find.text('White T-Shirt'),
      ),
      findsOneWidget,
    );

    await tester.tap(find.text('Save selected'));
    for (var i = 0; i < 10; i++) {
      await tester.pump(const Duration(milliseconds: 100));
    }

    expect(fakeApi.importedCandidateIds, ['rakuten:1']);
  });

  testWidgets('unchecking a Rakuten item in the dialog skips its import',
      (tester) async {
    final fakeApi = _FakeCoordinationApiClient(
      candidates: [
        {
          'item_id': 'rakuten:1',
          'source': 'RAKUTEN',
          'name': 'White T-Shirt',
          'recommended': true,
        },
      ],
    );

    await tester.binding.setSurfaceSize(const Size(900, 2600));
    addTearDown(() => tester.binding.setSurfaceSize(null));

    await tester.pumpWidget(
      localizedTestApp(
        ListView(
          children: [CoordinationScreen(uid: 'user-1', api: fakeApi)],
        ),
      ),
    );

    await tester.tap(find.widgetWithText(FilledButton, 'Start'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Generate selected'));
    for (var i = 0; i < 10; i++) {
      await tester.pump(const Duration(milliseconds: 100));
    }

    await tester.tap(
      find.descendant(
        of: find.byType(AlertDialog),
        matching: find.byType(CheckboxListTile),
      ),
    );
    await tester.pump();
    await tester.tap(find.text('Save selected'));
    for (var i = 0; i < 10; i++) {
      await tester.pump(const Duration(milliseconds: 100));
    }

    expect(fakeApi.importedCandidateIds, isEmpty);
  });

  testWidgets('closet-only generation never shows the save-Interesting modal',
      (tester) async {
    final fakeApi = _FakeCoordinationApiClient(
      candidates: [
        {'item_id': 'closet-1', 'source': 'CLOSET'},
      ],
    );

    await tester.binding.setSurfaceSize(const Size(900, 2600));
    addTearDown(() => tester.binding.setSurfaceSize(null));

    await tester.pumpWidget(
      localizedTestApp(
        ListView(
          children: [CoordinationScreen(uid: 'user-1', api: fakeApi)],
        ),
      ),
    );

    await tester.tap(find.widgetWithText(FilledButton, 'Start'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Generate selected'));
    for (var i = 0; i < 10; i++) {
      await tester.pump(const Duration(milliseconds: 100));
    }

    expect(find.text('Save Rakuten items to your closet?'), findsNothing);
  });
}
