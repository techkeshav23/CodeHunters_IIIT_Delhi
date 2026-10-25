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
  const QuestionCard({super.key, required this.msg, required this.live, required this.onAnswer, this.showHelper = true});
  final QuestionMsg msg;
  final bool live;
  final ValueChanged<String> onAnswer;

  /// False hides the small helper line (trace.reasoning_local) when the
  /// question card before it in the thread had the same one.
  final bool showHelper;

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
          if (showHelper && res.trace.reasoningLocal.isNotEmpty) ...[
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
            borderRadius: BorderRadius.circular(16),
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

/// The final decision: dial, care label (with "Sunaiye"), reasoning and
/// safety-net advice; then the links (why, anything else, new chat), the why
/// panel (who decided, case details) and the caregivers.
class DecisionCard extends StatefulWidget {
  const DecisionCard({super.key, required this.msg, this.onAddMore, this.canBook = true});
  final DecisionMsg msg;

  /// False when a later emergency in the same chat overtook this decision:
  /// its Book buttons are disabled.
  final bool canBook;

  /// "Kuch aur batana hai?"; null hides the button (older decisions).
  final VoidCallback? onAddMore;

  @override
  State<DecisionCard> createState() => _DecisionCardState();
}

class _DecisionCardState extends State<DecisionCard> {
  bool _why = false;
  bool _doctor = false; // caregivers shown on the "nothing understood" card
  bool _allCarers = false; // the caregivers after the first one

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
    final frame = BoxDecoration(
      color: cc.surface,
      borderRadius: const BorderRadius.only(
        topLeft: Radius.circular(6),
        topRight: Radius.circular(rXl),
        bottomLeft: Radius.circular(rXl),
        bottomRight: Radius.circular(rXl),
      ),
      border: Border.all(color: cc.line),
      boxShadow: cc.shadow,
    );

    // Nothing understood: no advice, dial or "why", only a plain card that
    // offers a doctor (this reply's caregivers) or a new chat.
    if (d.unclear) {
      return Container(
        clipBehavior: Clip.antiAlias,
        decoration: frame,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            _UnclearNotice(
              lang: lang,
              onDoctor: () => setState(() => _doctor = !_doctor),
              onNewChat: state.newChat,
            ),
            AnimatedSize(
              duration: const Duration(milliseconds: 300),
              curve: Curves.easeOutCubic,
              alignment: Alignment.topCenter,
              child: _doctor ? _carers(cc, lang) : const SizedBox(width: double.infinity),
            ),
          ],
        ),
      );
    }

    final level = urgencyLevel(res.urgency ?? d.urgency);
    final care = careLabel(res, lang);
    final decidedBy = decidedByText(res.trace, lang);
    final safetyNet = res.trace.safetyNetLocal;
    final specialty = d.specialty ?? '';
    final title = Text(care, style: dv(display(22, color: cc.ink, height: 1.2), care));
    final readAloud = ReadAloudButton(
      id: 'd${widget.msg.id}',
      text: decisionSummary(res),
      voiceLang: res.trace.language,
      speech: res.trace.speech,
    );
    // "Sunaiye" sits beside the care label; with very large text it goes under it
    final roomy = MediaQuery.textScalerOf(context).scale(10) <= 12;

    return Container(
      clipBehavior: Clip.antiAlias,
      decoration: frame,
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
                const SizedBox(height: 12),
                if (roomy)
                  Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Expanded(child: title),
                      const SizedBox(width: 4),
                      Transform.translate(offset: const Offset(8, -6), child: readAloud),
                    ],
                  )
                else ...[
                  title,
                  Transform.translate(offset: const Offset(-10, 0), child: readAloud),
                ],
                if (specialty.isNotEmpty) ...[
                  const SizedBox(height: 10),
                  CCChip(t(lang, K.specialist, {'x': specialtyLabel(lang, specialty)})),
                ],
                const SizedBox(height: 12),
                Text(res.trace.reasoningLocal, style: body(16, color: cc.ink2)),
                if (safetyNet != null) ...[
                  const SizedBox(height: 12),
                  _SafetyNetNotice(text: safetyNet),
                ],
              ],
            ),
          ),
          // one calm row of links (it wraps on a narrow phone)
          Padding(
            padding: const EdgeInsets.fromLTRB(8, 2, 8, 8),
            child: Wrap(
              spacing: 2,
              children: [
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
                if (widget.onAddMore != null)
                  TextButton(
                    onPressed: widget.onAddMore,
                    style: TextButton.styleFrom(
                      foregroundColor: state.addingTo == widget.msg.id ? cc.brand2 : cc.ink2,
                    ),
                    child: Text(tm(lang, M.addMore)),
                  ),
                TextButton.icon(
                  onPressed: state.newChat,
                  icon: const Icon(LucideIcons.plus, size: 18),
                  label: Text(tm(lang, M.newChat)),
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
                        if (decidedBy != null) ...[
                          _DecidedBy(text: decidedBy, source: d.source),
                          const SizedBox(height: 16),
                        ],
                        CaseDetails(res: res, lang: lang),
                      ],
                    ),
                  )
                : const SizedBox(width: double.infinity),
          ),
          _carers(cc, lang),
        ],
      ),
    );
  }

  /// "Aapke liye sabse sahi": this reply's caregivers, each with Book. Only
  /// the best one at first; "Aur 2 dekhein" shows the rest.
  Widget _carers(CC cc, Lang lang) {
    final res = widget.msg.res;
    final tele = isTele(res.careType);
    final carers = res.trace.caregivers;
    final shown = _allCarers || carers.length < 2 ? carers.length : 1;
    return Padding(
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
          if (!widget.canBook && carers.isNotEmpty)
            Padding(
              padding: const EdgeInsets.fromLTRB(8, 0, 8, 10),
              child: Text(t(lang, K.bookLocked), style: body(15, color: cc.ink3)),
            ),
          for (var i = 0; i < shown; i++)
            EntryAnimation(
              delay: Duration(milliseconds: i == 0 ? 500 : 80 * (i - 1)),
              child: Padding(
                padding: const EdgeInsets.only(bottom: 12),
                child: CaregiverCard(
                  cg: carers[i],
                  best: i == 0,
                  tele: tele,
                  lang: lang,
                  onBook: widget.canBook ? () => _book(carers[i]) : null,
                ),
              ),
            ),
          if (shown < carers.length)
            TextButton.icon(
              onPressed: () => setState(() => _allCarers = true),
              iconAlignment: IconAlignment.end,
              icon: const Icon(LucideIcons.chevronDown, size: 18),
              label: Text(tm(lang, M.seeMore, {'n': carers.length - shown})),
            ),
        ],
      ),
    );
  }
}

/// Top of the decision card when nothing was understood (the backend gave
/// up after three tries and fell back to a doctor call): says so plainly,
/// then "Doctor se baat karein" (shows the caregivers) and "Nayi chat".
class _UnclearNotice extends StatelessWidget {
  const _UnclearNotice({required this.lang, required this.onDoctor, required this.onNewChat});
  final Lang lang;
  final VoidCallback onDoctor;
  final VoidCallback onNewChat;

  @override
  Widget build(BuildContext context) {
    final cc = CC.of(context);
    final title = tm(lang, M.unclearTitle);
    return Padding(
      padding: const EdgeInsets.fromLTRB(18, 18, 18, 16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Container(
                width: 40,
                height: 40,
                decoration: BoxDecoration(color: cc.haldiSoft, borderRadius: BorderRadius.circular(12)),
                child: Icon(LucideIcons.messageCircleQuestion, size: 20, color: cc.ink),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Padding(
                  padding: const EdgeInsets.only(top: 6),
                  child: Text(title, style: dv(display(21, color: cc.ink, height: 1.25), title)),
                ),
              ),
            ],
          ),
          const SizedBox(height: 10),
          Text(tm(lang, M.unclearText), style: body(16, color: cc.ink2)),
          const SizedBox(height: 14),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: [
              FilledButton.icon(
                onPressed: onDoctor,
                icon: const Icon(LucideIcons.stethoscope, size: 18),
                label: Text(tm(lang, M.unclearDoctor)),
              ),
              OutlinedButton.icon(
                onPressed: onNewChat,
                icon: const Icon(LucideIcons.plus, size: 18),
                label: Text(tm(lang, M.newChat)),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

/// One quiet line at the top of "Yeh faisla kyon?": which part of the system
/// decided ("MuRIL model ne tay kiya · Pakka bharosa").
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

/// Emergency result inside the thread: the red button dials 112; the title
/// re-opens the full-screen takeover.
class EmergencyInline extends StatelessWidget {
  const EmergencyInline({super.key, required this.msg});
  final EmergencyMsg msg;

  @override
  Widget build(BuildContext context) {
    final cc = CC.of(context);
    final lang = AppScope.of(context).lang;
    final title = msg.res.trace.emergency?.titleLocal ?? t(lang, K.sosPageTitle);
    final raised = emergencyRaisedText(msg.res.trace, lang);
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
          Semantics(
            button: true,
            label: title,
            excludeSemantics: true,
            child: Pressable(
              onTap: () => openEmergency(context, msg),
              child: ConstrainedBox(
                constraints: const BoxConstraints(minHeight: 44),
                child: Row(
                  children: [
                    Icon(LucideIcons.triangleAlert, size: 20, color: cc.sindoor),
                    const SizedBox(width: 8),
                    Expanded(
                      child: Text(
                        title,
                        style: dv(display(19, weight: FontWeight.w700, color: cc.ink), title),
                      ),
                    ),
                    const SizedBox(width: 8),
                    Icon(LucideIcons.chevronRight, size: 22, color: cc.ink2),
                  ],
                ),
              ),
            ),
          ),
          if (msg.res.trace.reasoningLocal.isNotEmpty) ...[
            const SizedBox(height: 8),
            Text(msg.res.trace.reasoningLocal, style: body(15, color: cc.ink)),
          ],
          if (raised != null) ...[
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
                    raised,
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
              onPressed: () => callNumber(context, '112', lang),
              icon: const Icon(LucideIcons.phone, size: 20),
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
                padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 8),
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
                    // wraps with large text on a narrow phone instead of overflowing
                    Flexible(
                      child: Text(
                        t(lang, K.retry),
                        style: body(15.5, weight: FontWeight.w700, color: cc.ink),
                      ),
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
