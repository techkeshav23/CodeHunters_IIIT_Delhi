import 'package:flutter/material.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../i18n.dart';
import '../state.dart';
import '../theme.dart';
import '../ui/common.dart';
import '../ui/composer.dart';
import '../ui/emergency.dart';
import '../ui/thread.dart';

/// Jaanch. Empty: one line of greeting, one big mic, the text box, quick
/// chips. Once a message is sent: the consult thread with the composer
/// docked at the bottom.
class CheckScreen extends StatefulWidget {
  const CheckScreen({super.key});

  @override
  State<CheckScreen> createState() => _CheckScreenState();
}

class _CheckScreenState extends State<CheckScreen> {
  final _input = TextEditingController();
  final _focus = FocusNode();
  final _scroll = ScrollController();
  final Map<int, GlobalKey> _keys = {};
  int _seenCount = 0;
  bool _seenBusy = false;

  @override
  void dispose() {
    _input.dispose();
    _focus.dispose();
    _scroll.dispose();
    super.dispose();
  }

  Future<void> _send(String text, {bool usedVoice = false}) async {
    final state = AppScope.read(context);
    if (state.busy) return;
    _input.clear();
    _focus.unfocus();
    final added = await state.send(text, usedVoice: usedVoice);
    if (!mounted) return;
    if (added is EmergencyMsg) await openEmergency(context, added);
  }

  Future<void> _retry(ErrorMsg m) async {
    final added = await AppScope.read(context).retry(m);
    if (!mounted) return;
    if (added is EmergencyMsg) await openEmergency(context, added);
  }

  void _seed(String s) {
    _input.value = TextEditingValue(
      text: s,
      selection: TextSelection.collapsed(offset: s.length),
    );
    _focus.requestFocus();
  }

  /// A sent message scrolls to the end; a new answer scrolls to its own top
  /// (decision headline first), like the web app.
  void _autoScroll(AppState state) {
    final count = state.messages.length;
    final busy = state.busy;
    if (count == _seenCount && busy == _seenBusy) return;
    final grew = count > _seenCount;
    _seenCount = count;
    _seenBusy = busy;
    if (count == 0) {
      _keys.clear();
      return;
    }
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted || !_scroll.hasClients) return;
      final last = state.messages.last;
      if (last is UserMsg || busy || !grew) {
        _scroll.animateTo(
          _scroll.position.maxScrollExtent,
          duration: const Duration(milliseconds: 350),
          curve: Curves.easeOutCubic,
        );
      } else {
        final ctx = _keys[last.id]?.currentContext;
        if (ctx != null) {
          Scrollable.ensureVisible(
            ctx,
            alignment: 0,
            duration: const Duration(milliseconds: 450),
            curve: Curves.easeOutCubic,
          );
        }
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    final state = AppScope.of(context);
    _autoScroll(state);
    final msgs = state.messages;

    if (msgs.isEmpty) {
      return _StartView(
        controller: _input,
        focusNode: _focus,
        onSend: (text, usedVoice) => _send(text, usedVoice: usedVoice),
        onSeed: _seed,
        onExample: (s) => _send(s),
      );
    }

    final lastQuestionId = msgs.last is QuestionMsg ? msgs.last.id : null;
    return Column(
      children: [
        Expanded(
          child: ListView.builder(
            controller: _scroll,
            padding: const EdgeInsets.fromLTRB(16, 16, 16, 24),
            itemCount: msgs.length + (state.busy ? 1 : 0),
            itemBuilder: (context, i) {
              if (i == msgs.length) {
                return const Padding(
                  padding: EdgeInsets.only(top: 4),
                  child: EntryAnimation(child: TypingIndicator()),
                );
              }
              final m = msgs[i];
              final key = _keys.putIfAbsent(m.id, GlobalKey.new);
              final Widget child = switch (m) {
                UserMsg() => UserBubble(text: m.text),
                QuestionMsg() => QuestionCard(
                  msg: m,
                  live: m.id == lastQuestionId && !state.busy,
                  onAnswer: (s) => _send(s),
                ),
                DecisionMsg() => DecisionCard(msg: m),
                EmergencyMsg() => EmergencyInline(msg: m),
                ErrorMsg() => ErrorCard(onRetry: () => _retry(m)),
              };
              return Padding(
                key: key,
                padding: const EdgeInsets.only(bottom: 16),
                child: EntryAnimation(child: child),
              );
            },
          ),
        ),
        Composer(
          controller: _input,
          focusNode: _focus,
          onSend: (text, usedVoice) => _send(text, usedVoice: usedVoice),
        ),
      ],
    );
  }
}

const _picks = <(IconData, K, K)>[
  (LucideIcons.thermometer, K.pickFever, K.seedFever),
  (LucideIcons.wind, K.pickCough, K.seedCough),
  (LucideIcons.pill, K.pickStomach, K.seedStomach),
  (LucideIcons.bandage, K.pickInjury, K.seedInjury),
  (LucideIcons.syringe, K.pickInjection, K.seedInjection),
  (LucideIcons.stethoscope, K.pickDoctor, K.seedDoctor),
  (LucideIcons.handHeart, K.pickElder, K.seedElder),
  (LucideIcons.activity, K.pickBp, K.seedBp),
];

class _StartView extends StatelessWidget {
  const _StartView({
    required this.controller,
    required this.focusNode,
    required this.onSend,
    required this.onSeed,
    required this.onExample,
  });
  final TextEditingController controller;
  final FocusNode focusNode;
  final void Function(String text, bool usedVoice) onSend;
  final ValueChanged<String> onSeed;
  final ValueChanged<String> onExample;

  @override
  Widget build(BuildContext context) {
    final cc = CC.of(context);
    final lang = AppScope.of(context).lang;
    final hello = t(lang, K.hello);

    Widget label(K k) => Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: Text(
        t(lang, k),
        style: body(14.5, weight: FontWeight.w600, color: cc.ink3),
      ),
    );

    return ListView(
      padding: const EdgeInsets.fromLTRB(16, 22, 16, 28),
      children: [
        EntryAnimation(
          child: Text(
            hello,
            textAlign: TextAlign.center,
            style: dv(display(26, color: cc.ink, height: 1.2), hello),
          ),
        ),
        const SizedBox(height: 26),
        EntryAnimation(
          delay: const Duration(milliseconds: 80),
          child: Composer(controller: controller, focusNode: focusNode, onSend: onSend, hero: true),
        ),
        const SizedBox(height: 30),
        Center(child: label(K.quickPicks)),
        // small one-line pills, centred (web start screen)
        Wrap(
          alignment: WrapAlignment.center,
          spacing: 8,
          runSpacing: 8,
          children: [
            for (var i = 0; i < _picks.length; i++)
              EntryAnimation(
                delay: Duration(milliseconds: 140 + 30 * i),
                offset: 8,
                child: _PickTile(
                  icon: _picks[i].$1,
                  label: t(lang, _picks[i].$2),
                  onTap: () => onSeed(t(lang, _picks[i].$3)),
                ),
              ),
          ],
        ),
        const SizedBox(height: 24),
        Center(child: label(K.tryExample)),
        Wrap(
          alignment: WrapAlignment.center,
          spacing: 8,
          runSpacing: 8,
          children: [
            for (final k in const [K.ex1, K.ex2, K.ex3]) _Example(text: t(lang, k), onTap: () => onExample(t(lang, k))),
          ],
        ),
        const SizedBox(height: 28),
        Notice(t(lang, K.disclaimer)),
      ],
    );
  }
}

/// Quick pick tile (icon + label); seeds the text box.
class _PickTile extends StatelessWidget {
  const _PickTile({required this.icon, required this.label, required this.onTap});
  final IconData icon;
  final String label;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final cc = CC.of(context);
    return Semantics(
      button: true,
      label: label,
      excludeSemantics: true,
      child: Pressable(
        onTap: onTap,
        child: Container(
          constraints: const BoxConstraints(minHeight: 44),
          padding: const EdgeInsets.fromLTRB(12, 9, 15, 9),
          decoration: BoxDecoration(
            color: cc.surface,
            borderRadius: BorderRadius.circular(999),
            border: Border.all(color: cc.line),
          ),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(icon, size: 17, color: cc.brand),
              const SizedBox(width: 7),
              // wraps to a second line only with large text on a narrow phone
              Flexible(child: Text(label, style: body(14.5, weight: FontWeight.w600, color: cc.ink, height: 1.2))),
            ],
          ),
        ),
      ),
    );
  }
}

class _Example extends StatelessWidget {
  const _Example({required this.text, required this.onTap});
  final String text;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final cc = CC.of(context);
    return Semantics(
      button: true,
      label: text,
      excludeSemantics: true,
      child: Pressable(
        onTap: onTap,
        child: CustomPaint(
          painter: _DashedPill(color: Colors.transparent),
          child: ConstrainedBox(
            constraints: const BoxConstraints(minHeight: 40),
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
              child: Text(text, textAlign: TextAlign.center,
                  style: body(14.5, weight: FontWeight.w600, color: cc.brand, height: 1.3)),
            ),
          ),
        ),
      ),
    );
  }
}

class _DashedPill extends CustomPainter {
  _DashedPill({required this.color});
  final Color color;

  @override
  void paint(Canvas canvas, Size size) {
    final r = RRect.fromRectAndRadius(Offset.zero & size, Radius.circular(size.height.clamp(0, 22).toDouble()));
    final path = Path()..addRRect(r.deflate(0.6));
    final p = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1.2
      ..color = color;
    for (final m in path.computeMetrics()) {
      var d = 0.0;
      while (d < m.length) {
        canvas.drawPath(m.extractPath(d, d + 5), p);
        d += 9;
      }
    }
  }

  @override
  bool shouldRepaint(_DashedPill old) => old.color != color;
}
