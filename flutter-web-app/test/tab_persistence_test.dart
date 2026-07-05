import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gen_fashion_web/api/api_client.dart';
import 'package:gen_fashion_web/coordination/coordination_screen.dart';
import 'package:gen_fashion_web/history/history_item.dart';

import 'test_app.dart';

/// Minimal fake proving only that `CoordinationScreen`'s propose-phase state
/// (trace event + proposed candidate) survives being hidden and re-shown.
class _FakeApiClient extends ApiClient {
  @override
  Future<StyleSessionResponse> createSession() async => const StyleSessionResponse(
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
  Stream<SseMessage> streamSessionEvents(String sessionId) async* {
    yield const SseMessage(
      event: 'agent.event',
      data: {
        'seq': 1,
        'agentName': 'ClosetAgent',
        'eventKind': 'tool_call',
        'toolName': 'search_closet',
      },
    );
    yield const SseMessage(
      event: 'session.proposed',
      data: {
        'candidates': [
          {'item_id': 'closet-1', 'source': 'CLOSET'},
        ],
      },
    );
  }

  @override
  Future<SessionHistoryItem> getSession(String sessionId) async {
    return SessionHistoryItem(
      sessionId: sessionId,
      status: 'PROPOSING',
      selectedItems: const [],
      proposedCandidates: const [
        {'item_id': 'closet-1', 'source': 'CLOSET'},
      ],
    );
  }
}

void main() {
  testWidgets(
      'CoordinationScreen state survives being hidden behind an IndexedStack '
      'and shown again, proving tab switches no longer dispose it',
      (tester) async {
    final fakeApi = _FakeApiClient();
    var index = 0;

    await tester.binding.setSurfaceSize(const Size(900, 2600));
    addTearDown(() => tester.binding.setSurfaceSize(null));

    await tester.pumpWidget(
      localizedTestApp(
        StatefulBuilder(
          builder: (context, setState) => Column(
            children: [
              TextButton(
                onPressed: () => setState(() => index = index == 0 ? 1 : 0),
                child: const Text('switch tab'),
              ),
              Expanded(
                child: IndexedStack(
                  index: index,
                  children: [
                    CoordinationScreen(uid: 'user-1', api: fakeApi),
                    const Placeholder(),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );

    await tester.tap(find.widgetWithText(FilledButton, 'Start'));
    await tester.pumpAndSettle();

    expect(find.text('ClosetAgent is searching the closet'), findsOneWidget);
    expect(find.byType(CheckboxListTile), findsOneWidget);

    // Simulate switching to another tab, then back.
    await tester.tap(find.text('switch tab'));
    await tester.pump();
    expect(find.byType(CoordinationScreen), findsNothing);

    await tester.tap(find.text('switch tab'));
    await tester.pump();

    // Still there, unchanged: the widget's State was never disposed, so no
    // re-fetch/reset happened.
    expect(find.text('ClosetAgent is searching the closet'), findsOneWidget);
    expect(find.byType(CheckboxListTile), findsOneWidget);
  });
}
