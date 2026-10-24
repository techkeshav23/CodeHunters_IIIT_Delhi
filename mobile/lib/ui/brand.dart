import 'package:flutter/material.dart';

import '../theme.dart';

/// Logo: a compass needle inside a rounded tile. The haldi tip points the way.
/// Same geometry as web/src/ui/Brand.tsx (40 x 40 viewBox).
class BrandMark extends StatelessWidget {
  const BrandMark({super.key, this.size = 34});
  final double size;

  @override
  Widget build(BuildContext context) {
    final cc = CC.of(context);
    return SizedBox.square(
      dimension: size,
      child: CustomPaint(
        painter: BrandMarkPainter(brand: cc.brand, ink: cc.brandInk, haldi: cc.haldi),
      ),
    );
  }
}

class BrandMarkPainter extends CustomPainter {
  BrandMarkPainter({required this.brand, required this.ink, required this.haldi});
  final Color brand, ink, haldi;

  @override
  void paint(Canvas canvas, Size size) {
    final s = size.width / 40;
    canvas.scale(s);
    canvas.drawRRect(
      RRect.fromRectAndRadius(const Rect.fromLTWH(0, 0, 40, 40), const Radius.circular(12)),
      Paint()..color = brand,
    );
    canvas.drawCircle(
      const Offset(20, 20),
      12.5,
      Paint()
        ..style = PaintingStyle.stroke
        ..strokeWidth = 1.5
        ..color = ink.withValues(alpha: 0.35),
    );
    final north = Path()
      ..moveTo(20, 7.5)
      ..lineTo(24.2, 20)
      ..lineTo(20, 18.6)
      ..lineTo(15.8, 20)
      ..close();
    canvas.drawPath(north, Paint()..color = haldi);
    final south = Path()
      ..moveTo(20, 32.5)
      ..lineTo(15.8, 20)
      ..lineTo(20, 21.4)
      ..lineTo(24.2, 20)
      ..close();
    canvas.drawPath(south, Paint()..color = ink);
    canvas.drawCircle(const Offset(20, 20), 1.8, Paint()..color = brand);
  }

  @override
  bool shouldRepaint(BrandMarkPainter old) => old.brand != brand || old.ink != ink || old.haldi != haldi;
}

/// "Care" in ink, "Compass" in neem: the wordmark.
class BrandWordmark extends StatelessWidget {
  const BrandWordmark({super.key, this.size = 20});
  final double size;

  @override
  Widget build(BuildContext context) {
    final cc = CC.of(context);
    return Text.rich(
      TextSpan(
        children: [
          const TextSpan(text: 'Care'),
          TextSpan(
            text: 'Compass',
            style: TextStyle(color: cc.brand),
          ),
        ],
      ),
      style: display(size, color: cc.ink).copyWith(letterSpacing: -0.4),
    );
  }
}
