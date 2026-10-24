import 'package:flutter/material.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../i18n.dart';
import '../models.dart';
import '../state.dart';
import '../strings_mobile.dart';
import '../theme.dart';
import '../util.dart';
import 'common.dart';

/// Chats saved on this phone, newest first. Tapping one opens it in the
/// Jaanch thread; each can be deleted, or all of them after a confirm.
Future<void> showHistorySheet(BuildContext context) {
  return showModalBottomSheet<void>(
    context: context,
    isScrollControlled: true,
    useSafeArea: true,
    builder: (context) => const FractionallySizedBox(heightFactor: 0.92, child: _HistorySheet()),
  );
}

class _HistorySheet extends StatelessWidget {
  const _HistorySheet();

  Future<void> _deleteAll(BuildContext context, AppState state) async {
    final lang = state.lang;
    final cc = CC.of(context);
    final title = tm(lang, M.deleteAllTitle);
    final ok = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        scrollable: true,
        backgroundColor: cc.surface,
        surfaceTintColor: Colors.transparent,
        title: Text(title, style: dv(display(21, color: cc.ink), title)),
        content: Text(
          tm(lang, M.deleteAllText, {'n': state.chats.length}),
          style: body(15.5, color: cc.ink2),
        ),
        actions: [
          TextButton(onPressed: () => Navigator.of(context).pop(false), child: Text(t(lang, K.back))),
          FilledButton(
            style: FilledButton.styleFrom(backgroundColor: CC.sosFixed, foregroundColor: Colors.white),
            onPressed: () => Navigator.of(context).pop(true),
            child: Text(tm(lang, M.deleteYes)),
          ),
        ],
      ),
    );
    if (ok == true) state.deleteAllChats();
  }

  @override
  Widget build(BuildContext context) {
    final state = AppScope.of(context);
    final lang = state.lang;
    final cc = CC.of(context);
    final chats = state.chats;
    final title = tm(lang, M.historyTitle);

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(20, 0, 20, 12),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(title, style: dv(display(25, color: cc.ink), title)),
              const SizedBox(height: 4),
              Text(tm(lang, M.historySub), style: body(14.5, color: cc.ink2)),
            ],
          ),
        ),
        Expanded(
          child: chats.isEmpty
              ? ListView(
                  padding: const EdgeInsets.fromLTRB(16, 4, 16, 16),
                  children: [_Empty(text: tm(lang, M.historyEmpty))],
                )
              : ListView.separated(
                  padding: const EdgeInsets.fromLTRB(16, 4, 16, 16),
                  itemCount: chats.length,
                  separatorBuilder: (_, _) => const SizedBox(height: 10),
                  itemBuilder: (context, i) {
                    final c = chats[i];
                    return _ChatRow(
                      chat: c,
                      lang: lang,
                      open: c.id == state.chatId,
                      onOpen: () {
                        Navigator.of(context).pop();
                        state.openChat(c);
                      },
                      onDelete: () => state.deleteChat(c.id),
                    );
                  },
                ),
        ),
        if (chats.isNotEmpty)
          Container(
            width: double.infinity,
            padding: const EdgeInsets.fromLTRB(10, 6, 10, 10),
            decoration: BoxDecoration(border: Border(top: BorderSide(color: cc.line))),
            child: Align(
              alignment: Alignment.centerLeft,
              child: TextButton.icon(
                onPressed: () => _deleteAll(context, state),
                style: TextButton.styleFrom(foregroundColor: cc.sindoor),
                icon: const Icon(LucideIcons.trash2, size: 18),
                label: Text(tm(lang, M.deleteAll)),
              ),
            ),
          ),
      ],
    );
  }
}

/// One saved chat: what was asked, what it came to, and when.
class _ChatRow extends StatelessWidget {
  const _ChatRow({
    required this.chat,
    required this.lang,
    required this.open,
    required this.onOpen,
    required this.onDelete,
  });
  final SavedChat chat;
  final Lang lang;
  final bool open;
  final VoidCallback onOpen;
  final VoidCallback onDelete;

  @override
  Widget build(BuildContext context) {
    final cc = CC.of(context);
    final (icon, iconBg, iconFg, outcome, outcomeColor) = switch (chat.outcome) {
      'emergency' => (
        LucideIcons.triangleAlert,
        cc.sindoorSoft,
        cc.sindoor,
        chat.outcomeLabel ?? t(lang, K.sosPageTitle),
        cc.sindoor,
      ),
      'decision' => (
        LucideIcons.stethoscope,
        cc.brandSoft,
        cc.brand2,
        chat.outcomeLabel ?? '',
        chat.level == 2 ? cc.sindoor : cc.brand2,
      ),
      'question' => (LucideIcons.messageCircleQuestion, cc.haldiSoft, cc.ink, tm(lang, M.chatPending), cc.ink2),
      _ => (LucideIcons.messageSquare, cc.surface2, cc.ink3, tm(lang, M.chatNoReply), cc.ink3),
    };
    final when = chatTime(chat.updatedAt, lang);

    return Semantics(
      button: true,
      label: '${chat.title}. $outcome. $when',
      child: Pressable(
        onTap: onOpen,
        child: Container(
          padding: const EdgeInsets.fromLTRB(14, 12, 4, 12),
          decoration: BoxDecoration(
            color: cc.bg,
            borderRadius: BorderRadius.circular(rLg),
            border: Border.all(color: open ? cc.brand : cc.line, width: open ? 1.5 : 1),
          ),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Container(
                width: 38,
                height: 38,
                decoration: BoxDecoration(color: iconBg, borderRadius: BorderRadius.circular(12)),
                child: Icon(icon, size: 19, color: iconFg),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: ExcludeSemantics(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        chat.title,
                        maxLines: 2,
                        overflow: TextOverflow.ellipsis,
                        style: body(16, weight: FontWeight.w700, color: cc.ink, height: 1.3),
                      ),
                      if (outcome.isNotEmpty) ...[
                        const SizedBox(height: 4),
                        Text(
                          outcome,
                          maxLines: 2,
                          overflow: TextOverflow.ellipsis,
                          style: body(14, weight: FontWeight.w600, color: outcomeColor, height: 1.3),
                        ),
                      ],
                      const SizedBox(height: 3),
                      Text(when, style: body(13, color: cc.ink3, height: 1.3)),
                    ],
                  ),
                ),
              ),
              IconButton(
                tooltip: tm(lang, M.chatDelete),
                onPressed: onDelete,
                icon: Icon(LucideIcons.trash2, size: 18, color: cc.ink3),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _Empty extends StatelessWidget {
  const _Empty({required this.text});
  final String text;

  @override
  Widget build(BuildContext context) {
    final cc = CC.of(context);
    return Container(
      padding: const EdgeInsets.all(22),
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(rLg),
        border: Border.all(color: cc.line, width: 1.5),
        color: cc.bg,
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            width: 52,
            height: 52,
            decoration: BoxDecoration(color: cc.brandSoft, borderRadius: BorderRadius.circular(16)),
            child: Icon(LucideIcons.history, size: 26, color: cc.brand2),
          ),
          const SizedBox(height: 12),
          Text(text, style: body(15.5, color: cc.ink2)),
        ],
      ),
    );
  }
}
