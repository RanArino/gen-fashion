import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gen_fashion_web/coordination/coordination_screen.dart';

void main() {
  testWidgets('renders coordination controls and event accordion',
      (tester) async {
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: ListView(
            children: const [CoordinationScreen(uid: 'user-123')],
          ),
        ),
      ),
    );

    expect(find.text('Coordination'), findsOneWidget);
    expect(find.text('Shared'), findsOneWidget);
    expect(find.text('Mine'), findsOneWidget);
    expect(find.text('adult-01'), findsOneWidget);
  });

  testWidgets('renders event accordion tile', (tester) async {
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: AgentEventTile(
            event: AgentEvent(
              seq: 1,
              agentName: 'ClosetAgent',
              eventKind: 'tool_call',
              toolName: 'search_closet',
              toolArgs: const {'source': 'SHARED_CLOSET'},
            ),
          ),
        ),
      ),
    );

    expect(find.text('ClosetAgent is searching the closet'), findsOneWidget);
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
    expect(event.detailText, contains('style_synthesizer'));
  });
}
