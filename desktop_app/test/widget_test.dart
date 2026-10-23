import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:friday_desktop/widgets/holographic_orb.dart';

void main() {
  testWidgets('FRIDAY holographic core renders as a native Flutter widget', (tester) async {
    await tester.pumpWidget(
      const MaterialApp(
        home: Scaffold(
          body: Center(child: HolographicOrb(mode: 'idle', size: 220)),
        ),
      ),
    );
    expect(find.byType(HolographicOrb), findsOneWidget);
    await tester.pump(const Duration(milliseconds: 150));
    expect(tester.takeException(), isNull);
    await tester.pumpWidget(const SizedBox.shrink());
  });
}
