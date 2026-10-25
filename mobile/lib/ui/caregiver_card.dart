import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../i18n.dart';
import '../models.dart';
import '../theme.dart';
import '../util.dart';

/// Labels for the match sub-scores we know; any other key the API adds is
/// shown with a readable version of its name.
const _featureLabels = {
  'skill': K.fSkill,
  'time': K.fTime,
  'distance': K.fDistance,
  'language': K.fLanguage,
  'rating': K.fRating,
};

String featureLabel(String key, Lang lang) {
  final k = _featureLabels[key];
  if (k != null) return t(lang, k);
  final words = key.replaceAll('_', ' ').trim();
  return words.isEmpty ? key : words[0].toUpperCase() + words.substring(1);
}

/// One matched caregiver (web CaregiverCard.tsx): who, rating, free slot,
/// distance, languages, why, match % ring, a "how we matched" breakdown,
/// and a full-width Book button.
class CaregiverCard extends StatefulWidget {
  const CaregiverCard({
    super.key,
    required this.cg,
    required this.best,
    required this.tele,
    required this.lang,
    required this.onBook,
  });
  final TraceCaregiver cg;
  final bool best;
  final bool tele;
  final Lang lang;

  /// Null disables the Book button (a later emergency overtook this advice).
  final VoidCallback? onBook;

  @override
  State<CaregiverCard> createState() => _CaregiverCardState();
}

class _CaregiverCardState extends State<CaregiverCard> {
  bool _open = false;

  @override
  Widget build(BuildContext context) {
    final cc = CC.of(context);
    final cg = widget.cg;
    final lang = widget.lang;
    final pct = (cg.score * 100).round().clamp(0, 100);
    final feats = (cg.features?.values.entries ?? const <MapEntry<String, double>>[])
        .where((e) => !(widget.tele && e.key == 'distance'))
        .toList();

    // quiet cards; the best match gets a thin brand accent on its left edge
    final border = widget.best ? Color.lerp(cc.line, cc.brand, 0.45)! : cc.line;
    final bg = cc.surface;

    Widget fact(IconData icon, String text) => Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Icon(icon, size: 15, color: cc.ink2),
        const SizedBox(width: 5),
        Flexible(
          child: Text(text, style: body(14, color: cc.ink2, height: 1.3)),
        ),
      ],
    );

    final window = (cg.freeFrom != null && cg.freeUntil != null) ? '${cg.freeFrom}–${cg.freeUntil}' : null;

    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: bg,
        borderRadius: BorderRadius.circular(rLg),
        border: Border.all(color: border, width: 1),
        boxShadow: widget.best ? [BoxShadow(color: cc.brand, offset: const Offset(-3, 0))] : null,
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              _Avatar(name: cg.name, seed: cg.caregiverId),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    if (widget.best)
                      Container(
                        margin: const EdgeInsets.only(bottom: 4),
                        padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 3),
                        decoration: BoxDecoration(color: cc.haldi, borderRadius: BorderRadius.circular(999)),
                        child: Text(
                          t(lang, K.bestMatch),
                          style: body(12, weight: FontWeight.w700, color: cc.haldiInk, height: 1.2),
                        ),
                      ),
                    Text(
                      cg.name,
                      style: body(17.5, weight: FontWeight.w700, color: cc.ink, height: 1.25),
                    ),
                    const SizedBox(height: 2),
                    Text(
                      roleLabel(cg.role, lang),
                      style: body(14, weight: FontWeight.w600, color: cc.ink3),
                    ),
                  ],
                ),
              ),
              const SizedBox(width: 8),
              MatchRing(value: cg.score, label: t(lang, K.match), semantics: '$pct% ${t(lang, K.match)}'),
            ],
          ),
          const SizedBox(height: 12),
          Wrap(
            spacing: 14,
            runSpacing: 6,
            children: [
              if (cg.rating != null)
                Semantics(
                  label: '${t(lang, K.fRating)} ${cg.rating!.toStringAsFixed(1)}',
                  excludeSemantics: true,
                  child: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Icon(Icons.star_rounded, size: 18, color: cc.haldi),
                      const SizedBox(width: 3),
                      Text(
                        cg.rating!.toStringAsFixed(1),
                        style: body(14, weight: FontWeight.w700, color: cc.ink, height: 1.3),
                      ),
                    ],
                  ),
                ),
              if (cg.nextSlotLabelLocal != null) fact(LucideIcons.clock, cg.nextSlotLabelLocal!),
              if (window != null) fact(LucideIcons.calendarClock, window),
              if (widget.tele)
                fact(LucideIcons.video, t(lang, K.videoCall))
              else if (cg.distanceKm != null)
                fact(LucideIcons.mapPin, t(lang, K.kmAway, {'d': cg.distanceKm!.toStringAsFixed(1)})),
            ],
          ),
          if (cg.languages.isNotEmpty) ...[
            const SizedBox(height: 10),
            Wrap(
              spacing: 6,
              runSpacing: 6,
              crossAxisAlignment: WrapCrossAlignment.center,
              children: [
                Icon(LucideIcons.languages, size: 15, color: cc.ink3, semanticLabel: t(lang, K.fLanguage)),
                for (final l in cg.languages)
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                    decoration: BoxDecoration(
                      color: cc.surface,
                      borderRadius: BorderRadius.circular(999),
                      border: Border.all(color: cc.line),
                    ),
                    child: Text(
                      l,
                      style: body(13, weight: FontWeight.w600, color: cc.ink2, height: 1.2),
                    ),
                  ),
              ],
            ),
          ],
          const SizedBox(height: 10),
          Text(cg.reasonLocal, style: body(15, color: cc.ink)),
          if (feats.isNotEmpty) ...[
            const SizedBox(height: 4),
            Semantics(
              button: true,
              expanded: _open,
              child: InkWell(
                borderRadius: BorderRadius.circular(8),
                onTap: () => setState(() => _open = !_open),
                child: ConstrainedBox(
                  constraints: const BoxConstraints(minHeight: 44),
                  child: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Flexible(
                        child: Text(
                          t(lang, K.matchHow),
                          style: body(14.5, weight: FontWeight.w700, color: cc.brand2),
                        ),
                      ),
                      const SizedBox(width: 4),
                      AnimatedRotation(
                        turns: _open ? 0.5 : 0,
                        duration: const Duration(milliseconds: 200),
                        child: Icon(LucideIcons.chevronDown, size: 16, color: cc.brand2),
                      ),
                    ],
                  ),
                ),
              ),
            ),
            AnimatedSize(
              duration: const Duration(milliseconds: 260),
              curve: Curves.easeOutCubic,
              alignment: Alignment.topCenter,
              child: _open
                  ? Padding(
                      padding: const EdgeInsets.only(bottom: 6),
                      child: Column(
                        children: [
                          for (var i = 0; i < feats.length; i++)
                            FeatureBar(
                              label: featureLabel(feats[i].key, lang),
                              value: feats[i].value,
                              delay: i * 60,
                              // the rating feature is scaled over the roster (3.9 stars -> 8%): show the stars
                              stars: feats[i].key == 'rating' ? cg.rating : null,
                            ),
                        ],
                      ),
                    )
                  : const SizedBox(width: double.infinity),
            ),
          ],
          const SizedBox(height: 10),
          SizedBox(
            width: double.infinity,
            child: FilledButton.icon(
              onPressed: widget.onBook,
              icon: const Icon(LucideIcons.calendarCheck, size: 18),
              label: Text(t(lang, K.book)),
            ),
          ),
        ],
      ),
    );
  }
}

class _Avatar extends StatelessWidget {
  const _Avatar({required this.name, required this.seed});
  final String name;
  final String seed;

  @override
  Widget build(BuildContext context) {
    final c = avatarColor(seed);
    return ExcludeSemantics(
      child: Container(
        width: 52,
        height: 52,
        alignment: Alignment.center,
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(16),
          gradient: LinearGradient(
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
            colors: [Color.lerp(c, Colors.white, 0.12)!, c],
          ),
        ),
        child: Text(initials(name), style: display(19, color: Colors.white, height: 1)),
      ),
    );
  }
}

/// Circular match-% ring that fills once when the card appears.
class MatchRing extends StatelessWidget {
  const MatchRing({super.key, required this.value, required this.label, required this.semantics, this.size = 58});
  final double value;
  final String label;
  final String semantics;
  final double size;

  @override
  Widget build(BuildContext context) {
    final cc = CC.of(context);
    final v = value.clamp(0.0, 1.0);
    return Semantics(
      label: semantics,
      excludeSemantics: true,
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          TweenAnimationBuilder<double>(
            tween: Tween(begin: 0, end: v),
            duration: const Duration(milliseconds: 900),
            curve: Curves.easeOutCubic,
            builder: (context, x, _) => SizedBox.square(
              dimension: size,
              child: CustomPaint(
                painter: _RingPainter(value: x, track: cc.surface3, fill: cc.brand),
                child: Center(
                  child: FittedBox(
                    fit: BoxFit.scaleDown,
                    child: Padding(
                      padding: const EdgeInsets.all(7),
                      child: Text('${(x * 100).round()}%', style: display(17, color: cc.brand2, height: 1)),
                    ),
                  ),
                ),
              ),
            ),
          ),
          const SizedBox(height: 3),
          Text(
            label,
            style: body(11.5, weight: FontWeight.w600, color: cc.ink3, height: 1.1),
          ),
        ],
      ),
    );
  }
}

class _RingPainter extends CustomPainter {
  _RingPainter({required this.value, required this.track, required this.fill});
  final double value;
  final Color track, fill;

  @override
  void paint(Canvas canvas, Size size) {
    const stroke = 5.0;
    final rect = (Offset.zero & size).deflate(stroke / 2);
    canvas.drawArc(
      rect,
      0,
      math.pi * 2,
      false,
      Paint()
        ..style = PaintingStyle.stroke
        ..strokeWidth = stroke
        ..color = track,
    );
    canvas.drawArc(
      rect,
      -math.pi / 2,
      math.pi * 2 * value,
      false,
      Paint()
        ..style = PaintingStyle.stroke
        ..strokeWidth = stroke
        ..strokeCap = StrokeCap.round
        ..color = fill,
    );
  }

  @override
  bool shouldRepaint(_RingPainter old) => old.value != value || old.fill != fill || old.track != track;
}

/// Labelled 0-100% bar for one match sub-score, or, with [stars], the star
/// rating out of 5.
class FeatureBar extends StatelessWidget {
  const FeatureBar({super.key, required this.label, required this.value, this.delay = 0, this.stars});
  final String label;
  final double value;
  final int delay;
  final double? stars;

  @override
  Widget build(BuildContext context) {
    final cc = CC.of(context);
    final s = stars;
    final pct = s != null ? (s / 5 * 100).round().clamp(0, 100) : (value * 100).round().clamp(0, 100);
    final shown = s != null ? s.toStringAsFixed(1) : '$pct%';
    return Semantics(
      label: s != null ? '$label $shown / 5' : '$label $pct%',
      excludeSemantics: true,
      child: Padding(
        padding: const EdgeInsets.symmetric(vertical: 5),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Expanded(
                  child: Text(label, style: body(13.5, color: cc.ink2, height: 1.2)),
                ),
                Text(
                  shown,
                  style: body(
                    13,
                    weight: FontWeight.w600,
                    color: cc.ink3,
                  ).copyWith(fontFeatures: const [FontFeature.tabularFigures()]),
                ),
                if (s != null) ...[
                  const SizedBox(width: 2),
                  Icon(Icons.star_rounded, size: 15, color: cc.haldi),
                ],
              ],
            ),
            const SizedBox(height: 4),
            ClipRRect(
              borderRadius: BorderRadius.circular(4),
              child: Container(
                height: 7,
                color: cc.surface3,
                alignment: Alignment.centerLeft,
                child: TweenAnimationBuilder<double>(
                  tween: Tween(begin: 0, end: pct / 100),
                  duration: Duration(milliseconds: 600 + delay),
                  curve: Curves.easeOutCubic,
                  builder: (context, v, _) => FractionallySizedBox(
                    widthFactor: v,
                    heightFactor: 1,
                    child: DecoratedBox(
                      decoration: BoxDecoration(color: cc.brand, borderRadius: BorderRadius.circular(4)),
                    ),
                  ),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
