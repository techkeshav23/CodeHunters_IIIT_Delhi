import 'dart:math' as math;

import 'package:flutter/material.dart';

import '../util.dart';
import '../models.dart';
import '../theme.dart';

/// The compass dial: one needle, three bands (in a few days / today / now).
/// The needle swings in from the left once when a decision arrives, with a
/// small overshoot, then the active band settles thicker. Geometry follows
/// web/src/ui/Dial.tsx (220 x 150 viewBox).
class Dial extends StatefulWidget {
  const Dial({super.key, required this.level, required this.lang, this.animate = true});
  final int level; // 0 routine, 1 same_day, 2 immediate
  final Lang lang;
  final bool animate;

  @override
  State<Dial> createState() => _DialState();
}

class _DialState extends State<Dial> with SingleTickerProviderStateMixin {
  static const _angles = [-60.0, 0.0, 60.0];
  late final AnimationController _c;
  late Animation<double> _needle;
  late Animation<double> _band;

  @override
  void initState() {
    super.initState();
    _c = AnimationController(vsync: this, duration: const Duration(milliseconds: 1100));
    _setup(-90);
    if (widget.animate) {
      _c.forward();
    } else {
      _c.value = 1;
    }
  }

  void _setup(double from) {
    _needle = Tween(begin: from, end: _angles[widget.level]).animate(
      CurvedAnimation(
        parent: _c,
        curve: const Interval(0, 0.82, curve: Cubic(0.2, 0.9, 0.2, 1.15)),
      ),
    );
    _band = CurvedAnimation(
      parent: _c,
      curve: const Interval(0.45, 1, curve: Curves.easeOutCubic),
    );
  }

  @override
  void didUpdateWidget(Dial old) {
    super.didUpdateWidget(old);
    if (old.level != widget.level) {
      _setup(_needle.value);
      _c.forward(from: 0);
    }
  }

  @override
  void dispose() {
    _c.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final cc = CC.of(context);
    final labels = [for (var i = 0; i < 3; i++) urgencyText(i, widget.lang)];
    return Semantics(
      label: labels[widget.level],
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 210),
        child: AspectRatio(
          aspectRatio: 220 / 150,
          child: AnimatedBuilder(
            animation: _c,
            builder: (context, _) => CustomPaint(
              painter: _DialPainter(
                level: widget.level,
                angle: _needle.value,
                bandT: _band.value,
                labels: labels,
                bands: [cc.brand, cc.haldi, cc.sindoor],
                ink: cc.ink,
                ink2: cc.ink2,
                ink3: cc.ink3,
                surface: cc.surface,
                haldi: cc.haldi,
              ),
            ),
          ),
        ),
      ),
    );
  }
}

class _DialPainter extends CustomPainter {
  _DialPainter({
    required this.level,
    required this.angle,
    required this.bandT,
    required this.labels,
    required this.bands,
    required this.ink,
    required this.ink2,
    required this.ink3,
    required this.surface,
    required this.haldi,
  });

  final int level;
  final double angle;
  final double bandT;
  final List<String> labels;
  final List<Color> bands;
  final Color ink, ink2, ink3, surface, haldi;

  static const cx = 110.0, cy = 112.0, r = 86.0;
  static const _bandRanges = [(178.0, 122.0), (118.0, 62.0), (58.0, 2.0)];

  Offset pt(double deg, [double rad = r]) {
    final a = deg * math.pi / 180;
    return Offset(cx + rad * math.cos(a), cy - rad * math.sin(a));
  }

  @override
  void paint(Canvas canvas, Size size) {
    canvas.save();
    canvas.scale(size.width / 220);

    // bands
    final rect = Rect.fromCircle(center: const Offset(cx, cy), radius: r);
    for (var i = 0; i < 3; i++) {
      final (from, to) = _bandRanges[i];
      final active = i == level;
      final width = active ? 10 + 6 * bandT : 10.0;
      final opacity = active ? 0.28 + 0.72 * bandT : 0.28;
      final p = Paint()
        ..style = PaintingStyle.stroke
        ..strokeCap = StrokeCap.round
        ..strokeWidth = width
        ..color = bands[i].withValues(alpha: opacity);
      canvas.drawArc(rect, -from * math.pi / 180, (from - to) * math.pi / 180, false, p);
    }

    // ticks
    final tick = Paint()
      ..strokeWidth = 1.5
      ..color = ink3.withValues(alpha: 0.5);
    for (var i = 0; i < 13; i++) {
      final d = 180.0 - i * 15;
      canvas.drawLine(pt(d, r - 18), pt(d, r - (i.isOdd ? 22 : 26)), tick);
    }

    // needle (drawn pointing up, rotated clockwise by `angle` degrees)
    canvas.save();
    canvas.translate(cx, cy);
    canvas.rotate(angle * math.pi / 180);
    final shadow = Path()
      ..moveTo(0, -70)
      ..lineTo(7, 0)
      ..lineTo(-7, 0)
      ..close();
    canvas.drawShadow(shadow, Colors.black, 2.5, false);
    canvas.drawPath(shadow, Paint()..color = ink);
    final tip = Path()
      ..moveTo(0, -70)
      ..lineTo(4, -40)
      ..lineTo(-4, -40)
      ..close();
    canvas.drawPath(tip, Paint()..color = haldi);
    canvas.restore();

    // hub
    canvas.drawCircle(const Offset(cx, cy), 10, Paint()..color = surface);
    canvas.drawCircle(
      const Offset(cx, cy),
      10,
      Paint()
        ..style = PaintingStyle.stroke
        ..strokeWidth = 3
        ..color = ink,
    );

    // labels
    void label(String s, Offset at, TextAlign align, bool active, Color activeColor) {
      final tp = TextPainter(
        text: TextSpan(
          text: s,
          style: TextStyle(
            fontFamily: fBody,
            fontFamilyFallback: fBodyFallback,
            fontSize: 13.5,
            fontWeight: FontWeight.w700,
            color: active ? Color.lerp(ink2, activeColor, bandT) : ink2,
          ),
        ),
        textDirection: TextDirection.ltr,
        maxLines: 1,
      )..layout(maxWidth: 110);
      final dx = switch (align) {
        TextAlign.center => at.dx - tp.width / 2,
        TextAlign.end => at.dx - tp.width,
        _ => at.dx,
      };
      tp.paint(canvas, Offset(dx, at.dy - tp.height + 3));
    }

    label(labels[0], Offset(pt(180).dx - 2, cy + 26), TextAlign.start, level == 0, bands[0]);
    label(labels[1], const Offset(cx, 14), TextAlign.center, level == 1, ink);
    label(labels[2], Offset(pt(0).dx + 2, cy + 26), TextAlign.end, level == 2, bands[2]);
    canvas.restore();
  }

  @override
  bool shouldRepaint(_DialPainter old) =>
      old.angle != angle || old.bandT != bandT || old.level != level || old.labels != labels || old.ink != ink;
}
