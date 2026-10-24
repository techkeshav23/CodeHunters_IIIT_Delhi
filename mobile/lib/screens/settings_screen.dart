import 'package:flutter/material.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../config.dart';
import '../i18n.dart';
import '../models.dart';
import '../state.dart';
import '../strings_mobile.dart';
import '../theme.dart';
import '../ui/common.dart';

/// Language, text size, read-aloud, theme, location, API base (read-only).
class SettingsScreen extends StatelessWidget {
  const SettingsScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final state = AppScope.of(context);
    final lang = state.lang;
    final cc = CC.of(context);

    final statusKey = switch (state.backend) {
      Backend.ok => K.serviceOk,
      Backend.bad => K.serviceBad,
      Backend.wait => K.serviceWait,
    };
    final statusColor = switch (state.backend) {
      Backend.ok => cc.ok,
      Backend.bad => cc.sos,
      Backend.wait => cc.ink3,
    };

    return ListView(
      padding: const EdgeInsets.fromLTRB(16, 20, 16, 24),
      children: [
        PageHead(title: t(lang, K.settingsTitle)),
        const SizedBox(height: 20),
        Panel(
          padding: const EdgeInsets.fromLTRB(18, 6, 18, 6),
          child: Column(
            children: [
              _Setting(
                title: t(lang, K.setLang),
                sub: t(lang, K.setLangSub),
                child: _Segmented<Lang>(
                  value: lang,
                  options: [
                    for (final l in [Lang.hinglish, Lang.hi, Lang.en]) (l, langLabel[l]!),
                  ],
                  onChanged: state.setLang,
                ),
              ),
              _Setting(
                title: t(lang, K.setText),
                sub: t(lang, K.setTextSub),
                child: _Segmented<bool>(
                  value: state.largeText,
                  options: [(false, t(lang, K.textNormal)), (true, t(lang, K.textLarge))],
                  onChanged: state.setLargeText,
                ),
              ),
              _Setting(
                title: t(lang, K.setRead),
                sub: t(lang, K.setReadSub),
                child: _Segmented<bool>(
                  value: state.autoRead,
                  options: [(true, t(lang, K.on)), (false, t(lang, K.off))],
                  onChanged: state.setAutoRead,
                ),
              ),
              _Setting(
                title: t(lang, K.setTheme),
                child: _Segmented<ThemePref>(
                  value: state.theme,
                  options: [
                    (ThemePref.auto, t(lang, K.themeAuto)),
                    (ThemePref.light, t(lang, K.themeLight)),
                    (ThemePref.dark, t(lang, K.themeDark)),
                  ],
                  onChanged: state.setTheme,
                ),
              ),
              _Setting(
                title: t(lang, K.setLoc),
                sub: t(lang, K.setLocSub),
                last: false,
                child: Row(
                  children: [
                    Icon(LucideIcons.mapPin, size: 16, color: cc.brand2),
                    const SizedBox(width: 6),
                    Expanded(
                      child: Text(
                        state.locationLabel,
                        style: body(15, weight: FontWeight.w600, color: cc.ink),
                      ),
                    ),
                  ],
                ),
              ),
              _Setting(
                title: tm(lang, M.apiServer),
                last: true,
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    SelectableText(
                      apiBase,
                      style: body(14.5, weight: FontWeight.w600, color: cc.ink),
                    ),
                    const SizedBox(height: 6),
                    Row(
                      children: [
                        Container(
                          width: 9,
                          height: 9,
                          decoration: BoxDecoration(color: statusColor, shape: BoxShape.circle),
                        ),
                        const SizedBox(width: 8),
                        Expanded(
                          child: Text(t(lang, statusKey), style: body(13.5, color: cc.ink2)),
                        ),
                      ],
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
        const SizedBox(height: 16),
        Notice(t(lang, K.disclaimer)),
      ],
    );
  }
}

class _Setting extends StatelessWidget {
  const _Setting({required this.title, this.sub, required this.child, this.last = false});
  final String title;
  final String? sub;
  final Widget child;
  final bool last;

  @override
  Widget build(BuildContext context) {
    final cc = CC.of(context);
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.symmetric(vertical: 16),
      decoration: BoxDecoration(
        border: last ? null : Border(bottom: BorderSide(color: cc.line)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            title,
            style: body(16.5, weight: FontWeight.w700, color: cc.ink),
          ),
          if (sub != null && sub!.isNotEmpty) ...[
            const SizedBox(height: 2),
            Text(sub!, style: body(14, color: cc.ink2)),
          ],
          const SizedBox(height: 12),
          child,
        ],
      ),
    );
  }
}

/// Segmented control styled like the web `.segmented`.
class _Segmented<T> extends StatelessWidget {
  const _Segmented({required this.value, required this.options, required this.onChanged});
  final T value;
  final List<(T, String)> options;
  final ValueChanged<T> onChanged;

  @override
  Widget build(BuildContext context) {
    final cc = CC.of(context);
    return Container(
      padding: const EdgeInsets.all(4),
      decoration: BoxDecoration(color: cc.surface2, borderRadius: BorderRadius.circular(rMd)),
      child: Row(
        children: [
          for (final (v, label) in options)
            Expanded(
              child: GestureDetector(
                behavior: HitTestBehavior.opaque,
                onTap: () => onChanged(v),
                child: AnimatedContainer(
                  duration: const Duration(milliseconds: 200),
                  curve: Curves.easeOut,
                  padding: const EdgeInsets.symmetric(vertical: 10, horizontal: 6),
                  alignment: Alignment.center,
                  decoration: BoxDecoration(
                    color: v == value ? cc.surface : Colors.transparent,
                    borderRadius: BorderRadius.circular(rSm),
                    boxShadow: v == value ? cc.shadow : null,
                  ),
                  child: Text(
                    label,
                    textAlign: TextAlign.center,
                    style: body(14.5, weight: FontWeight.w700, color: v == value ? cc.ink : cc.ink2, height: 1.25),
                  ),
                ),
              ),
            ),
        ],
      ),
    );
  }
}
