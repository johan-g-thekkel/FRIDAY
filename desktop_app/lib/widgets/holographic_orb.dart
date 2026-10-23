import 'dart:math' as math;

import 'package:flutter/material.dart';

class HolographicOrb extends StatefulWidget {
  const HolographicOrb({
    super.key,
    required this.mode,
    this.size = 260,
    this.onTap,
  });

  final String mode;
  final double size;
  final VoidCallback? onTap;

  @override
  State<HolographicOrb> createState() => _HolographicOrbState();
}

class _HolographicOrbState extends State<HolographicOrb> with SingleTickerProviderStateMixin {
  late final AnimationController _controller = AnimationController(
    vsync: this,
    duration: const Duration(seconds: 9),
  )..repeat();

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final active = widget.mode == 'listening';
    final thinking = widget.mode == 'thinking';
    final speaking = widget.mode == 'speaking';
    final glow = active ? const Color(0xFF69E8F5) : thinking ? const Color(0xFFB29BFF) : const Color(0xFF8DB9FF);
    return GestureDetector(
      onTap: widget.onTap,
      child: AnimatedBuilder(
        animation: _controller,
        builder: (context, _) {
          return SizedBox(
            width: widget.size,
            height: widget.size,
            child: CustomPaint(
              painter: _OrbPainter(
                phase: _controller.value * math.pi * 2,
                glow: glow,
                listening: active,
                thinking: thinking,
                speaking: speaking,
              ),
              child: Center(
                child: Container(
                  width: widget.size * .48,
                  height: widget.size * .48,
                  decoration: BoxDecoration(
                    shape: BoxShape.circle,
                    gradient: RadialGradient(
                      colors: [
                        const Color(0xFF7FEFFF).withValues(alpha: .30),
                        const Color(0xFF706BFF).withValues(alpha: .16),
                        const Color(0xFF0B1227).withValues(alpha: .20),
                      ],
                    ),
                    border: Border.all(color: glow.withValues(alpha: .7), width: 1.1),
                    boxShadow: [
                      BoxShadow(color: glow.withValues(alpha: active ? .35 : .19), blurRadius: active ? 56 : 34, spreadRadius: active ? 8 : 2),
                    ],
                  ),
                  child: CustomPaint(painter: _FacePainter(color: glow, speaking: speaking, phase: _controller.value * math.pi * 2)),
                ),
              ),
            ),
          );
        },
      ),
    );
  }
}

class _OrbPainter extends CustomPainter {
  _OrbPainter({required this.phase, required this.glow, required this.listening, required this.thinking, required this.speaking});
  final double phase;
  final Color glow;
  final bool listening;
  final bool thinking;
  final bool speaking;

  @override
  void paint(Canvas canvas, Size size) {
    final center = Offset(size.width / 2, size.height / 2);
    final radius = size.shortestSide * .39;
    final pulse = listening ? (math.sin(phase * 2) + 1) * .06 : (math.sin(phase) + 1) * .025;
    final faint = Paint()..color = glow.withValues(alpha: .08)..style = PaintingStyle.stroke..strokeWidth = 1;
    canvas.drawCircle(center, radius * (1 + pulse), faint);
    for (var i = 0; i < 3; i++) {
      final angle = phase * (i.isEven ? 1 : -0.7) + i * math.pi / 3;
      final rect = Rect.fromCenter(center: center, width: radius * (1.35 + i * .13), height: radius * (.42 + i * .07));
      canvas.save();
      canvas.translate(center.dx, center.dy);
      canvas.rotate(angle * .2);
      canvas.translate(-center.dx, -center.dy);
      canvas.drawOval(rect, Paint()..color = glow.withValues(alpha: .14 + i * .02)..style = PaintingStyle.stroke..strokeWidth = 1);
      final dotAngle = angle + phase * .25;
      final dot = Offset(center.dx + math.cos(dotAngle) * rect.width * .5, center.dy + math.sin(dotAngle) * rect.height * .5);
      canvas.drawCircle(dot, i == 0 ? 3 : 2, Paint()..color = glow.withValues(alpha: .9));
      canvas.restore();
    }
    if (thinking) {
      for (var i = 0; i < 5; i++) {
        final a = phase * 1.6 + i * math.pi * 2 / 5;
        final p = Offset(center.dx + math.cos(a) * radius * .72, center.dy + math.sin(a) * radius * .72);
        canvas.drawCircle(p, 2.5, Paint()..color = const Color(0xFFC6B6FF).withValues(alpha: .85));
      }
    }
  }

  @override
  bool shouldRepaint(covariant _OrbPainter oldDelegate) =>
      oldDelegate.phase != phase || oldDelegate.glow != glow || oldDelegate.listening != listening || oldDelegate.thinking != thinking || oldDelegate.speaking != speaking;
}

class _FacePainter extends CustomPainter {
  _FacePainter({required this.color, required this.speaking, required this.phase});
  final Color color;
  final bool speaking;
  final double phase;

  @override
  void paint(Canvas canvas, Size size) {
    final w = size.width, h = size.height;
    final stroke = Paint()..color = color..style = PaintingStyle.stroke..strokeWidth = 1.8..strokeCap = StrokeCap.round;
    final fill = Paint()..shader = const LinearGradient(colors: [Color(0xFF8CE9FF), Color(0xFFAFA4FF)]).createShader(Offset.zero & size);
    final path = Path()
      ..moveTo(w * .20, h * .24)
      ..quadraticBezierTo(w * .5, h * .02, w * .80, h * .24)
      ..lineTo(w * .84, h * .56)
      ..quadraticBezierTo(w * .78, h * .91, w * .5, h * .92)
      ..quadraticBezierTo(w * .22, h * .91, w * .16, h * .56)
      ..close();
    canvas.drawPath(path, Paint()..shader = const RadialGradient(colors: [Color(0xFF253E68), Color(0xFF0A1328)]).createShader(Offset.zero & size));
    canvas.drawPath(path, stroke);
    for (final x in [.33, .67]) {
      final eye = Path()
        ..moveTo(w * (x - .09), h * .47)
        ..quadraticBezierTo(w * x, h * .42, w * (x + .09), h * .47);
      canvas.drawPath(eye, Paint()..color = const Color(0xFFB8F9FF)..style = PaintingStyle.stroke..strokeWidth = 2.8..strokeCap = StrokeCap.round);
      canvas.drawCircle(Offset(w * x, h * .47), 1.8, fill);
    }
    final nose = Path()..moveTo(w * .5, h * .49)..lineTo(w * .47, h * .64)..lineTo(w * .53, h * .66);
    canvas.drawPath(nose, stroke);
    final mouth = Path()..moveTo(w * .37, h * .76);
    if (speaking) {
      mouth.quadraticBezierTo(w * .5, h * (.79 + .04 * math.sin(DateTime.now().millisecondsSinceEpoch / 90)), w * .63, h * .76);
      canvas.drawOval(Rect.fromCenter(center: Offset(w * .5, h * .76), width: w * .23, height: h * (.025 + ((math.sin(phase * 8) + 1) / 2) * .07)), Paint()..color = color.withValues(alpha: .75));
    } else {
      mouth.quadraticBezierTo(w * .5, h * .81, w * .63, h * .76);
      canvas.drawPath(mouth, Paint()..color = const Color(0xFFD4B9FF)..style = PaintingStyle.stroke..strokeWidth = 2.3..strokeCap = StrokeCap.round);
    }
  }

  @override
  bool shouldRepaint(covariant _FacePainter oldDelegate) => oldDelegate.color != color || oldDelegate.speaking != speaking || oldDelegate.phase != phase;
}
