import 'package:flutter/material.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../i18n.dart';
import '../state.dart';
import '../theme.dart';
import '../ui/common.dart';
import '../util.dart';

/// Bookings made on this phone (saved with shared_preferences).
class BookingsScreen extends StatelessWidget {
  const BookingsScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final state = AppScope.of(context);
    final lang = state.lang;
    final cc = CC.of(context);
    final list = state.bookings;

    return ListView(
      padding: const EdgeInsets.fromLTRB(16, 20, 16, 24),
      children: [
        PageHead(title: t(lang, K.bookingsTitle), sub: t(lang, K.bookingsSub)),
        const SizedBox(height: 20),
        if (list.isEmpty)
          Container(
            padding: const EdgeInsets.all(26),
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(rLg),
              border: Border.all(color: cc.line, width: 1.5),
              color: cc.surface.withValues(alpha: 0.5),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Container(
                  width: 56,
                  height: 56,
                  decoration: BoxDecoration(color: cc.brandSoft, borderRadius: BorderRadius.circular(18)),
                  child: Icon(LucideIcons.calendarCheck, size: 28, color: cc.brand2),
                ),
                const SizedBox(height: 14),
                Text(t(lang, K.bookingsEmpty), style: body(16, color: cc.ink2)),
                const SizedBox(height: 16),
                FilledButton(onPressed: state.newCheck, child: Text(t(lang, K.startCheck))),
              ],
            ),
          )
        else
          for (var i = 0; i < list.length; i++)
            EntryAnimation(
              delay: Duration(milliseconds: 40 * i),
              child: Padding(
                padding: const EdgeInsets.only(bottom: 12),
                child: Panel(
                  padding: const EdgeInsets.all(16),
                  child: Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Avatar(name: list[i].caregiverName, seed: list[i].caregiverId, size: 48),
                      const SizedBox(width: 14),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            CCChip(t(lang, K.confirmed), tone: ChipTone.brand, icon: LucideIcons.check),
                            const SizedBox(height: 6),
                            Text(
                              list[i].caregiverName,
                              style: body(17, weight: FontWeight.w700, color: cc.ink, height: 1.25),
                            ),
                            const SizedBox(height: 2),
                            Text(
                              '${roleLabel(list[i].role, lang)}${list[i].careLabel != null ? ', ${list[i].careLabel}' : ''}',
                              style: body(14.5, color: cc.ink2),
                            ),
                            const SizedBox(height: 8),
                            Wrap(
                              spacing: 12,
                              runSpacing: 6,
                              crossAxisAlignment: WrapCrossAlignment.center,
                              children: [
                                if (list[i].slotLabel != null)
                                  Row(
                                    mainAxisSize: MainAxisSize.min,
                                    children: [
                                      Icon(LucideIcons.clock, size: 14, color: cc.ink3),
                                      const SizedBox(width: 5),
                                      Flexible(
                                        child: Text(list[i].slotLabel!, style: body(14, color: cc.ink2)),
                                      ),
                                    ],
                                  ),
                                Text(
                                  '${t(lang, K.bookingId)}: ${list[i].bookingId}',
                                  style: body(13.5, weight: FontWeight.w600, color: cc.ink3),
                                ),
                              ],
                            ),
                          ],
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ),
        const SizedBox(height: 12),
        Notice(t(lang, K.disclaimer)),
      ],
    );
  }
}
