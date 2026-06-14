import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gen_fashion_web/main.dart' as app;
import 'package:integration_test/integration_test.dart';

Future<void> _pumpUntil(
  WidgetTester tester,
  bool Function() condition, {
  Duration timeout = const Duration(seconds: 180),
}) async {
  final end = DateTime.now().add(timeout);
  while (DateTime.now().isBefore(end)) {
    await tester.pump(const Duration(milliseconds: 500));
    if (condition()) return;
  }
  throw TimeoutException('Condition was not met within $timeout');
}

class TimeoutException implements Exception {
  TimeoutException(this.message);
  final String message;

  @override
  String toString() => message;
}

void main() {
  IntegrationTestWidgetsFlutterBinding.ensureInitialized();

  testWidgets('M5 shared closet coordination renders live trace and result',
      (tester) async {
    app.main();
    await tester.pumpAndSettle(const Duration(seconds: 1));

    await _pumpUntil(
      tester,
      () => find.text('Coordinate').evaluate().isNotEmpty,
      timeout: const Duration(seconds: 30),
    );
    await tester.tap(find.text('Coordinate'));
    await tester.pumpAndSettle();

    expect(find.text('Coordination'), findsOneWidget);
    expect(find.text('Shared'), findsOneWidget);
    expect(find.text('adult-01'), findsOneWidget);

    await tester.tap(find.text('Start'));
    await tester.pump();

    await _pumpUntil(
      tester,
      () => find.text('COMPLETED').evaluate().isNotEmpty,
    );

    expect(find.text('Agent trace'), findsOneWidget);
    expect(find.text('Result'), findsOneWidget);
    expect(find.textContaining('tool_call'), findsAtLeastNWidgets(1));
    expect(find.textContaining('tool_result'), findsAtLeastNWidgets(1));
    expect(find.textContaining('search_closet'), findsAtLeastNWidgets(1));
    expect(find.textContaining('style_synthesizer'), findsAtLeastNWidgets(1));
    expect(find.byType(Image), findsAtLeastNWidgets(1));
  });
}
