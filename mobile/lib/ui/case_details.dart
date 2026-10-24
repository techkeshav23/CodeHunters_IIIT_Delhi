import 'package:flutter/material.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../i18n.dart';
import '../models.dart';
import '../theme.dart';
import '../util.dart';
import 'common.dart';

/// "What we understood / what we checked / why" (web CaseDetails.tsx).
class CaseDetails extends StatelessWidget {
  const CaseDetails({super.key, required this.res, required this.lang});
  final TriageResponse res;
  final Lang lang;

  @override
  Widget build(BuildContext context) {
    final cc = CC.of(context);
    final tr = res.trace;
    final u = tr.understood;
    final chips = <String>[];
    if (u.patient.relationLabel != null && u.patient.relationLabel!.isNotEmpty) {
      chips.add(titleCase(u.patient.relationLabel!));
    }
    final age = u.patient.ageYears;
    if (age != null && age >= 1) chips.add('${age.round()}y');
    for (final s in u.symptoms) {
      chips.add(s.labelLocal);
    }
    for (final s in u.services) {
      chips.add(s.labelLocal);
    }
    final dur = fmtDays(u.durationDays, lang);
    if (dur != null) chips.add(dur);
    final hasRelation = u.patient.relationLabel != null && u.patient.relationLabel!.isNotEmpty;

    Widget heading(K k) => Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: Text(
        t(lang, k),
        style: body(15, weight: FontWeight.w700, color: cc.ink2),
      ),
    );

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        heading(K.understood),
        if (chips.isEmpty)
          Text('-', style: body(15, color: cc.ink3))
        else
          Wrap(
            spacing: 6,
            runSpacing: 6,
            children: [
              for (var i = 0; i < chips.length; i++)
                CCChip(chips[i], tone: i == 0 && hasRelation ? ChipTone.haldi : ChipTone.neutral),
            ],
          ),
        if (tr.checks.isNotEmpty) ...[
          const SizedBox(height: 18),
          heading(K.checked),
          for (final c in tr.checks) _CheckRow(check: c, lang: lang),
        ],
        const SizedBox(height: 18),
        heading(K.reasonTitle),
        Text(tr.reasoningLocal, style: body(15.5, color: cc.ink)),
        const SizedBox(height: 6),
        Text(
          '${tr.decision.rule} | ${(tr.decision.confidence * 100).round()}% | ${tr.timingMs} ms',
          style: body(12.5, color: cc.ink3),
        ),
      ],
    );
  }
}

class _CheckRow extends StatelessWidget {
  const _CheckRow({required this.check, required this.lang});
  final Check check;
  final Lang lang;

  @override
  Widget build(BuildContext context) {
    final cc = CC.of(context);
    final (IconData icon, Color bg, Color fg, K label) = switch (check.status) {
      CheckStatus.present => (LucideIcons.triangleAlert, cc.sindoorSoft, cc.sindoor, K.stPresent),
      CheckStatus.absent => (LucideIcons.check, cc.ok.withValues(alpha: 0.18), cc.ok, K.stAbsent),
      CheckStatus.notReported => (LucideIcons.circleHelp, cc.surface3, cc.ink3, K.stUnknown),
    };
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            width: 24,
            height: 24,
            alignment: Alignment.center,
            decoration: BoxDecoration(color: bg, shape: BoxShape.circle),
            child: Icon(icon, size: 14, color: fg),
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(check.labelLocal, style: body(15, color: cc.ink)),
                Text(t(lang, label), style: body(13, color: cc.ink3)),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
