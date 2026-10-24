import 'package:flutter/material.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../i18n.dart';
import '../models.dart';
import '../state.dart';
import '../strings_mobile.dart';
import '../theme.dart';
import '../util.dart';
import 'booking_sheet.dart';
import 'caregiver_card.dart';
import 'case_details.dart';
import 'common.dart';
import 'dial.dart';
import 'emergency.dart';

/// The user's own message: a neem bubble on the right.
class UserBubble extends StatelessWidget {
  const UserBubble({super.key, required this.text});
  final String text;

  @override
  Widget build(BuildContext context) {
    final cc = CC.of(context);
    return Align(
      alignment: Alignment.centerRight,
      child: ConstrainedBox(
        constraints: BoxConstraints(maxWidth: MediaQuery.sizeOf(context).width * 0.82),
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
          decoration: BoxDecoration(
            gradient: LinearGradient(
              begin: Alignment.topLeft,
              end: Alignment.bottomRight,
              colors: [Color.lerp(cc.brand, Colors.white, 0.06)!, cc.brand],
            ),
            borderRadius: const BorderRadius.only(
              topLeft: Radius.circular(20),
              topRight: Radius.circular(20),
              bottomLeft: Radius.circular(20),
              bottomRight: Radius.circular(6),
            ),
          ),
          child: Text(text, style: body(16.5, color: cc.brandInk, height: 1.4)),
        ),
      ),
    );
  }
}

/// "Samajh rahe hain..." with three blinking dots.
class TypingIndicator extends StatefulWidget {
  const TypingIndicator({super.key});
  @override
  State<TypingIndicator> createState() => _TypingIndicatorState();
}

class _TypingIndicatorState extends State<TypingIndicator> with SingleTickerProviderStateMixin {
  late final AnimationController _c = AnimationController(vsync: this, duration: const Duration(milliseconds: 1200))
    ..repeat();

  @override
  void dispose() {
    _c.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final cc = CC.of(context);
    final lang = AppScope.of(context).lang;
    return Align(
      alignment: Alignment.centerLeft,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
        decoration: BoxDecoration(
          color: cc.surface,
          border: Border.all(color: cc.line),
          borderRadius: const BorderRadius.only(
            topLeft: Radius.circular(6),
            topRight: Radius.circular(20),
            bottomLeft: Radius.circular(20),
            bottomRight: Radius.circular(20),
          ),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Text(t(lang, K.thinking), style: body(15, color: cc.ink2)),
            const SizedBox(width: 10),
            AnimatedBuilder(
              animation: _c,
              builder: (context, _) => Row(
                children: [
                  for (var i = 0; i < 3; i++) ...[
                    if (i > 0) const SizedBox(width: 4),
                    Opacity(opacity: _dot(i), child: _circle(cc.brand)),
                  ],
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  double _dot(int i) {
    // 0.25 -> 1 -> 0.25 between 0% and 80% of the cycle, staggered 0.15s.
    final p = ((_c.value - i * 0.125) % 1.0);
    if (p > 0.8) return 0.25;
    final x = p / 0.8; // 0..1
    final tri = x < 0.5 ? x * 2 : (1 - x) * 2;
    return 0.25 + 0.75 * tri;
  }

  Widget _circle(Color c) => Container(
    width: 7,
    height: 7,
    decoration: BoxDecoration(color: c, shape: BoxShape.circle),
  );
}

const _assistantRadius = BorderRadius.only(
  topLeft: Radius.circular(6),
  topRight: Radius.circular(rLg),
  bottomLeft: Radius.circular(rLg),
  bottomRight: Radius.circular(rLg),
);

/// A follow-up question with tappable options ("Sawaal 1 / 3").
class QuestionCard extends StatelessWidget {
  const QuestionCard({super.key, required this.msg, required this.live, required this.onAnswer});
  final QuestionMsg msg;
  final bool live;
  final ValueChanged<String> onAnswer;

  @override
  Widget build(BuildContext context) {
    final cc = CC.of(context);
    final lang = AppScope.of(context).lang;
    final res = msg.res;
    final fu = res.trace.followUp;
    final text = res.questionText ?? '';
    final n = fu?.askedSoFar ?? 1;
    final max = (fu?.max ?? 3).clamp(1, 10);
    final voiceLang = res.trace.language;
    // q_scope is a polite "we can't help with this" reply, not a numbered question.
    final counted = fu?.id != 'q_scope';

    return Container(
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        color: cc.surface,
        borderRadius: _assistantRadius,
        border: Border.all(color: cc.line),
        boxShadow: cc.shadow,
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Wrap(
            crossAxisAlignment: WrapCrossAlignment.center,
            spacing: 9,
            runSpacing: 2,
            children: [
              if (counted) ...[
                Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    for (var i = 0; i < max; i++)
                      Container(
                        width: 22,
                        height: 5,
                        margin: EdgeInsets.only(right: i < max - 1 ? 5 : 0),
                        decoration: BoxDecoration(
                          color: i < n ? cc.haldi : cc.surface3,
                          borderRadius: BorderRadius.circular(3),
                        ),
                      ),
                  ],
                ),
                Text(
                  t(lang, K.questionOf, {'n': n, 'max': max}),
                  style: body(13.5, weight: FontWeight.w600, color: cc.ink3),
                ),
              ],
              ReadAloudButton(id: 'q${msg.id}', text: text, voiceLang: voiceLang, speech: res.trace.speech),
            ],
          ),
          const SizedBox(height: 8),
          Text(
            text,
            style: dv(display(23, weight: FontWeight.w700, color: cc.ink, height: 1.2), text),
          ),
          if (res.trace.reasoningLocal.isNotEmpty) ...[
            const SizedBox(height: 8),
            Text(res.trace.reasoningLocal, style: body(14.5, color: cc.ink2)),
          ],
          if (live && fu != null && fu.options.isNotEmpty) ...[
            const SizedBox(height: 14),
            if (fu.options.length <= 3)
              // Short answer sets share one row (Haan / Nahi / Pata nahi).
              IntrinsicHeight(
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    for (var i = 0; i < fu.options.length; i++) ...[
                      if (i > 0) const SizedBox(width: 8),
                      Expanded(
                        child: EntryAnimation(
                          delay: Duration(milliseconds: 80 * i),
                          offset: 10,
                          child: _OptionButton(option: fu.options[i], onTap: () => onAnswer(fu.options[i].label)),
                        ),
                      ),
                    ],
                  ],
                ),
              )
            else
              // Longer sets: two equal columns, so every option is a big target.
              LayoutBuilder(
                builder: (context, c) {
                  final w = (c.maxWidth - 10) / 2;
                  return Wrap(
                    spacing: 10,
                    runSpacing: 10,
                    children: [
                      for (var i = 0; i < fu.options.length; i++)
                        SizedBox(
                          width: w,
                          child: EntryAnimation(
                            delay: Duration(milliseconds: 80 * i),
                            offset: 10,
                            child: _OptionButton(option: fu.options[i], onTap: () => onAnswer(fu.options[i].label)),
                          ),
                        ),
                    ],
                  );
                },
              ),
          ],
        ],
      ),
    );
  }
}

class _OptionButton extends StatelessWidget {
  const _OptionButton({required this.option, required this.onTap});
  final FollowUpOption option;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final cc = CC.of(context);
    final yes = option.value == 'yes';
    return Semantics(
      button: true,
      label: option.label,
      excludeSemantics: true,
      child: Pressable(
        onTap: onTap,
        // Big, thumb-sized targets for elderly and low-literacy users.
        child: Container(
          constraints: const BoxConstraints(minHeight: 58, minWidth: 88),
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
          alignment: Alignment.center,
          decoration: BoxDecoration(
            color: cc.bg,
            borderRadius: BorderRadius.circular(999),
            border: Border.all(
              color: yes ? Color.lerp(cc.line, cc.sindoor, 0.45)! : Color.lerp(cc.line, cc.brand, 0.35)!,
              width: 1.8,
            ),
          ),
          child: Text(
            option.label,
            textAlign: TextAlign.center,
            style: body(18, weight: FontWeight.w700, color: cc.ink, height: 1.25),
          ),
        ),
      ),
    );
  }
}

/// The final decision: dial, care label, who decided, reasoning, safety-net
/// advice, why, caregivers.
class DecisionCard extends StatefulWidget {
  const DecisionCard({super.key, required this.msg, this.onAddMore});
  final DecisionMsg msg;

  /// "Aur jaankari jodein"; null hides the button (older decisions).
  final VoidCallback? onAddMore;

  @override
  State<DecisionCard> createState() => _DecisionCardState();
}

class _DecisionCardState extends State<DecisionCard> {
  bool _why = false;

  Future<void> _book(TraceCaregiver cg) async {
    final state = AppScope.read(context);
    final goToBookings = await showBookingSheet(context, cg, widget.msg.res);
    if (goToBookings == true) state.setTab(1);
  }

  @override
  Widget build(BuildContext context) {
    final cc = CC.of(context);
    final state = AppScope.of(context);
    final lang = state.lang;
    final res = widget.msg.res;
    final d = res.trace.decision;
    final level = urgencyLevel(res.urgency ?? d.urgency);
    final tele = isTele(res.careType);
    final carers = res.trace.caregivers;
    final dur = fmtDays(res.trace.structured?.durationDays ?? res.trace.understood.durationDays, lang);
    final care = careLabel(res, lang);
    final urg = urgencyLabel(res, lang);
    final decidedBy = decidedByText(res.trace, lang);
    final safetyNet = res.trace.safetyNetLocal;
    final urgTone = switch (level) {
      2 => ChipTone.danger,
      1 => ChipTone.haldi,
      _ => ChipTone.brand,
    };

    return Container(
      clipBehavior: Clip.antiAlias,
      decoration: BoxDecoration(
        color: cc.surface,
        borderRadius: const BorderRadius.only(
          topLeft: Radius.circular(6),
          topRight: Radius.circular(rXl),
          bottomLeft: Radius.circular(rXl),
          bottomRight: Radius.circular(rXl),
        ),
        border: Border.all(color: cc.line),
        boxShadow: cc.shadow,
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(18, 18, 18, 6),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Center(
                  child: Dial(level: level, lang: lang),
                ),
                const SizedBox(height: 10),
                Text(
                  t(lang, K.ourAdvice),
                  style: body(14, weight: FontWeight.w600, color: cc.ink3),
                ),
                const SizedBox(height: 4),
                Text(care, style: dv(display(22, color: cc.ink, height: 1.2), care)),
                const SizedBox(height: 10),
                Wrap(
                  spacing: 6,
                  runSpacing: 6,
                  children: [
                    CCChip(urg, tone: urgTone, icon: LucideIcons.clock),
                    if (d.specialty != null && d.specialty!.isNotEmpty)
                      CCChip(t(lang, K.specialist, {'x': specialtyLabel(lang, d.specialty!)})),
                    if (dur != null) CCChip(dur),
                  ],
                ),
                if (decidedBy != null) ...[
                  const SizedBox(height: 10),
                  _DecidedBy(text: decidedBy, source: d.source),
                ],
                const SizedBox(height: 12),
                Text(
                  res.trace.reasoningLocal,
                  maxLines: _why ? null : 3,
                  overflow: _why ? null : TextOverflow.ellipsis,
                  style: body(16, color: cc.ink2),
                ),
                if (safetyNet != null) ...[
                  const SizedBox(height: 12),
                  _SafetyNetNotice(text: safetyNet),
                ],
              ],
            ),
          ),
          Padding(
            padding: const EdgeInsets.fromLTRB(8, 2, 8, 8),
            child: Wrap(
              spacing: 2,
              children: [
                if (widget.onAddMore != null)
                  TextButton.icon(
                    onPressed: widget.onAddMore,
                    style: TextButton.styleFrom(
                      foregroundColor: state.addingTo == widget.msg.id ? cc.brand2 : cc.ink2,
                    ),
                    icon: const Icon(LucideIcons.messageSquarePlus, size: 18),
                    label: Text(tm(lang, M.addMore)),
                  ),
                ReadAloudButton(
                  id: 'd${widget.msg.id}',
                  text: decisionSummary(res),
                  voiceLang: res.trace.language,
                  speech: res.trace.speech,
                ),
                TextButton.icon(
                  onPressed: () => setState(() => _why = !_why),
                  iconAlignment: IconAlignment.end,
                  icon: AnimatedRotation(
                    turns: _why ? 0.5 : 0,
                    duration: const Duration(milliseconds: 220),
                    child: const Icon(LucideIcons.chevronDown, size: 18),
                  ),
                  label: Text(t(lang, K.whyThis)),
                ),
                TextButton.icon(
                  onPressed: state.newChat,
                  icon: const Icon(LucideIcons.rotateCcw, size: 16),
                  label: Text(t(lang, K.newCheck)),
                ),
              ],
            ),
          ),
          AnimatedSize(
            duration: const Duration(milliseconds: 300),
            curve: Curves.easeOutCubic,
            alignment: Alignment.topCenter,
            child: _why
                ? Container(
                    width: double.infinity,
                    padding: const EdgeInsets.fromLTRB(18, 16, 18, 18),
                    decoration: BoxDecoration(
                      color: cc.surface2,
                      border: Border(
                        top: BorderSide(color: cc.line),
                        bottom: BorderSide(color: cc.line),
                      ),
                    ),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        CaseDetails(res: res, lang: lang),
                        if (res.trace.modelTopProbability != null) ...[
                          const SizedBox(height: 8),
                          Row(
                            children: [
                              Icon(LucideIcons.chartNoAxesColumn, size: 14, color: cc.ink3),
                              const SizedBox(width: 6),
                              Expanded(
                                child: Text(
                                  tm(lang, M.modelConfidence,
                                      {'p': ((res.trace.modelSupportFor(res.careType) ?? 0) * 100).round()}),
                                  style: body(13, weight: FontWeight.w600, color: cc.ink3),
                                ),
                              ),
                            ],
                          ),
                        ],
                      ],
                    ),
                  )
                : const SizedBox(width: double.infinity),
          ),
          Padding(
            padding: const EdgeInsets.fromLTRB(10, 12, 10, 12),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Padding(
                  padding: const EdgeInsets.fromLTRB(8, 0, 8, 10),
                  child: Text(
                    t(lang, K.carersTitle),
                    style: display(19, weight: FontWeight.w700, color: cc.ink),
                  ),
                ),
                if (carers.isEmpty)
                  Padding(
                    padding: const EdgeInsets.fromLTRB(8, 0, 8, 6),
                    child: Text(t(lang, K.noCarers), style: body(15, color: cc.ink3)),
                  ),
                for (var i = 0; i < carers.length; i++)
                  EntryAnimation(
                    delay: Duration(milliseconds: 500 + 120 * i),
                    child: Padding(
                      padding: const EdgeInsets.only(bottom: 12),
                      child: CaregiverCard(
                        cg: carers[i],
                        best: i == 0,
                        tele: tele,
                        lang: lang,
                        onBook: () => _book(carers[i]),
                      ),
                    ),
                  ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

/// One quiet line under the care label: which part of the system decided
/// ("MuRIL model ne tay kiya · Pakka bharosa").
class _DecidedBy extends StatelessWidget {
  const _DecidedBy({required this.text, required this.source});
  final String text;
  final String source;

  @override
  Widget build(BuildContext context) {
    final cc = CC.of(context);
    final icon = switch (source) {
      'llm' => LucideIcons.sparkles,
      'safety_net' => LucideIcons.shieldCheck,
      'rules' => LucideIcons.listChecks,
      _ => LucideIcons.brainCircuit,
    };
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Padding(
          padding: const EdgeInsets.only(top: 2),
          child: Icon(icon, size: 15, color: cc.brand),
        ),
        const SizedBox(width: 7),
        Expanded(
          child: Text(text, style: body(13.5, weight: FontWeight.w600, color: cc.ink2, height: 1.35)),
        ),
      ],
    );
  }
}

/// "Come back / call 112 if ..." advice (trace.safety_net_local), always in
/// full under the reason.
class _SafetyNetNotice extends StatelessWidget {
  const _SafetyNetNotice({required this.text});
  final String text;

  @override
  Widget build(BuildContext context) {
    final cc = CC.of(context);
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.fromLTRB(12, 10, 12, 10),
      decoration: BoxDecoration(
        color: cc.haldiSoft,
        borderRadius: BorderRadius.circular(rMd),
        border: Border.all(color: cc.haldi.withValues(alpha: 0.35)),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Padding(
            padding: const EdgeInsets.only(top: 2),
            child: Icon(LucideIcons.lifeBuoy, size: 18, color: cc.ink),
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Text(text, style: body(15, color: cc.ink, height: 1.4)),
          ),
        ],
      ),
    );
  }
}

/// Emergency result inside the thread: re-opens the full-screen takeover.
class EmergencyInline extends StatelessWidget {
  const EmergencyInline({super.key, required this.msg});
  final EmergencyMsg msg;

  @override
  Widget build(BuildContext context) {
    final cc = CC.of(context);
    final lang = AppScope.of(context).lang;
    final title = msg.res.trace.emergency?.titleLocal ?? t(lang, K.sosPageTitle);
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: cc.sindoorSoft,
        borderRadius: _assistantRadius,
        border: Border.all(color: cc.sindoor.withValues(alpha: 0.35)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(LucideIcons.triangleAlert, size: 20, color: cc.sindoor),
              const SizedBox(width: 8),
              Expanded(
                child: Text(
                  title,
                  style: dv(display(19, weight: FontWeight.w700, color: cc.ink), title),
                ),
              ),
            ],
          ),
          if (msg.res.trace.reasoningLocal.isNotEmpty) ...[
            const SizedBox(height: 8),
            Text(msg.res.trace.reasoningLocal, style: body(15, color: cc.ink)),
          ],
          if (msg.res.trace.raisedBySafetyNet) ...[
            const SizedBox(height: 8),
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Padding(
                  padding: const EdgeInsets.only(top: 2),
                  child: Icon(LucideIcons.shieldAlert, size: 15, color: cc.sindoor),
                ),
                const SizedBox(width: 7),
                Expanded(
                  child: Text(
                    tm(lang, M.sosBySafetyNet),
                    style: body(13.5, weight: FontWeight.w600, color: cc.ink2, height: 1.35),
                  ),
                ),
              ],
            ),
          ],
          const SizedBox(height: 12),
          SizedBox(
            width: double.infinity,
            child: FilledButton.icon(
              style: FilledButton.styleFrom(backgroundColor: CC.sosFixed, foregroundColor: Colors.white),
              onPressed: () => openEmergency(context, msg),
              icon: const Icon(LucideIcons.siren, size: 20),
              label: Text(t(lang, K.sosNow)),
            ),
          ),
        ],
      ),
    );
  }
}

/// A failed request: never a made-up answer, only the error and a retry
/// chip on that message.
class ErrorCard extends StatelessWidget {
  const ErrorCard({super.key, required this.onRetry});
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) {
    final cc = CC.of(context);
    final lang = AppScope.of(context).lang;
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.fromLTRB(16, 14, 16, 14),
      decoration: BoxDecoration(
        color: cc.sindoorSoft,
        borderRadius: _assistantRadius,
        border: Border.all(color: cc.sindoor.withValues(alpha: 0.25)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Padding(
                padding: const EdgeInsets.only(top: 2),
                child: Icon(LucideIcons.wifiOff, size: 18, color: cc.sindoor),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: Text(t(lang, K.errorText), style: body(15, color: cc.ink)),
              ),
            ],
          ),
          const SizedBox(height: 12),
          Semantics(
            button: true,
            label: t(lang, K.retry),
            excludeSemantics: true,
            child: Pressable(
              onTap: onRetry,
              child: Container(
                constraints: const BoxConstraints(minHeight: 48),
                padding: const EdgeInsets.symmetric(horizontal: 18),
                decoration: BoxDecoration(
                  color: cc.surface,
                  borderRadius: BorderRadius.circular(999),
                  border: Border.all(color: cc.sindoor.withValues(alpha: 0.5), width: 1.5),
                ),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Icon(LucideIcons.rotateCcw, size: 17, color: cc.sindoor),
                    const SizedBox(width: 8),
                    Text(
                      t(lang, K.retry),
                      style: body(15.5, weight: FontWeight.w700, color: cc.ink),
                    ),
                  ],
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}
