import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gen_fashion_web/api/api_client.dart';
import 'package:gen_fashion_web/closet/closet_item.dart';
import 'package:gen_fashion_web/closet/upload_service.dart';
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
  Map<String, String>? selectedSourcePreference;
  Map<String, String>? assistedPreference;
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
    selectedSourcePreference = userPreference;
    return const StyleSessionResponse(
      sessionId: 'session-1',
      status: 'PROPOSING',
      source: 'SHARED_CLOSET',
    );
  }

  @override
  Future<StyleSessionResponse> assistSession({
    required String sessionId,
    required List<String> anchorItemIds,
    required Map<String, String> userPreference,
  }) async {
    assistedPreference = userPreference;
    return const StyleSessionResponse(
      sessionId: 'session-1',
      status: 'PROPOSING',
      source: 'CLOSET',
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

/// Fake backend for exercising the terminal-callback + bounded recovery poll
/// (MP-2/MP-3): the propose-phase stream/session stay PROPOSING (no polling
/// needed there, matching production), but once candidates are selected the
/// generate-phase stream ends without a terminal status, forcing the poll
/// loop in `_recoverSessionState` to do the work: `getSession` reports
/// GENERATING once, then COMPLETED.
class _PollingFakeApiClient extends ApiClient {
  bool _selected = false;
  int _pollCallsAfterSelect = 0;

  static const _coordinateImageUrl = 'https://example.com/coordinate.jpg';

  @override
  Future<StyleSessionResponse> createSession() async =>
      const StyleSessionResponse(
        sessionId: 'session-1',
        status: 'PROPOSING',
        source: 'SHARED_CLOSET',
      );

  @override
  Future<StyleSessionResponse> selectSource({
    required String sessionId,
    required String source,
    required Map<String, String> userPreference,
    String? sharedClosetId,
  }) async =>
      const StyleSessionResponse(
        sessionId: 'session-1',
        status: 'PROPOSING',
        source: 'SHARED_CLOSET',
      );

  @override
  Future<StyleSessionResponse> selectCandidates({
    required String sessionId,
    required List<String> selectedItemIds,
  }) async {
    _selected = true;
    return const StyleSessionResponse(
      sessionId: 'session-1',
      status: 'GENERATING',
      source: 'SHARED_CLOSET',
    );
  }

  @override
  Stream<SseMessage> streamSessionEvents(String sessionId) async* {
    if (!_selected) {
      yield const SseMessage(
        event: 'session.proposed',
        data: {
          'candidates': [
            {'item_id': 'closet-1', 'source': 'CLOSET'},
          ],
        },
      );
    }
    // The generate-phase stream (after selection) ends here without a
    // terminal event, simulating the SSE stream's own 150s cap closing
    // before the backend actually finishes.
  }

  @override
  Future<SessionHistoryItem> getSession(String sessionId) async {
    if (!_selected) {
      return SessionHistoryItem(
        sessionId: sessionId,
        status: 'PROPOSING',
        selectedItems: const [],
        proposedCandidates: const [],
      );
    }
    _pollCallsAfterSelect += 1;
    final completed = _pollCallsAfterSelect >= 2;
    return SessionHistoryItem(
      sessionId: sessionId,
      status: completed ? 'COMPLETED' : 'GENERATING',
      selectedItems: const [],
      proposedCandidates: const [],
      coordinateImageUrl: completed ? _coordinateImageUrl : null,
    );
  }
}

/// Same shape, but `getSession` never resolves past GENERATING, exercising
/// the poll loop's bounded give-up path.
class _NeverCompletingFakeApiClient extends ApiClient {
  bool _selected = false;

  @override
  Future<StyleSessionResponse> createSession() async =>
      const StyleSessionResponse(
        sessionId: 'session-1',
        status: 'PROPOSING',
        source: 'SHARED_CLOSET',
      );

  @override
  Future<StyleSessionResponse> selectSource({
    required String sessionId,
    required String source,
    required Map<String, String> userPreference,
    String? sharedClosetId,
  }) async =>
      const StyleSessionResponse(
        sessionId: 'session-1',
        status: 'PROPOSING',
        source: 'SHARED_CLOSET',
      );

  @override
  Future<StyleSessionResponse> selectCandidates({
    required String sessionId,
    required List<String> selectedItemIds,
  }) async {
    _selected = true;
    return const StyleSessionResponse(
      sessionId: 'session-1',
      status: 'GENERATING',
      source: 'SHARED_CLOSET',
    );
  }

  @override
  Stream<SseMessage> streamSessionEvents(String sessionId) async* {
    if (!_selected) {
      yield const SseMessage(
        event: 'session.proposed',
        data: {
          'candidates': [
            {'item_id': 'closet-1', 'source': 'CLOSET'},
          ],
        },
      );
    }
  }

  @override
  Future<SessionHistoryItem> getSession(String sessionId) async {
    return SessionHistoryItem(
      sessionId: sessionId,
      status: _selected ? 'GENERATING' : 'PROPOSING',
      selectedItems: const [],
      proposedCandidates: const [],
    );
  }
}

class _FakeUploadService extends UploadService {
  _FakeUploadService(this.itemId) : super(api: ApiClient());

  final String itemId;

  @override
  Future<String?> upload() async => itemId;
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

  testWidgets('renders Japanese preference defaults as multi-select chips',
      (tester) async {
    await tester.pumpWidget(
      localizedTestApp(
        ListView(
          children: const [CoordinationScreen(uid: 'user-123')],
        ),
        locale: const Locale('ja'),
      ),
    );

    expect(find.text('コーディネート'), findsOneWidget);
    expect(find.text('カジュアルな週末'), findsOneWidget);
    expect(find.text('きれいめカジュアル'), findsOneWidget);
    expect(find.text('春'), findsOneWidget);
    expect(
      tester
          .widget<FilterChip>(find.byKey(const ValueKey('color-blue')))
          .selected,
      isTrue,
    );
    expect(
      tester
          .widget<FilterChip>(find.byKey(const ValueKey('color-white')))
          .selected,
      isTrue,
    );
  });

  testWidgets('renders English preference defaults as multi-select chips',
      (tester) async {
    await tester.pumpWidget(
      localizedTestApp(
        ListView(
          children: const [CoordinationScreen(uid: 'user-123')],
        ),
        locale: const Locale('en'),
      ),
    );

    expect(find.text('Coordination'), findsOneWidget);
    expect(find.text('casual weekend'), findsOneWidget);
    expect(find.text('clean casual'), findsOneWidget);
    expect(find.text('spring'), findsOneWidget);
    expect(
      tester
          .widget<FilterChip>(find.byKey(const ValueKey('color-blue')))
          .selected,
      isTrue,
    );
    expect(
      tester
          .widget<FilterChip>(find.byKey(const ValueKey('color-white')))
          .selected,
      isTrue,
    );
  });

  testWidgets('sends multi-select preferences as comma-separated strings',
      (tester) async {
    final fakeApi = _FakeCoordinationApiClient(candidates: const []);
    await tester.binding.setSurfaceSize(const Size(900, 2600));
    addTearDown(() => tester.binding.setSurfaceSize(null));

    await tester.pumpWidget(
      localizedTestApp(
        ListView(
          children: [CoordinationScreen(uid: 'user-123', api: fakeApi)],
        ),
        locale: const Locale('en'),
      ),
    );

    await tester.tap(find.byKey(const ValueKey('occasion-work')));
    await tester.tap(find.byKey(const ValueKey('style-minimal')));
    await tester.tap(find.byKey(const ValueKey('season-summer')));
    await tester.tap(find.byKey(const ValueKey('color-black')));
    await tester.pump();

    await tester.tap(find.widgetWithText(FilledButton, 'Start'));
    await tester.pumpAndSettle();

    expect(fakeApi.selectedSourcePreference, isNotNull);
    expect(
      fakeApi.selectedSourcePreference,
      containsPair('occasion', 'casual weekend, work'),
    );
    expect(
      fakeApi.selectedSourcePreference,
      containsPair('style', 'clean casual, minimal'),
    );
    expect(
      fakeApi.selectedSourcePreference,
      containsPair('season', 'spring, summer'),
    );
    expect(
      fakeApi.selectedSourcePreference,
      containsPair('colorPreference', 'blue, white, black'),
    );
    expect(fakeApi.selectedSourcePreference, containsPair('gender', 'common'));
    expect(fakeApi.selectedSourcePreference, containsPair('language', 'en'));
  });

  testWidgets('includes Other free text in preference payload', (tester) async {
    final fakeApi = _FakeCoordinationApiClient(candidates: const []);
    await tester.binding.setSurfaceSize(const Size(900, 2600));
    addTearDown(() => tester.binding.setSurfaceSize(null));

    await tester.pumpWidget(
      localizedTestApp(
        ListView(
          children: [CoordinationScreen(uid: 'user-123', api: fakeApi)],
        ),
        locale: const Locale('ja'),
      ),
    );

    await tester.tap(find.byKey(const ValueKey('style-other')));
    await tester.pump();
    await tester.enterText(
      find.byKey(const ValueKey('style-other-input')),
      'モード系',
    );

    await tester.tap(find.widgetWithText(FilledButton, '開始'));
    await tester.pumpAndSettle();

    expect(fakeApi.selectedSourcePreference, isNotNull);
    expect(
      fakeApi.selectedSourcePreference,
      containsPair('style', 'きれいめカジュアル, モード系'),
    );
    expect(fakeApi.selectedSourcePreference, containsPair('language', 'ja'));
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

  testWidgets('assisted mode selects an uploaded anchor once it is ready',
      (tester) async {
    final stream = StreamController<List<ClosetItem>>();
    addTearDown(stream.close);

    await tester.pumpWidget(
      localizedTestApp(
        ListView(
          children: [
            CoordinationScreen(
              uid: 'user-123',
              uploads: _FakeUploadService('item-new'),
              anchorItemsStream: stream.stream,
            ),
          ],
        ),
      ),
    );

    stream.add(const []);
    await tester.tap(find.text('Style & Shop'));
    await tester.pump();
    await tester.pump();

    await tester.tap(find.widgetWithText(TextButton, 'Add item'));
    await tester.pump();
    stream.add([
      ClosetItem(
        id: 'item-new',
        status: ItemStatus.processing,
        category: 'top',
      ),
    ]);
    await tester.pump();
    expect(find.byIcon(Icons.check_circle), findsNothing);

    stream.add([
      ClosetItem(
        id: 'item-new',
        status: ItemStatus.ready,
        category: 'top',
      ),
    ]);
    await tester.pump();
    await tester.pump();

    expect(find.byKey(const ValueKey('anchor-item-new')), findsOneWidget);
    expect(find.byIcon(Icons.check_circle), findsOneWidget);
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

  testWidgets('candidate panel marks recommended and anchor candidates',
      (tester) async {
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

  testWidgets('candidate panel disables generation outside proposing state',
      (tester) async {
    var generated = false;

    await tester.pumpWidget(
      localizedTestApp(
        ListView(
          children: [
            CandidatePanel(
              candidates: const [
                {'item_id': 'rakuten:1', 'source': 'RAKUTEN'},
              ],
              selectedIds: const {'rakuten:1'},
              savedIds: const {},
              importingIds: const {},
              running: false,
              canGenerate: false,
              onChanged: (id, isSelected) {},
              onGenerate: () => generated = true,
            ),
          ],
        ),
      ),
    );

    final button = tester.widget<FilledButton>(
      find.widgetWithText(FilledButton, 'Generate selected'),
    );
    expect(button.onPressed, isNull);

    await tester.tap(find.widgetWithText(FilledButton, 'Generate selected'));
    await tester.pump();

    expect(generated, isFalse);
  });

  testWidgets('default selection keeps recommended items balanced by category',
      (tester) async {
    final fakeApi = _FakeCoordinationApiClient(
      candidates: [
        {
          'item_id': 'anchor-top',
          'source': 'CLOSET',
          'category': 'top',
          'anchor': true,
          'recommended': true,
        },
        {
          'item_id': 'rakuten:pants-1',
          'source': 'RAKUTEN',
          'name': 'Beige pants',
          'category': 'bottom',
          'recommended': true,
        },
        {
          'item_id': 'rakuten:pants-2',
          'source': 'RAKUTEN',
          'name': 'Grey slacks',
          'category': 'bottom',
          'recommended': true,
        },
        {
          'item_id': 'rakuten:pants-3',
          'source': 'RAKUTEN',
          'name': 'Black jeans',
          'category': 'bottom',
          'recommended': true,
        },
        {
          'item_id': 'rakuten:shoes-1',
          'source': 'RAKUTEN',
          'name': 'White sneakers',
          'category': 'shoes',
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

    final checkboxes = tester
        .widgetList<CheckboxListTile>(find.byType(CheckboxListTile))
        .toList();
    expect(
      checkboxes.map((checkbox) => checkbox.value).toList(),
      [true, true, false, false, true],
    );
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
              'limit': 1,
              'requestedLimit': 1,
              'effectiveLimit': 5,
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
    expect(find.text('1 -> 5'), findsOneWidget);
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

    await tester.ensureVisible(find.widgetWithText(FilledButton, 'Start'));
    await tester.ensureVisible(find.widgetWithText(FilledButton, 'Start'));
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

  testWidgets('onSessionTerminal does not fire while only PROPOSING',
      (tester) async {
    final fakeApi = _FakeCoordinationApiClient(
      candidates: [
        {'item_id': 'closet-1', 'source': 'CLOSET'},
      ],
    );
    final calls = <(String, String)>[];

    await tester.binding.setSurfaceSize(const Size(900, 2600));
    addTearDown(() => tester.binding.setSurfaceSize(null));

    await tester.pumpWidget(
      localizedTestApp(
        ListView(
          children: [
            CoordinationScreen(
              uid: 'user-1',
              api: fakeApi,
              onSessionTerminal: (id, status) => calls.add((id, status)),
            ),
          ],
        ),
      ),
    );

    await tester.ensureVisible(find.widgetWithText(FilledButton, 'Start'));
    await tester.tap(find.widgetWithText(FilledButton, 'Start'));
    await tester.pumpAndSettle();

    expect(calls, isEmpty);
  });

  testWidgets(
      'onSessionTerminal fires exactly once with COMPLETED after Start -> Generate',
      (tester) async {
    final fakeApi = _FakeCoordinationApiClient(
      candidates: [
        {'item_id': 'closet-1', 'source': 'CLOSET'},
      ],
    );
    final calls = <(String, String)>[];

    await tester.binding.setSurfaceSize(const Size(900, 2600));
    addTearDown(() => tester.binding.setSurfaceSize(null));

    await tester.pumpWidget(
      localizedTestApp(
        ListView(
          children: [
            CoordinationScreen(
              uid: 'user-1',
              api: fakeApi,
              onSessionTerminal: (id, status) => calls.add((id, status)),
            ),
          ],
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

    expect(calls, [('session-1', 'COMPLETED')]);
  });

  testWidgets('completed session can be cleared to start a new coordinate',
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
    await tester.ensureVisible(find.text('Generate selected'));
    await tester.tap(find.text('Generate selected'));
    for (var i = 0; i < 10; i++) {
      await tester.pump(const Duration(milliseconds: 100));
    }

    expect(find.text('Your coordinate is complete'), findsOneWidget);
    expect(find.text('Start a new coordinate'), findsOneWidget);
    expect(find.text('COMPLETED'), findsOneWidget);

    await tester.tap(find.text('Start a new coordinate'));
    await tester.pumpAndSettle();

    expect(find.text('Your coordinate is complete'), findsNothing);
    expect(find.text('Start a new coordinate'), findsNothing);
    expect(find.text('COMPLETED'), findsNothing);
    expect(find.text('Generate selected'), findsNothing);
    expect(find.text('Coordinate image will appear here.'), findsOneWidget);
    expect(find.widgetWithText(FilledButton, 'Start'), findsOneWidget);
  });

  testWidgets(
      'bounded recovery poll advances GENERATING -> COMPLETED and notifies once',
      (tester) async {
    final fakeApi = _PollingFakeApiClient();
    final calls = <(String, String)>[];

    await tester.binding.setSurfaceSize(const Size(900, 2600));
    addTearDown(() => tester.binding.setSurfaceSize(null));

    await tester.pumpWidget(
      localizedTestApp(
        ListView(
          children: [
            CoordinationScreen(
              uid: 'user-1',
              api: fakeApi,
              onSessionTerminal: (id, status) => calls.add((id, status)),
              recoveryPollInterval: const Duration(milliseconds: 10),
              recoveryPollMaxWait: const Duration(seconds: 5),
            ),
          ],
        ),
      ),
    );

    await tester.tap(find.widgetWithText(FilledButton, 'Start'));
    await tester.pumpAndSettle();

    expect(calls, isEmpty);

    await tester.ensureVisible(find.text('Generate selected'));
    await tester.tap(find.text('Generate selected'));
    for (var i = 0; i < 10; i++) {
      await tester.pump(const Duration(milliseconds: 20));
    }

    expect(calls, [('session-1', 'COMPLETED')]);
    expect(find.text('COMPLETED'), findsOneWidget);
  });

  testWidgets('bounded recovery poll gives up after recoveryPollMaxWait',
      (tester) async {
    final fakeApi = _NeverCompletingFakeApiClient();
    final calls = <(String, String)>[];

    await tester.binding.setSurfaceSize(const Size(900, 2600));
    addTearDown(() => tester.binding.setSurfaceSize(null));

    await tester.pumpWidget(
      localizedTestApp(
        ListView(
          children: [
            CoordinationScreen(
              uid: 'user-1',
              api: fakeApi,
              onSessionTerminal: (id, status) => calls.add((id, status)),
              recoveryPollInterval: const Duration(milliseconds: 10),
              recoveryPollMaxWait: const Duration(milliseconds: 100),
            ),
          ],
        ),
      ),
    );

    await tester.tap(find.widgetWithText(FilledButton, 'Start'));
    await tester.pumpAndSettle();
    await tester.ensureVisible(find.text('Generate selected'));
    await tester.tap(find.text('Generate selected'));
    for (var i = 0; i < 20; i++) {
      await tester.pump(const Duration(milliseconds: 20));
    }

    expect(calls, isEmpty);
    expect(find.textContaining('Still generating'), findsOneWidget);
  });

  testWidgets(
      'save-Interesting dialog does not appear when recovery resolves non-COMPLETED',
      (tester) async {
    final fakeApi = _NeverCompletingFakeApiClient();

    await tester.binding.setSurfaceSize(const Size(900, 2600));
    addTearDown(() => tester.binding.setSurfaceSize(null));

    await tester.pumpWidget(
      localizedTestApp(
        ListView(
          children: [
            CoordinationScreen(
              uid: 'user-1',
              api: fakeApi,
              recoveryPollInterval: const Duration(milliseconds: 10),
              recoveryPollMaxWait: const Duration(milliseconds: 100),
            ),
          ],
        ),
      ),
    );

    await tester.tap(find.widgetWithText(FilledButton, 'Start'));
    await tester.pumpAndSettle();
    await tester.ensureVisible(find.text('Generate selected'));
    await tester.tap(find.text('Generate selected'));
    for (var i = 0; i < 20; i++) {
      await tester.pump(const Duration(milliseconds: 20));
    }

    expect(find.text('Save Rakuten items to your closet?'), findsNothing);
  });
}
