import 'package:flutter/material.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../i18n.dart';
import '../models.dart';
import '../strings_mobile.dart';
import '../theme.dart';
import '../util.dart';
import 'common.dart';

/// "What we understood / what we checked / safety checks" (web
/// CaseDetails.tsx).
class CaseDetails extends StatelessWidget {
  const CaseDetails({super.key, required this.res, required this.lang});
  final TriageResponse res;
  final Lang lang;

  /// Chips from trace.structured (the model's structured symptoms), or from
  /// trace.understood on servers that do not send it. The first chips are
  /// "who" (highlighted), only from the words or an answer (relation, age
  /// group, pregnancy), never the model's guess alone. No age in years: a
  /// tapped range ("60 saal ya zyada") is stored as 70, which nobody said.
  (List<String>, bool) _chips() {
    final tr = res.trace;
    final u = tr.understood;
    final st = tr.structured;
    final chips = <String>[];
    if (st != null && !st.isEmpty) {
      final p = u.patient;
      final rel = p.relation != null && p.relation != 'self' ? (p.relationLabel ?? '').trim() : '';
      if (rel.isNotEmpty) chips.add(titleCase(rel));
      final who = (p.ageGroup != null || p.pregnant == true || p.relation == 'self') ? st.whoChip : null;
      if (who != null && !chips.contains(titleCase(who))) chips.add(titleCase(who));
      final hasWho = chips.isNotEmpty;
      for (final s in st.symptoms) {
        chips.add(s.labelLocal);
      }
      final dur = fmtDays(st.durationDays ?? u.durationDays, lang);
      if (dur != null) chips.add(dur);
      return (chips, hasWho);
    }
    final hasRelation = u.patient.relationLabel != null && u.patient.relationLabel!.isNotEmpty;
    if (hasRelation) chips.add(titleCase(u.patient.relationLabel!));
    for (final s in u.symptoms) {
      chips.add(s.labelLocal);
    }
    for (final s in u.services) {
      chips.add(s.labelLocal);
    }
    final dur = fmtDays(u.durationDays, lang);
    if (dur != null) chips.add(dur);
    return (chips, hasRelation);
  }

  @override
  Widget build(BuildContext context) {
    final cc = CC.of(context);
    final tr = res.trace;
    final (chips, firstIsWho) = _chips();
    final guards = tr.guardrailsFiredFirst;
    final passed = [...guards.where((g) => !g.fired)];

    Widget heading(String text) => Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: Text(
        text,
        style: body(15, weight: FontWeight.w700, color: cc.ink2),
      ),
    );

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        heading(t(lang, K.understood)),
        if (chips.isEmpty)
          Text('-', style: body(15, color: cc.ink3))
        else
          Wrap(
            spacing: 6,
            runSpacing: 6,
            children: [
              for (var i = 0; i < chips.length; i++)
                CCChip(chips[i], tone: i == 0 && firstIsWho ? ChipTone.haldi : ChipTone.neutral),
            ],
          ),
        if (tr.checks.isNotEmpty) ...[
          const SizedBox(height: 18),
          heading(t(lang, K.checked)),
          for (final c in tr.checks) _CheckRow(check: c, lang: lang),
        ],
        if (guards.isNotEmpty) ...[
          const SizedBox(height: 18),
          heading(tm(lang, M.safetyChecks)),
          for (final g in guards.where((g) => g.fired)) _GuardrailRow(guard: g, lang: lang),
          if (passed.isNotEmpty) _PassedChecks(guards: passed, lang: lang),
        ],
      ],
    );
  }
}

/// The safety checks that passed, folded into one row ("11 suraksha jaanch ·
/// Theek") that opens to the full list. Fired checks stay visible above it.
class _PassedChecks extends StatefulWidget {
  const _PassedChecks({required this.guards, required this.lang});
  final List<Guardrail> guards;
  final Lang lang;

  @override
  State<_PassedChecks> createState() => _PassedChecksState();
}

class _PassedChecksState extends State<_PassedChecks> {
  bool _open = false;

  @override
  Widget build(BuildContext context) {
    final cc = CC.of(context);
    final lang = widget.lang;
    final label = tm(lang, M.safetyChecksPassed, {'n': '${widget.guards.length}'});
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Semantics(
          button: true,
          expanded: _open,
          child: InkWell(
            borderRadius: BorderRadius.circular(8),
            onTap: () => setState(() => _open = !_open),
            child: ConstrainedBox(
              constraints: const BoxConstraints(minHeight: 44),
              child: Row(
                children: [
                  Container(
                    width: 24,
                    height: 24,
                    alignment: Alignment.center,
                    decoration: BoxDecoration(color: cc.ok.withValues(alpha: 0.18), shape: BoxShape.circle),
                    child: Icon(LucideIcons.check, size: 14, color: cc.ok),
                  ),
                  const SizedBox(width: 10),
                  Expanded(
                    child: Text(label, style: body(15, weight: FontWeight.w600, color: cc.ink)),
                  ),
                  const SizedBox(width: 4),
                  AnimatedRotation(
                    turns: _open ? 0.5 : 0,
                    duration: const Duration(milliseconds: 200),
                    child: Icon(LucideIcons.chevronDown, size: 18, color: cc.ink2),
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
                  padding: const EdgeInsets.only(top: 8),
                  child: Column(
                    children: [for (final g in widget.guards) _GuardrailRow(guard: g, lang: lang)],
                  ),
                )
              : const SizedBox(width: double.infinity),
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

/// One safety check (trace.guardrails). A check that changed the answer is
/// highlighted on a haldi ground; one that passed is a plain row.
class _GuardrailRow extends StatelessWidget {
  const _GuardrailRow({required this.guard, required this.lang});
  final Guardrail guard;
  final Lang lang;

  @override
  Widget build(BuildContext context) {
    final cc = CC.of(context);
    final fired = guard.fired;
    final label = guard.labelLocal.isNotEmpty ? guard.labelLocal : guard.id;
    final status = tm(lang, fired ? M.grFired : M.grPass);
    final note = guard.noteLocal.trim();
    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      padding: fired ? const EdgeInsets.fromLTRB(10, 9, 10, 9) : EdgeInsets.zero,
      decoration: fired
          ? BoxDecoration(
              color: cc.haldiSoft,
              borderRadius: BorderRadius.circular(rMd),
              border: Border.all(color: cc.haldi.withValues(alpha: 0.4)),
            )
          : null,
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            width: 24,
            height: 24,
            alignment: Alignment.center,
            decoration: BoxDecoration(
              color: fired ? cc.haldi : cc.ok.withValues(alpha: 0.18),
              shape: BoxShape.circle,
            ),
            child: Icon(
              fired ? LucideIcons.shieldAlert : LucideIcons.check,
              size: 14,
              color: fired ? cc.haldiInk : cc.ok,
            ),
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  label,
                  style: body(15, weight: fired ? FontWeight.w700 : FontWeight.w400, color: cc.ink),
                ),
                Text(
                  note.isEmpty ? status : '$status · $note',
                  style: body(13, color: fired ? cc.ink2 : cc.ink3),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
