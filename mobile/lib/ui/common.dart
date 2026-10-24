import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../i18n.dart';
import '../models.dart';
import '../state.dart';
import '../theme.dart';
import '../util.dart';

enum ChipTone { neutral, brand, haldi, danger }

/// Rounded pill, like the web `.chip`.
class CCChip extends StatelessWidget {
  const CCChip(this.text, {super.key, this.tone = ChipTone.neutral, this.icon});
  final String text;
  final ChipTone tone;
  final IconData? icon;

  @override
  Widget build(BuildContext context) {
    final cc = CC.of(context);
    final (bg, fg) = switch (tone) {
      ChipTone.brand => (cc.brandSoft, cc.brand2),
      ChipTone.haldi => (cc.haldiSoft, cc.ink),
      ChipTone.danger => (cc.sindoorSoft, cc.sindoor),
      ChipTone.neutral => (cc.surface2, cc.ink),
    };
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
      decoration: BoxDecoration(color: bg, borderRadius: BorderRadius.circular(999)),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          if (icon != null) ...[Icon(icon, size: 14, color: fg), const SizedBox(width: 6)],
          Flexible(
            child: Text(
              text,
              style: body(14, weight: FontWeight.w600, color: fg, height: 1.3),
            ),
          ),
        ],
      ),
    );
  }
}

/// Initials on a palette colour (web `.avatar`).
class Avatar extends StatelessWidget {
  const Avatar({super.key, required this.name, required this.seed, this.size = 52});
  final String name;
  final String seed;
  final double size;

  @override
  Widget build(BuildContext context) {
    final c = avatarColor(seed);
    return Container(
      width: size,
      height: size,
      alignment: Alignment.center,
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(size * 0.31),
        gradient: LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [Color.lerp(c, Colors.white, 0.12)!, c],
        ),
      ),
      child: Text(initials(name), style: display(size * 0.36, color: Colors.white, height: 1)),
    );
  }
}

/// Scales down a touch while pressed, for a tactile feel.
class Pressable extends StatefulWidget {
  const Pressable({super.key, required this.child, this.onTap, this.scale = 0.97, this.haptic = true});
  final Widget child;
  final VoidCallback? onTap;
  final double scale;
  final bool haptic;

  @override
  State<Pressable> createState() => _PressableState();
}

class _PressableState extends State<Pressable> {
  bool _down = false;

  @override
  Widget build(BuildContext context) {
    final enabled = widget.onTap != null;
    return GestureDetector(
      behavior: HitTestBehavior.opaque,
      onTapDown: enabled ? (_) => setState(() => _down = true) : null,
      onTapCancel: enabled ? () => setState(() => _down = false) : null,
      onTapUp: enabled ? (_) => setState(() => _down = false) : null,
      onTap: enabled
          ? () {
              if (widget.haptic) HapticFeedback.selectionClick();
              widget.onTap!();
            }
          : null,
      child: AnimatedScale(
        scale: _down ? widget.scale : 1,
        duration: const Duration(milliseconds: 120),
        curve: Curves.easeOut,
        child: widget.child,
      ),
    );
  }
}

/// Fades and lifts its child in once, when first built.
class EntryAnimation extends StatefulWidget {
  const EntryAnimation({super.key, required this.child, this.delay = Duration.zero, this.offset = 18});
  final Widget child;
  final Duration delay;
  final double offset;

  @override
  State<EntryAnimation> createState() => _EntryAnimationState();
}

class _EntryAnimationState extends State<EntryAnimation> with SingleTickerProviderStateMixin {
  late final AnimationController _c = AnimationController(vsync: this, duration: const Duration(milliseconds: 420));
  late final Animation<double> _a = CurvedAnimation(parent: _c, curve: Curves.easeOutCubic);

  @override
  void initState() {
    super.initState();
    if (widget.delay == Duration.zero) {
      _c.forward();
    } else {
      Future.delayed(widget.delay, () {
        if (mounted) _c.forward();
      });
    }
  }

  @override
  void dispose() {
    _c.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: _a,
      child: widget.child,
      builder: (context, child) => Opacity(
        opacity: _a.value,
        child: Transform.translate(offset: Offset(0, (1 - _a.value) * widget.offset), child: child),
      ),
    );
  }
}

/// "Sunaiye" / "Rokein" button that reads [text] aloud with flutter_tts.
class ReadAloudButton extends StatelessWidget {
  const ReadAloudButton({super.key, required this.id, required this.text, required this.voiceLang});
  final String id;
  final String text;
  final Lang voiceLang;

  @override
  Widget build(BuildContext context) {
    final state = AppScope.of(context);
    final cc = CC.of(context);
    return ValueListenableBuilder<String?>(
      valueListenable: state.voice.speaking,
      builder: (context, speaking, _) {
        final on = speaking == id;
        return TextButton.icon(
          onPressed: () => on ? state.voice.stopSpeaking() : state.voice.speak(text, voiceLang, id: id),
          style: TextButton.styleFrom(foregroundColor: on ? cc.brand2 : cc.ink2),
          icon: Icon(on ? LucideIcons.square : LucideIcons.volume2, size: on ? 16 : 18),
          label: Text(t(state.lang, on ? K.stopReading : K.readAloud)),
        );
      },
    );
  }
}

/// Card surface with the web's border + radius.
class Panel extends StatelessWidget {
  const Panel({super.key, required this.child, this.padding = const EdgeInsets.all(20), this.color});
  final Widget child;
  final EdgeInsets padding;
  final Color? color;

  @override
  Widget build(BuildContext context) {
    final cc = CC.of(context);
    return Container(
      width: double.infinity,
      padding: padding,
      decoration: BoxDecoration(
        color: color ?? cc.surface,
        borderRadius: BorderRadius.circular(rLg),
        border: Border.all(color: cc.line),
      ),
      child: child,
    );
  }
}

/// Page title + subtitle (web `.page-head`).
class PageHead extends StatelessWidget {
  const PageHead({super.key, required this.title, this.sub});
  final String title;
  final String? sub;

  @override
  Widget build(BuildContext context) {
    final cc = CC.of(context);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(title, style: display(30, color: cc.ink)),
        if (sub != null) ...[const SizedBox(height: 8), Text(sub!, style: body(15.5, color: cc.ink2))],
      ],
    );
  }
}

/// Small grey disclaimer line (web `.notice`).
class Notice extends StatelessWidget {
  const Notice(this.text, {super.key, this.align = TextAlign.center});
  final String text;
  final TextAlign align;

  @override
  Widget build(BuildContext context) {
    return Text(
      text,
      textAlign: align,
      style: body(13, color: CC.of(context).ink3),
    );
  }
}
