import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../config.dart';
import '../i18n.dart';
import '../state.dart';
import '../theme.dart';
import '../ui/common.dart';

/// "How it works" + the last request/response for judges (web HowView).
class HowScreen extends StatelessWidget {
  const HowScreen({super.key});

  static const _steps = [
    (K.step1, K.step1t),
    (K.step2, K.step2t),
    (K.step3, K.step3t),
    (K.step4, K.step4t),
    (K.step5, K.step5t),
    (K.step6, K.step6t),
  ];

  @override
  Widget build(BuildContext context) {
    final state = AppScope.of(context);
    final lang = state.lang;
    final cc = CC.of(context);

    return ListView(
      padding: const EdgeInsets.fromLTRB(16, 20, 16, 24),
      children: [
        PageHead(title: t(lang, K.howTitle), sub: t(lang, K.howSub)),
        const SizedBox(height: 20),
        for (var i = 0; i < _steps.length; i++)
          Padding(
            padding: const EdgeInsets.only(bottom: 10),
            child: Panel(
              padding: const EdgeInsets.all(16),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Container(
                    width: 32,
                    height: 32,
                    alignment: Alignment.center,
                    decoration: BoxDecoration(color: cc.brand, shape: BoxShape.circle),
                    child: Text('${i + 1}', style: display(16, color: cc.brandInk, height: 1)),
                  ),
                  const SizedBox(width: 14),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          t(lang, _steps[i].$1),
                          style: body(16.5, weight: FontWeight.w700, color: cc.ink),
                        ),
                        const SizedBox(height: 2),
                        Text(t(lang, _steps[i].$2), style: body(14.5, color: cc.ink2)),
                      ],
                    ),
                  ),
                ],
              ),
            ),
          ),
        const SizedBox(height: 8),
        Panel(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                t(lang, K.rulesTitle),
                style: display(21, weight: FontWeight.w700, color: cc.ink),
              ),
              const SizedBox(height: 12),
              for (final k in const [K.rule1, K.rule2, K.rule3, K.rule4])
                Padding(
                  padding: const EdgeInsets.only(bottom: 10),
                  child: Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Padding(
                        padding: const EdgeInsets.only(top: 2),
                        child: Icon(LucideIcons.shieldCheck, size: 18, color: cc.brand2),
                      ),
                      const SizedBox(width: 10),
                      Expanded(
                        child: Text(t(lang, k), style: body(15.5, color: cc.ink)),
                      ),
                    ],
                  ),
                ),
            ],
          ),
        ),
        const SizedBox(height: 12),
        Panel(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                t(lang, K.testedTitle),
                style: display(21, weight: FontWeight.w700, color: cc.ink),
              ),
              const SizedBox(height: 12),
              for (final (big, k) in const [('583', K.stat1), ('209/209', K.stat2), ('~2 ms', K.stat3)])
                Container(
                  width: double.infinity,
                  margin: const EdgeInsets.only(bottom: 10),
                  padding: const EdgeInsets.all(16),
                  decoration: BoxDecoration(color: cc.brandSoft, borderRadius: BorderRadius.circular(rLg)),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(big, style: display(32, color: cc.brand2, height: 1)),
                      const SizedBox(height: 4),
                      Text(t(lang, k), style: body(14, color: cc.ink2)),
                    ],
                  ),
                ),
            ],
          ),
        ),
        const SizedBox(height: 12),
        const _ApiPanel(),
      ],
    );
  }
}

class _ApiPanel extends StatelessWidget {
  const _ApiPanel();

  @override
  Widget build(BuildContext context) {
    final state = AppScope.of(context);
    final lang = state.lang;
    final cc = CC.of(context);
    final last = state.last;
    const enc = JsonEncoder.withIndent('  ');
    final req = last == null ? '' : enc.convert(last.req.toJson());
    final res = last == null ? '' : enc.convert(last.res.schemaFields);

    Widget code(String title, String text) => Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Expanded(
              child: Text(
                'POST /v1/triage: $title',
                style: body(15, weight: FontWeight.w700, color: cc.ink),
              ),
            ),
            TextButton.icon(
              onPressed: () async {
                await Clipboard.setData(ClipboardData(text: text));
                if (context.mounted) {
                  ScaffoldMessenger.maybeOf(context)?.showSnackBar(SnackBar(content: Text(t(lang, K.copied))));
                }
              },
              icon: const Icon(LucideIcons.copy, size: 16),
              label: Text(t(lang, K.copy)),
            ),
          ],
        ),
        const SizedBox(height: 6),
        Container(
          width: double.infinity,
          constraints: const BoxConstraints(maxHeight: 320),
          padding: const EdgeInsets.all(14),
          decoration: BoxDecoration(color: cc.surface2, borderRadius: BorderRadius.circular(rMd)),
          child: SingleChildScrollView(
            child: SingleChildScrollView(
              scrollDirection: Axis.horizontal,
              child: SelectableText(
                text,
                style: TextStyle(fontFamily: 'monospace', fontSize: 12.5, height: 1.5, color: cc.ink),
              ),
            ),
          ),
        ),
        const SizedBox(height: 14),
      ],
    );

    return Panel(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            t(lang, K.apiTitle),
            style: display(21, weight: FontWeight.w700, color: cc.ink),
          ),
          const SizedBox(height: 6),
          Text(t(lang, K.apiSub), style: body(14.5, color: cc.ink2)),
          const SizedBox(height: 6),
          SelectableText(
            apiBase,
            style: body(13.5, weight: FontWeight.w600, color: cc.brand2),
          ),
          const SizedBox(height: 12),
          if (last == null)
            Text(t(lang, K.apiEmpty), style: body(15, color: cc.ink3))
          else ...[
            CCChip(t(lang, K.answeredIn, {'ms': last.res.trace.timingMs}), tone: ChipTone.brand),
            const SizedBox(height: 12),
            code(t(lang, K.request), req),
            code(t(lang, K.response), res),
          ],
        ],
      ),
    );
  }
}
