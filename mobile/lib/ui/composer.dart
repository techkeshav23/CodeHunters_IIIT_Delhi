import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../i18n.dart';
import '../models.dart';
import '../state.dart';
import '../strings_mobile.dart';
import '../theme.dart';

/// Text box + mic + send (web Composer.tsx). Dictation fills the box so the
/// user can fix it before sending.
///
/// [hero] is the start-screen layout: one big mic button with the text box
/// under it. Otherwise it is the compact bar docked above the tab bar.
class Composer extends StatefulWidget {
  const Composer({
    super.key,
    required this.controller,
    required this.focusNode,
    required this.onSend,
    this.hero = false,
  });
  final TextEditingController controller;
  final FocusNode focusNode;
  final void Function(String text, bool usedVoice) onSend;
  final bool hero;

  @override
  State<Composer> createState() => _ComposerState();
}

class _ComposerState extends State<Composer> with SingleTickerProviderStateMixin {
  bool _usedVoice = false;
  late final AnimationController _ring = AnimationController(vsync: this, duration: const Duration(milliseconds: 1400));

  @override
  void initState() {
    super.initState();
    widget.controller.addListener(_onChange);
    widget.focusNode.addListener(_onChange);
  }

  @override
  void dispose() {
    widget.controller.removeListener(_onChange);
    widget.focusNode.removeListener(_onChange);
    _ring.dispose();
    super.dispose();
  }

  void _onChange() {
    if (mounted) setState(() {});
  }

  void _send() {
    final state = AppScope.read(context);
    final text = widget.controller.text.trim();
    if (text.isEmpty || state.busy) return;
    state.voice.stopListening();
    HapticFeedback.lightImpact();
    widget.onSend(text, _usedVoice);
    _usedVoice = false;
  }

  Future<void> _toggleMic() async {
    final state = AppScope.read(context);
    final voice = state.voice;
    if (voice.listening.value) {
      await voice.stopListening();
      return;
    }
    HapticFeedback.mediumImpact();
    final ok = await voice.startListening(state.lang, (text, isFinal) {
      widget.controller.value = TextEditingValue(
        text: text,
        selection: TextSelection.collapsed(offset: text.length),
      );
    });
    if (!mounted) return;
    if (ok) {
      _usedVoice = true;
    } else {
      ScaffoldMessenger.maybeOf(context)?.showSnackBar(SnackBar(content: Text(tm(state.lang, M.voiceUnavailable))));
    }
  }

  @override
  Widget build(BuildContext context) {
    final state = AppScope.of(context);
    return ValueListenableBuilder<bool>(
      valueListenable: state.voice.listening,
      builder: (context, listening, _) {
        if (listening && !_ring.isAnimating) _ring.repeat();
        if (!listening && _ring.isAnimating) _ring.stop();
        return widget.hero ? _heroLayout(context, state, listening) : _dockLayout(context, state, listening);
      },
    );
  }

  Widget _field(BuildContext context, AppState state, bool listening, {required double size}) {
    final cc = CC.of(context);
    final lang = state.lang;
    return TextField(
      controller: widget.controller,
      focusNode: widget.focusNode,
      minLines: 1,
      maxLines: 5,
      textInputAction: TextInputAction.send,
      textCapitalization: TextCapitalization.sentences,
      onSubmitted: (_) => _send(),
      onTapOutside: (_) => widget.focusNode.unfocus(),
      style: body(size, color: cc.ink, height: 1.35),
      decoration: InputDecoration(
        isDense: true,
        border: InputBorder.none,
        contentPadding: const EdgeInsets.symmetric(vertical: 12),
        hintText: listening ? t(lang, K.listening) : t(lang, state.answering ? K.placeholderAnswer : K.placeholder),
        hintStyle: body(size, color: listening ? cc.sindoor : cc.ink3),
      ),
    );
  }

  Widget _sendButton(BuildContext context, AppState state) {
    final cc = CC.of(context);
    final canSend = widget.controller.text.trim().isNotEmpty && !state.busy;
    return AnimatedContainer(
      duration: const Duration(milliseconds: 200),
      width: 48,
      height: 48,
      decoration: BoxDecoration(color: canSend ? cc.brand : cc.surface3, shape: BoxShape.circle),
      child: IconButton(
        tooltip: t(state.lang, K.send),
        onPressed: canSend ? _send : null,
        icon: Icon(LucideIcons.sendHorizontal, size: 22, color: canSend ? cc.brandInk : cc.ink3),
      ),
    );
  }

  BoxDecoration _boxDecoration(CC cc, bool listening) => BoxDecoration(
    color: cc.surface,
    borderRadius: BorderRadius.circular(rXl),
    border: Border.all(color: listening ? cc.sindoor : (widget.focusNode.hasFocus ? cc.brand : cc.line), width: 1.5),
    boxShadow: cc.shadow,
  );

  Widget _dockLayout(BuildContext context, AppState state, bool listening) {
    final cc = CC.of(context);
    final lang = state.lang;
    return Container(
      padding: const EdgeInsets.fromLTRB(12, 8, 12, 0),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.bottomCenter,
          end: Alignment.topCenter,
          colors: [cc.bg, cc.bg, cc.bg.withValues(alpha: 0)],
          stops: const [0, 0.7, 1],
        ),
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          AnimatedContainer(
            duration: const Duration(milliseconds: 200),
            padding: const EdgeInsets.fromLTRB(16, 6, 6, 6),
            decoration: _boxDecoration(cc, listening),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.end,
              children: [
                Expanded(child: _field(context, state, listening, size: 17)),
                const SizedBox(width: 6),
                _MicButton(listening: listening, ring: _ring, onTap: _toggleMic, lang: lang, size: 48),
                const SizedBox(width: 8),
                _sendButton(context, state),
              ],
            ),
          ),
          // Room for the raised SOS button of the tab bar below. While
          // listening, the box border and hint turn red instead of a note.
          const SizedBox(height: 26),
        ],
      ),
    );
  }

  Widget _heroLayout(BuildContext context, AppState state, bool listening) {
    final cc = CC.of(context);
    final lang = state.lang;
    return Column(
      children: [
        _MicButton(listening: listening, ring: _ring, onTap: _toggleMic, lang: lang, size: 104),
        const SizedBox(height: 12),
        AnimatedSwitcher(
          duration: const Duration(milliseconds: 200),
          child: Text(
            t(lang, listening ? K.listening : K.micStart),
            key: ValueKey(listening),
            textAlign: TextAlign.center,
            style: body(16, weight: FontWeight.w700, color: listening ? cc.sindoor : cc.ink2),
          ),
        ),
        const SizedBox(height: 18),
        AnimatedContainer(
          duration: const Duration(milliseconds: 200),
          padding: const EdgeInsets.fromLTRB(18, 6, 6, 6),
          decoration: _boxDecoration(cc, listening),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.end,
            children: [
              Expanded(child: _field(context, state, listening, size: 17.5)),
              const SizedBox(width: 8),
              _sendButton(context, state),
            ],
          ),
        ),
        const SizedBox(height: 8),
        Row(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(LucideIcons.mapPin, size: 14, color: cc.ink3),
            const SizedBox(width: 5),
            Flexible(
              child: Text(
                state.locationLabel,
                style: body(13, color: cc.ink3),
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
              ),
            ),
          ],
        ),
      ],
    );
  }
}

class _MicButton extends StatelessWidget {
  const _MicButton({
    required this.listening,
    required this.ring,
    required this.onTap,
    required this.lang,
    required this.size,
  });
  final bool listening;
  final AnimationController ring;
  final VoidCallback onTap;
  final Lang lang;
  final double size;

  @override
  Widget build(BuildContext context) {
    final cc = CC.of(context);
    final big = size > 60;
    return Semantics(
      button: true,
      label: t(lang, listening ? K.micStop : K.micStart),
      excludeSemantics: true,
      child: GestureDetector(
        onTap: onTap,
        child: SizedBox.square(
          dimension: size,
          child: Stack(
            clipBehavior: Clip.none,
            alignment: Alignment.center,
            children: [
              if (listening)
                AnimatedBuilder(
                  animation: ring,
                  builder: (context, _) {
                    final v = Curves.easeOut.transform(ring.value);
                    return Transform.scale(
                      scale: 0.9 + 0.45 * v,
                      child: Container(
                        width: size + 8,
                        height: size + 8,
                        decoration: BoxDecoration(
                          shape: BoxShape.circle,
                          border: Border.all(
                            color: cc.sindoor.withValues(alpha: 0.9 * (1 - v)),
                            width: big ? 4 : 3,
                          ),
                        ),
                      ),
                    );
                  },
                ),
              AnimatedContainer(
                duration: const Duration(milliseconds: 220),
                width: size,
                height: size,
                decoration: BoxDecoration(
                  color: listening ? CC.sosFixed : cc.haldi,
                  shape: BoxShape.circle,
                  boxShadow: big
                      ? [
                          BoxShadow(
                            color: (listening ? CC.sosFixed : cc.haldi).withValues(alpha: 0.35),
                            blurRadius: 24,
                            offset: const Offset(0, 10),
                          ),
                        ]
                      : null,
                ),
                child: Icon(
                  listening ? LucideIcons.square : LucideIcons.mic,
                  size: listening ? size * 0.36 : size * 0.46,
                  color: listening ? Colors.white : cc.haldiInk,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
