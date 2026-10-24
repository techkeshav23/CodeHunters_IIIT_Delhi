import 'package:flutter/material.dart';

import '../theme.dart';

/// Logo: a caring hand under a heartbeat, with a location pin (assets/logo_mark.png),
/// on a white rounded tile so it reads in light and dark themes. Same as the web.
class BrandMark extends StatelessWidget {
  const BrandMark({super.key, this.size = 34});
  final double size;

  @override
  Widget build(BuildContext context) {
    return ClipRRect(
      borderRadius: BorderRadius.circular(size * 0.28),
      child: Container(
        width: size,
        height: size,
        color: Colors.white,
        child: Image.asset('assets/logo_mark.png', fit: BoxFit.contain, semanticLabel: null),
      ),
    );
  }
}

/// "Raahat" in neem: the wordmark.
class BrandWordmark extends StatelessWidget {
  const BrandWordmark({super.key, this.size = 20});
  final double size;

  @override
  Widget build(BuildContext context) {
    final cc = CC.of(context);
    return Text.rich(
      TextSpan(
        children: [
          TextSpan(
            text: 'Raahat',
            style: TextStyle(color: cc.brand),
          ),
        ],
      ),
      style: display(size, color: cc.ink).copyWith(letterSpacing: -0.4),
    );
  }
}
