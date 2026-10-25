import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import 'i18n.dart';
import 'models.dart';
import 'screens/bookings_screen.dart';
import 'screens/check_screen.dart';
import 'screens/how_screen.dart';
import 'screens/settings_screen.dart';
import 'screens/sos_screen.dart';
import 'state.dart';
import 'strings_mobile.dart';
import 'theme.dart';
import 'ui/brand.dart';
import 'ui/emergency.dart';
import 'ui/history_sheet.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  final state = AppState();
  state.load();
  runApp(CareCompassApp(state: state));
}

class CareCompassApp extends StatelessWidget {
  const CareCompassApp({super.key, required this.state});
  final AppState state;

  @override
  Widget build(BuildContext context) {
    return AppScope(
      state: state,
      child: ListenableBuilder(
        listenable: state,
        builder: (context, _) => MaterialApp(
          title: 'Raahat',
          debugShowCheckedModeBanner: false,
          theme: buildTheme(Brightness.light),
          darkTheme: buildTheme(Brightness.dark),
          themeMode: switch (state.theme) {
            ThemePref.auto => ThemeMode.system,
            ThemePref.light => ThemeMode.light,
            ThemePref.dark => ThemeMode.dark,
          },
          builder: (context, child) {
            final mq = MediaQuery.of(context);
            if (!state.largeText) return child!;
            final base = mq.textScaler.scale(16) / 16;
            return MediaQuery(
              data: mq.copyWith(textScaler: TextScaler.linear((base * 1.18).clamp(1.0, 2.0))),
              child: child!,
            );
          },
          home: const Shell(),
        ),
      ),
    );
  }
}

/// Phone layout from the web app: top bar, the current view, and a bottom
/// tab bar with a raised SOS button in the middle. The ☰ in the top bar
/// opens the chat sidebar on every tab.
class Shell extends StatelessWidget {
  const Shell({super.key});

  static const _pages = [CheckScreen(), BookingsScreen(), SosScreen(), HowScreen(), SettingsScreen()];

  @override
  Widget build(BuildContext context) {
    final state = AppScope.of(context);
    final cc = CC.of(context);
    final dark = Theme.of(context).brightness == Brightness.dark;

    return AnnotatedRegion<SystemUiOverlayStyle>(
      value: (dark ? SystemUiOverlayStyle.light : SystemUiOverlayStyle.dark).copyWith(
        statusBarColor: Colors.transparent,
        systemNavigationBarColor: cc.surface,
        systemNavigationBarIconBrightness: dark ? Brightness.light : Brightness.dark,
      ),
      child: PopScope(
        canPop: state.tab == 0,
        onPopInvokedWithResult: (didPop, _) {
          if (!didPop) state.setTab(0);
        },
        child: Scaffold(
          backgroundColor: cc.bg,
          drawer: const ChatDrawer(),
          body: Column(
            children: [
              const _TopBar(),
              if (state.backend == Backend.bad) const _OfflineBanner(),
              Expanded(
                child: Stack(
                  children: [
                    for (var i = 0; i < _pages.length; i++) _FadePage(active: state.tab == i, child: _pages[i]),
                  ],
                ),
              ),
            ],
          ),
          bottomNavigationBar: const _BottomNav(),
        ),
      ),
    );
  }
}

/// Keeps every tab alive (so the consult and draft survive tab switches) and
/// cross-fades between them.
class _FadePage extends StatefulWidget {
  const _FadePage({required this.active, required this.child});
  final bool active;
  final Widget child;

  @override
  State<_FadePage> createState() => _FadePageState();
}

class _FadePageState extends State<_FadePage> {
  late bool _offstage = !widget.active;

  @override
  void didUpdateWidget(_FadePage old) {
    super.didUpdateWidget(old);
    if (widget.active) _offstage = false;
  }

  @override
  Widget build(BuildContext context) {
    return Offstage(
      offstage: _offstage,
      child: IgnorePointer(
        ignoring: !widget.active,
        child: AnimatedOpacity(
          opacity: widget.active ? 1 : 0,
          duration: const Duration(milliseconds: 220),
          curve: Curves.easeOut,
          onEnd: () {
            if (!widget.active && mounted) setState(() => _offstage = true);
          },
          child: AnimatedSlide(
            offset: widget.active ? Offset.zero : const Offset(0, 0.015),
            duration: const Duration(milliseconds: 220),
            curve: Curves.easeOut,
            // Hidden tabs stop their own animations.
            child: TickerMode(enabled: widget.active, child: widget.child),
          ),
        ),
      ),
    );
  }
}

class _TopBar extends StatelessWidget {
  const _TopBar();

  @override
  Widget build(BuildContext context) {
    final state = AppScope.of(context);
    final cc = CC.of(context);
    final lang = state.lang;
    const order = [Lang.hi, Lang.hinglish, Lang.en];
    final next = order[(order.indexOf(lang) + 1) % order.length];

    // Labels here grow with large text only up to x1.2, so the name, the
    // language and 112 stay on one line on a 360 dp phone.
    return MediaQuery.withClampedTextScaling(
      maxScaleFactor: 1.2,
      child: Container(
        padding: EdgeInsets.fromLTRB(6, MediaQuery.paddingOf(context).top + 8, 12, 8),
        decoration: BoxDecoration(
          color: cc.bg,
          border: Border(bottom: BorderSide(color: cc.line)),
        ),
        child: Row(
          children: [
            IconButton(
              tooltip: tm(lang, M.chats),
              onPressed: () => Scaffold.of(context).openDrawer(),
              constraints: const BoxConstraints.tightFor(width: 42, height: 42),
              padding: EdgeInsets.zero,
              icon: Icon(LucideIcons.menu, size: 22, color: cc.ink),
            ),
            const SizedBox(width: 4),
            Expanded(
              child: GestureDetector(
                onTap: () => state.setTab(0),
                // when the bar is tight the logo tile steps aside; the name stays
                child: LayoutBuilder(
                  builder: (context, c) => Align(
                    alignment: Alignment.centerLeft,
                    child: FittedBox(
                      fit: BoxFit.scaleDown,
                      child: Row(
                        children: [
                          if (c.maxWidth >= 100) ...[const BrandMark(size: 32), const SizedBox(width: 10)],
                          const BrandWordmark(size: 21),
                        ],
                      ),
                    ),
                  ),
                ),
              ),
            ),
            const SizedBox(width: 8),
            Semantics(
              button: true,
              label: '${t(lang, K.setLang)}: ${langLabel[lang]}',
              child: InkWell(
                borderRadius: BorderRadius.circular(999),
                onTap: () => state.setLang(next),
                child: Container(
                  height: 44,
                  // the full language name; it shrinks rather than overflow
                  // if a phone's font runs wide
                  constraints: const BoxConstraints(maxWidth: 140),
                  padding: const EdgeInsets.symmetric(horizontal: 13),
                  decoration: BoxDecoration(
                    color: cc.surface,
                    borderRadius: BorderRadius.circular(999),
                    border: Border.all(color: cc.line),
                  ),
                  child: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Icon(LucideIcons.languages, size: 15, color: cc.ink2),
                      const SizedBox(width: 6),
                      Flexible(
                        child: FittedBox(
                          fit: BoxFit.scaleDown,
                          child: Text(
                            langShort[lang]!,
                            style: dv(body(14, weight: FontWeight.w700, color: cc.ink, height: 1.2), langShort[lang]!),
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ),
            const SizedBox(width: 8),
            Semantics(
              button: true,
              label: t(lang, K.sosNow),
              child: InkWell(
                borderRadius: BorderRadius.circular(999),
                onTap: () => callNumber(context, '112', lang),
                child: Container(
                  height: 44,
                  padding: const EdgeInsets.symmetric(horizontal: 14),
                  decoration: BoxDecoration(color: CC.sosFixed, borderRadius: BorderRadius.circular(999)),
                  child: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      const Icon(LucideIcons.phone, size: 15, color: Colors.white),
                      const SizedBox(width: 6),
                      Text(
                        '112',
                        style: body(15, weight: FontWeight.w700, color: Colors.white, height: 1.2),
                      ),
                    ],
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

class _OfflineBanner extends StatelessWidget {
  const _OfflineBanner();

  @override
  Widget build(BuildContext context) {
    final cc = CC.of(context);
    final lang = AppScope.of(context).lang;
    return Container(
      width: double.infinity,
      color: cc.sindoorSoft,
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      child: Row(
        children: [
          Container(
            width: 8,
            height: 8,
            decoration: const BoxDecoration(color: CC.sosFixed, shape: BoxShape.circle),
          ),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              t(lang, K.serviceBad),
              style: body(13.5, weight: FontWeight.w600, color: cc.ink),
            ),
          ),
        ],
      ),
    );
  }
}

class _BottomNav extends StatelessWidget {
  const _BottomNav();

  static const _items = [
    (LucideIcons.stethoscope, K.navCheck),
    (LucideIcons.calendarCheck, K.navBookings),
    (LucideIcons.siren, K.navSosShort),
    (LucideIcons.info, K.navHowShort),
    (LucideIcons.settings, K.navSettings),
  ];

  @override
  Widget build(BuildContext context) {
    final state = AppScope.of(context);
    final cc = CC.of(context);
    final lang = state.lang;
    final bottom = MediaQuery.paddingOf(context).bottom;

    return Container(
      height: 68 + bottom,
      padding: EdgeInsets.only(bottom: bottom, left: 4, right: 4),
      decoration: BoxDecoration(
        color: cc.surface,
        border: Border(top: BorderSide(color: cc.line)),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.end,
        children: [
          for (var i = 0; i < _items.length; i++)
            Expanded(
              child: i == 2
                  ? _SosTab(label: t(lang, _items[i].$2), active: state.tab == 2, onTap: () => state.setTab(2))
                  : _Tab(
                      icon: _items[i].$1,
                      label: t(lang, _items[i].$2),
                      active: state.tab == i,
                      badge: i == 1 && state.bookings.isNotEmpty ? state.bookings.length : null,
                      onTap: () {
                        HapticFeedback.selectionClick();
                        state.setTab(i);
                      },
                    ),
            ),
        ],
      ),
    );
  }
}

class _Tab extends StatelessWidget {
  const _Tab({required this.icon, required this.label, required this.active, required this.onTap, this.badge});
  final IconData icon;
  final String label;
  final bool active;
  final VoidCallback onTap;
  final int? badge;

  @override
  Widget build(BuildContext context) {
    final cc = CC.of(context);
    final color = active ? cc.brand2 : cc.ink3;
    return Semantics(
      selected: active,
      button: true,
      label: label,
      child: InkResponse(
        onTap: onTap,
        radius: 36,
        child: SizedBox(
          height: 68,
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              AnimatedContainer(
                duration: const Duration(milliseconds: 220),
                curve: Curves.easeOut,
                width: active ? 54 : 40,
                height: 30,
                decoration: BoxDecoration(
                  color: active ? cc.brandSoft : Colors.transparent,
                  borderRadius: BorderRadius.circular(999),
                ),
                child: Badge(
                  isLabelVisible: badge != null,
                  label: Text('${badge ?? ''}'),
                  backgroundColor: cc.haldi,
                  textColor: cc.haldiInk,
                  offset: const Offset(10, -6),
                  child: Icon(icon, size: 22, color: color),
                ),
              ),
              const SizedBox(height: 3),
              // large text on a narrow phone: the label shrinks to fit, never cut off
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 2),
                child: FittedBox(
                  fit: BoxFit.scaleDown,
                  child: Text(
                    label,
                    maxLines: 1,
                    style: body(11.5, weight: FontWeight.w700, color: color, height: 1.2),
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

class _SosTab extends StatelessWidget {
  const _SosTab({required this.label, required this.active, required this.onTap});
  final String label;
  final bool active;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final cc = CC.of(context);
    return Semantics(
      selected: active,
      button: true,
      label: label,
      child: GestureDetector(
        behavior: HitTestBehavior.opaque,
        onTap: () {
          HapticFeedback.mediumImpact();
          onTap();
        },
        child: SizedBox(
          height: 68,
          child: Stack(
            clipBehavior: Clip.none,
            alignment: Alignment.topCenter,
            children: [
              // Raised orb: sits 24 px above the bar, like the web phone view.
              Positioned(
                top: -24,
                child: AnimatedScale(
                  scale: active ? 1.06 : 1,
                  duration: const Duration(milliseconds: 220),
                  child: Container(
                    width: 62,
                    height: 62,
                    decoration: BoxDecoration(
                      color: CC.sosFixed,
                      shape: BoxShape.circle,
                      border: Border.all(color: cc.surface, width: 4),
                      boxShadow: [
                        BoxShadow(
                          color: cc.sindoor.withValues(alpha: 0.45),
                          blurRadius: 18,
                          offset: const Offset(0, 6),
                        ),
                      ],
                    ),
                    child: const Icon(LucideIcons.siren, size: 26, color: Colors.white),
                  ),
                ),
              ),
              Positioned(
                bottom: 10,
                child: Text(
                  label,
                  style: body(11.5, weight: FontWeight.w700, color: cc.sindoor, height: 1.2),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
