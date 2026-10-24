import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';
import 'package:url_launcher/url_launcher.dart';

import '../i18n.dart';
import '../models.dart';
import '../state.dart';
import '../strings_mobile.dart';
import '../theme.dart';
import 'common.dart';

/// Opens the phone dialer with [number] filled in (the user presses call).
Future<void> callNumber(BuildContext context, String number, Lang lang) async {
  final digits = number.replaceAll(RegExp(r'[^0-9+]'), '');
  HapticFeedback.heavyImpact();
  var ok = false;
  try {
    ok = await launchUrl(Uri(scheme: 'tel', path: digits));
  } catch (_) {
    ok = false;
  }
  if (!ok && context.mounted) {
    ScaffoldMessenger.maybeOf(context)?.showSnackBar(SnackBar(content: Text(tm(lang, M.callFailed, {'n': number}))));
  }
}

/// Full-screen, impossible to miss. No booking, no caregivers: only the call
/// for help (web EmergencyTakeover.tsx).
Future<void> openEmergency(BuildContext context, EmergencyMsg msg) {
  HapticFeedback.heavyImpact();
  return Navigator.of(context, rootNavigator: true).push(
    PageRouteBuilder<void>(
      fullscreenDialog: true,
      opaque: true,
      transitionDuration: const Duration(milliseconds: 420),
      reverseTransitionDuration: const Duration(milliseconds: 280),
      pageBuilder: (context, _, _) => EmergencyTakeover(msg: msg),
      transitionsBuilder: (context, anim, _, child) {
        final curved = CurvedAnimation(parent: anim, curve: Curves.easeOutCubic, reverseCurve: Curves.easeInCubic);
        return FadeTransition(
          opacity: curved,
          child: SlideTransition(
            position: Tween(begin: const Offset(0, 0.08), end: Offset.zero).animate(curved),
            child: child,
          ),
        );
      },
    ),
  );
}

class EmergencyTakeover extends StatelessWidget {
  const EmergencyTakeover({super.key, required this.msg});
  final EmergencyMsg msg;

  /// API numbers (except 112) plus 102 and 108 if the API left them out.
  List<(String number, String label)> _otherNumbers(Lang voiceLang) {
    final out = <(String, String)>[];
    final seen = <String>{'112'};
    for (final n in msg.res.trace.emergency?.numbers ?? const <EmergencyNumber>[]) {
      if (n.number.isEmpty || !seen.add(n.number)) continue;
      out.add((n.number, n.labelLocal));
    }
    for (final n in LabelsResponse.fallback.emergencyNumbers) {
      if (!seen.add(n.number)) continue;
      out.add((n.number, voiceLang == Lang.en ? n.label : n.labelHi));
    }
    return out;
  }

  @override
  Widget build(BuildContext context) {
    final state = AppScope.of(context);
    final lang = state.lang;
    final res = msg.res;
    final em = res.trace.emergency;
    final others = _otherNumbers(res.trace.language);
    final flags = res.trace.redFlags;
    final steps = em?.stepsLocal ?? const <String>[];
    const white = Colors.white;

    Widget block(String title, List<Widget> children) => Container(
      width: double.infinity,
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(color: Colors.black.withValues(alpha: 0.16), borderRadius: BorderRadius.circular(rLg)),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            title,
            style: display(20, weight: FontWeight.w700, color: white),
          ),
          const SizedBox(height: 10),
          ...children,
        ],
      ),
    );

    return AnnotatedRegion<SystemUiOverlayStyle>(
      value: SystemUiOverlayStyle.light.copyWith(
        statusBarColor: Colors.transparent,
        systemNavigationBarColor: CC.sosScreen,
        systemNavigationBarIconBrightness: Brightness.light,
      ),
      // Leaving is deliberate: only the "Wapas" button goes back, not a stray
      // back gesture.
      child: PopScope(
        canPop: false,
        child: Scaffold(
          backgroundColor: CC.sosScreen,
          body: Container(
            decoration: const BoxDecoration(
              gradient: LinearGradient(
                begin: Alignment.topCenter,
                end: Alignment.bottomCenter,
                colors: [Color(0xFFC0281E), CC.sosScreen, Color(0xFFA51E16)],
              ),
            ),
            child: SafeArea(
              child: ListView(
                padding: const EdgeInsets.fromLTRB(18, 16, 18, 28),
                children: [
                  Row(
                    children: [
                      Expanded(
                        child: Align(
                          alignment: Alignment.centerLeft,
                          child: Container(
                            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 7),
                            decoration: BoxDecoration(
                              color: Colors.black.withValues(alpha: 0.2),
                              borderRadius: BorderRadius.circular(999),
                            ),
                            child: Row(
                              mainAxisSize: MainAxisSize.min,
                              children: [
                                const Icon(LucideIcons.triangleAlert, size: 17, color: white),
                                const SizedBox(width: 8),
                                Flexible(
                                  child: Text(
                                    t(lang, K.sosTag),
                                    maxLines: 1,
                                    overflow: TextOverflow.ellipsis,
                                    style: body(14.5, weight: FontWeight.w700, color: white, height: 1.2),
                                  ),
                                ),
                              ],
                            ),
                          ),
                        ),
                      ),
                      const SizedBox(width: 10),
                      OutlinedButton.icon(
                        onPressed: () => Navigator.of(context).pop(),
                        style: OutlinedButton.styleFrom(
                          foregroundColor: white,
                          side: BorderSide(color: white.withValues(alpha: 0.6), width: 1.5),
                          minimumSize: const Size(48, 44),
                          padding: const EdgeInsets.symmetric(horizontal: 14),
                        ),
                        icon: const Icon(LucideIcons.arrowLeft, size: 18),
                        label: Text(t(lang, K.back), semanticsLabel: t(lang, K.sosBack)),
                      ),
                    ],
                  ),
                  const SizedBox(height: 22),
                  EntryAnimation(
                    child: Text(
                      em?.titleLocal ?? t(lang, K.sosPageTitle),
                      style: display(38, color: white, height: 1.08),
                    ),
                  ),
                  const SizedBox(height: 26),
                  _BigCallButton(
                    label: t(lang, K.callNow),
                    semantics: t(lang, K.sosNow),
                    onTap: () => callNumber(context, '112', lang),
                  ),
                  if (others.isNotEmpty) ...[
                    const SizedBox(height: 18),
                    LayoutBuilder(
                      builder: (context, c) {
                        final w = (c.maxWidth - 10) / 2;
                        return Wrap(
                          spacing: 10,
                          runSpacing: 10,
                          children: [
                            for (final (number, label) in others)
                              SizedBox(
                                width: w,
                                child: _SmallCall(
                                  number: number,
                                  label: label,
                                  onTap: () => callNumber(context, number, lang),
                                ),
                              ),
                          ],
                        );
                      },
                    ),
                  ],
                  if (steps.isNotEmpty) ...[
                    const SizedBox(height: 18),
                    block(t(lang, K.sosSteps), [
                      for (var i = 0; i < steps.length; i++)
                        Padding(
                          padding: const EdgeInsets.only(bottom: 8),
                          child: Row(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Container(
                                width: 26,
                                height: 26,
                                alignment: Alignment.center,
                                decoration: BoxDecoration(color: white.withValues(alpha: 0.2), shape: BoxShape.circle),
                                child: Text('${i + 1}', style: display(15, color: white, height: 1)),
                              ),
                              const SizedBox(width: 12),
                              Expanded(
                                child: Text(steps[i], style: body(17, color: white, height: 1.4)),
                              ),
                            ],
                          ),
                        ),
                    ]),
                  ],
                  if (flags.isNotEmpty) ...[
                    const SizedBox(height: 18),
                    block(t(lang, K.sosSeen), [
                      for (final f in flags)
                        Padding(
                          padding: const EdgeInsets.only(bottom: 10),
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                f.labelLocal,
                                style: body(17, weight: FontWeight.w700, color: white, height: 1.3),
                              ),
                              if (f.evidence.isNotEmpty)
                                Text('"${f.evidence}"', style: body(14.5, color: white.withValues(alpha: 0.85))),
                            ],
                          ),
                        ),
                      Text(
                        '${t(lang, K.sosYouSaid)}: "${msg.userText}"',
                        style: body(14, color: white.withValues(alpha: 0.85)),
                      ),
                    ]),
                  ],
                  const SizedBox(height: 22),
                  Align(
                    alignment: Alignment.centerLeft,
                    child: OutlinedButton.icon(
                      onPressed: () {
                        state.newCheck();
                        Navigator.of(context).pop();
                      },
                      style: OutlinedButton.styleFrom(
                        foregroundColor: white,
                        side: BorderSide(color: white.withValues(alpha: 0.6), width: 1.5),
                      ),
                      icon: const Icon(LucideIcons.rotateCcw, size: 18),
                      label: Text(t(lang, K.newCheck)),
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}

/// The huge white "112" pill with a pulsing beacon ring.
class _BigCallButton extends StatefulWidget {
  const _BigCallButton({required this.label, required this.semantics, required this.onTap});
  final String label;
  final String semantics;
  final VoidCallback onTap;

  @override
  State<_BigCallButton> createState() => _BigCallButtonState();
}

class _BigCallButtonState extends State<_BigCallButton> with SingleTickerProviderStateMixin {
  late final AnimationController _c = AnimationController(vsync: this, duration: const Duration(milliseconds: 1800))
    ..repeat();

  @override
  void dispose() {
    _c.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Semantics(
      button: true,
      label: widget.semantics,
      child: Pressable(
        onTap: widget.onTap,
        haptic: false,
        child: AnimatedBuilder(
          animation: _c,
          builder: (context, child) {
            final v = Curves.easeOut.transform(_c.value);
            return Container(
              height: 104,
              decoration: BoxDecoration(
                color: Colors.white,
                borderRadius: BorderRadius.circular(999),
                boxShadow: [
                  BoxShadow(
                    color: Colors.white.withValues(alpha: 0.55 * (1 - v)),
                    spreadRadius: 24 * v,
                  ),
                  BoxShadow(color: Colors.black.withValues(alpha: 0.18), blurRadius: 24, offset: const Offset(0, 10)),
                ],
              ),
              child: child,
            );
          },
          child: Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              const Icon(LucideIcons.phone, size: 38, color: CC.sosDeep),
              const SizedBox(width: 18),
              Flexible(
                child: FittedBox(
                  fit: BoxFit.scaleDown,
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text('112', style: display(48, color: CC.sosDeep, height: 0.95).copyWith(letterSpacing: 1)),
                      Text(
                        widget.label,
                        style: display(17, weight: FontWeight.w700, color: CC.sosDeep, height: 1.1),
                      ),
                    ],
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _SmallCall extends StatelessWidget {
  const _SmallCall({required this.number, required this.label, required this.onTap});
  final String number;
  final String label;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Pressable(
      onTap: onTap,
      child: Container(
        constraints: const BoxConstraints(minHeight: 86),
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
        decoration: BoxDecoration(
          color: Colors.black.withValues(alpha: 0.18),
          borderRadius: BorderRadius.circular(rLg),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Expanded(
                  child: FittedBox(
                    alignment: Alignment.centerLeft,
                    fit: BoxFit.scaleDown,
                    child: Text(
                      number,
                      style: display(26, color: Colors.white, height: 1.1).copyWith(letterSpacing: 0.5),
                    ),
                  ),
                ),
                const Icon(LucideIcons.phone, size: 18, color: Colors.white),
              ],
            ),
            const SizedBox(height: 2),
            Text(label, style: body(13.5, color: Colors.white.withValues(alpha: 0.92), height: 1.3)),
          ],
        ),
      ),
    );
  }
}
