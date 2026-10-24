import 'package:flutter/material.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../i18n.dart';
import '../models.dart';
import '../state.dart';
import '../theme.dart';
import '../ui/common.dart';
import '../ui/emergency.dart';

/// Always-available emergency numbers and danger signs (web SosView).
/// Numbers come from /v1/labels, with the web client's built-in fallback.
class SosScreen extends StatefulWidget {
  const SosScreen({super.key});

  @override
  State<SosScreen> createState() => _SosScreenState();
}

class _SosScreenState extends State<SosScreen> {
  static const _hide = {'possible_emergency', 'emergency_requested'};
  LabelsResponse _data = LabelsResponse.fallback;
  bool _loaded = false;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (_loaded) return;
    _loaded = true;
    AppScope.read(context).api.labels().then((d) {
      if (mounted) setState(() => _data = d);
    });
  }

  @override
  Widget build(BuildContext context) {
    final state = AppScope.of(context);
    final lang = state.lang;
    final cc = CC.of(context);
    final numbers = _data.allNumbers;
    final flags = _data.redFlags.where((f) => !_hide.contains(f.id)).toList();

    return ListView(
      padding: const EdgeInsets.fromLTRB(16, 20, 16, 24),
      children: [
        PageHead(title: t(lang, K.sosPageTitle), sub: t(lang, K.sosPageSub)),
        const SizedBox(height: 20),
        for (var i = 0; i < numbers.length; i++)
          Padding(
            padding: const EdgeInsets.only(bottom: 10),
            child: _NumberTile(
              number: numbers[i].number,
              label: lang == Lang.en ? numbers[i].label : numbers[i].labelHi,
              main: i == 0,
              hint: t(lang, K.tapToCall),
              onTap: () => callNumber(context, numbers[i].number, lang),
            ),
          ),
        if (flags.isNotEmpty) ...[
          const SizedBox(height: 10),
          Panel(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  t(lang, K.sosSignsTitle),
                  style: display(21, weight: FontWeight.w700, color: cc.ink),
                ),
                const SizedBox(height: 12),
                for (final f in flags)
                  Container(
                    width: double.infinity,
                    margin: const EdgeInsets.only(bottom: 8),
                    padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
                    decoration: BoxDecoration(color: cc.sindoorSoft, borderRadius: BorderRadius.circular(rMd)),
                    child: Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Padding(
                          padding: const EdgeInsets.only(top: 2),
                          child: Icon(LucideIcons.triangleAlert, size: 16, color: cc.sindoor),
                        ),
                        const SizedBox(width: 10),
                        Expanded(
                          child: Text(
                            f.labelFor(lang),
                            style: body(15, weight: FontWeight.w600, color: cc.ink),
                          ),
                        ),
                      ],
                    ),
                  ),
              ],
            ),
          ),
        ],
      ],
    );
  }
}

class _NumberTile extends StatelessWidget {
  const _NumberTile({
    required this.number,
    required this.label,
    required this.main,
    required this.hint,
    required this.onTap,
  });
  final String number;
  final String label;
  final bool main;
  final String hint;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final cc = CC.of(context);
    return Semantics(
      button: true,
      label: '$number, $label. $hint',
      child: Pressable(
        onTap: onTap,
        child: Container(
          padding: EdgeInsets.symmetric(horizontal: 18, vertical: main ? 18 : 14),
          decoration: BoxDecoration(
            color: main ? CC.sosFixed : cc.surface,
            borderRadius: BorderRadius.circular(rLg),
            border: Border.all(color: main ? CC.sosFixed : cc.line),
            boxShadow: main
                ? [BoxShadow(color: CC.sosFixed.withValues(alpha: 0.35), blurRadius: 18, offset: const Offset(0, 8))]
                : null,
          ),
          child: Row(
            children: [
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(number, style: display(main ? 36 : 27, color: main ? Colors.white : cc.sindoor, height: 1.05)),
                    const SizedBox(height: 2),
                    Text(label, style: body(14, color: main ? Colors.white.withValues(alpha: 0.92) : cc.ink2)),
                  ],
                ),
              ),
              Container(
                width: 48,
                height: 48,
                decoration: BoxDecoration(
                  color: main ? Colors.white.withValues(alpha: 0.18) : cc.sindoorSoft,
                  shape: BoxShape.circle,
                ),
                child: Icon(LucideIcons.phone, size: 22, color: main ? Colors.white : cc.sindoor),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
