import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:friday_desktop/widgets/holographic_orb.dart';

void main() {
  testWidgets('renders an animated idle assistant core', (tester) async {
    await tester.pumpWidget(const MaterialApp(
      home: Scaffold(body: Center(child: HolographicOrb(mode: 'idle', size: 220))),
    ));
    expect(find.byType(HolographicOrb), findsOneWidget);
    await tester.pump(const Duration(milliseconds: 120));
    expect(tester.takeException(), isNull);
    await tester.pumpWidget(const SizedBox.shrink());
  });

  testWidgets('renders active listening and speaking modes', (tester) async {
    await tester.pumpWidget(const MaterialApp(
      home: Scaffold(body: Center(child: HolographicOrb(mode: 'listening', size: 240))),
    ));
    await tester.pump(const Duration(milliseconds: 100));
    await tester.pumpWidget(const MaterialApp(
      home: Scaffold(body: Center(child: HolographicOrb(mode: 'speaking', size: 240))),
    ));
    await tester.pump(const Duration(milliseconds: 100));
    expect(tester.takeException(), isNull);
  });
}
