import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../i18n.dart';
import '../models.dart';
import '../state.dart';
import '../theme.dart';
import '../util.dart';
import 'common.dart';

/// Confirm sheet -> POST /v1/bookings -> confirmation with booking id
/// (web BookingSheet.tsx). Returns true if the user tapped "See my bookings".
Future<bool?> showBookingSheet(BuildContext context, TraceCaregiver cg, TriageResponse res) {
  return showModalBottomSheet<bool>(
    context: context,
    isScrollControlled: true,
    useSafeArea: true,
    builder: (context) => _BookingSheet(cg: cg, res: res),
  );
}

enum _St { idle, busy, done, error }

class _BookingSheet extends StatefulWidget {
  const _BookingSheet({required this.cg, required this.res});
  final TraceCaregiver cg;
  final TriageResponse res;

  @override
  State<_BookingSheet> createState() => _BookingSheetState();
}

class _BookingSheetState extends State<_BookingSheet> {
  final _note = TextEditingController();
  _St _st = _St.idle;
  SavedBooking? _saved;

  @override
  void dispose() {
    _note.dispose();
    super.dispose();
  }

  Future<void> _confirm() async {
    setState(() => _st = _St.busy);
    final state = AppScope.read(context);
    try {
      final s = await state.book(widget.cg, widget.res, _note.text.trim());
      if (!mounted) return;
      HapticFeedback.mediumImpact();
      setState(() {
        _saved = s;
        _st = _St.done;
      });
    } catch (_) {
      if (!mounted) return;
      setState(() => _st = _St.error);
    }
  }

  @override
  Widget build(BuildContext context) {
    final state = AppScope.of(context);
    final lang = state.lang;
    final cc = CC.of(context);
    final tele = isTele(widget.res.careType);
    final insets = MediaQuery.viewInsetsOf(context);

    return Padding(
      padding: EdgeInsets.only(bottom: insets.bottom),
      child: SingleChildScrollView(
        padding: const EdgeInsets.fromLTRB(22, 0, 22, 24),
        child: AnimatedSwitcher(
          duration: const Duration(milliseconds: 320),
          switchInCurve: Curves.easeOutCubic,
          transitionBuilder: (child, a) => FadeTransition(
            opacity: a,
            child: ScaleTransition(scale: Tween(begin: 0.97, end: 1.0).animate(a), child: child),
          ),
          child: _st == _St.done ? _done(context, lang, cc) : _form(context, lang, cc, tele),
        ),
      ),
    );
  }

  Widget _kv(CC cc, String k, String v, {TextStyle? vStyle}) => Padding(
    padding: const EdgeInsets.only(bottom: 12),
    child: Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        SizedBox(
          width: 92,
          child: Text(
            k,
            style: body(14.5, weight: FontWeight.w600, color: cc.ink3),
          ),
        ),
        Expanded(
          child: Text(
            v,
            style: vStyle ?? body(16, weight: FontWeight.w600, color: cc.ink),
          ),
        ),
      ],
    ),
  );

  Widget _form(BuildContext context, Lang lang, CC cc, bool tele) {
    final cg = widget.cg;
    final busy = _st == _St.busy;
    return Column(
      key: const ValueKey('form'),
      crossAxisAlignment: CrossAxisAlignment.start,
      mainAxisSize: MainAxisSize.min,
      children: [
        Row(
          children: [
            Avatar(name: cg.name, seed: cg.caregiverId, size: 44),
            const SizedBox(width: 12),
            Expanded(
              child: Text(t(lang, K.confirmTitle), style: display(25, color: cc.ink)),
            ),
          ],
        ),
        const SizedBox(height: 20),
        _kv(cc, t(lang, K.bWho), '${cg.name}, ${roleLabel(cg.role, lang)}'),
        _kv(cc, t(lang, K.bWhen), cg.nextSlotLabelLocal ?? '-'),
        _kv(cc, t(lang, K.bWhere), tele ? t(lang, K.videoCall) : AppScope.of(context).locationLabel),
        _kv(cc, t(lang, K.bWhat), careLabel(widget.res, lang)),
        const SizedBox(height: 6),
        Text(
          t(lang, K.bNote),
          style: body(14.5, weight: FontWeight.w600, color: cc.ink2),
        ),
        const SizedBox(height: 6),
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
          decoration: BoxDecoration(
            color: cc.bg,
            borderRadius: BorderRadius.circular(rMd),
            border: Border.all(color: cc.line, width: 1.5),
          ),
          child: TextField(
            controller: _note,
            maxLength: 500,
            minLines: 2,
            maxLines: 4,
            style: body(16, color: cc.ink),
            decoration: const InputDecoration(counterText: '', border: InputBorder.none),
          ),
        ),
        if (_st == _St.error) ...[
          const SizedBox(height: 12),
          Container(
            width: double.infinity,
            padding: const EdgeInsets.all(14),
            decoration: BoxDecoration(color: cc.sindoorSoft, borderRadius: BorderRadius.circular(rMd)),
            child: Text(t(lang, K.bookFailed), style: body(15, color: cc.ink)),
          ),
        ],
        const SizedBox(height: 18),
        Row(
          children: [
            Expanded(
              child: OutlinedButton(
                onPressed: busy ? null : () => Navigator.of(context).pop(false),
                child: Text(t(lang, K.back)),
              ),
            ),
            const SizedBox(width: 10),
            Expanded(
              flex: 2,
              child: FilledButton.icon(
                onPressed: busy ? null : _confirm,
                icon: busy
                    ? SizedBox(
                        width: 18,
                        height: 18,
                        child: CircularProgressIndicator(strokeWidth: 2.2, color: cc.brandInk),
                      )
                    : const Icon(LucideIcons.calendarCheck, size: 18),
                label: Text(busy ? t(lang, K.booking) : t(lang, K.confirm)),
              ),
            ),
          ],
        ),
      ],
    );
  }

  Widget _done(BuildContext context, Lang lang, CC cc) {
    final cg = widget.cg;
    return Column(
      key: const ValueKey('done'),
      crossAxisAlignment: CrossAxisAlignment.start,
      mainAxisSize: MainAxisSize.min,
      children: [
        TweenAnimationBuilder<double>(
          tween: Tween(begin: 0, end: 1),
          duration: const Duration(milliseconds: 600),
          curve: Curves.elasticOut,
          builder: (context, v, child) => Transform.scale(scale: 0.6 + 0.4 * v, child: child),
          child: Container(
            width: 68,
            height: 68,
            decoration: BoxDecoration(color: cc.ok.withValues(alpha: 0.18), shape: BoxShape.circle),
            child: Icon(LucideIcons.circleCheck, size: 38, color: cc.ok),
          ),
        ),
        const SizedBox(height: 14),
        Text(t(lang, K.booked), style: display(28, color: cc.ink)),
        const SizedBox(height: 8),
        Text(
          t(lang, K.bookedText, {'name': cg.name, 'time': cg.nextSlotLabelLocal ?? ''}),
          style: body(16, color: cc.ink2),
        ),
        const SizedBox(height: 16),
        Container(
          width: double.infinity,
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
          decoration: BoxDecoration(color: cc.brandSoft, borderRadius: BorderRadius.circular(rMd)),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                t(lang, K.bookingId),
                style: body(14.5, weight: FontWeight.w600, color: cc.ink2),
              ),
              const SizedBox(height: 2),
              SelectableText(
                _saved?.bookingId ?? '',
                style: display(
                  20,
                  color: cc.brand2,
                ).copyWith(letterSpacing: 1, fontFeatures: const [FontFeature.tabularFigures()]),
              ),
            ],
          ),
        ),
        const SizedBox(height: 18),
        Row(
          children: [
            Expanded(
              child: OutlinedButton(
                onPressed: () => Navigator.of(context).pop(true),
                child: Text(t(lang, K.seeBookings), textAlign: TextAlign.center),
              ),
            ),
            const SizedBox(width: 10),
            Expanded(
              child: FilledButton(onPressed: () => Navigator.of(context).pop(false), child: Text(t(lang, K.close))),
            ),
          ],
        ),
      ],
    );
  }
}
