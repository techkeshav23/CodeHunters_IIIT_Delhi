import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../i18n.dart';
import '../models.dart';
import '../state.dart';
import '../strings_mobile.dart';
import '../theme.dart';
import '../util.dart';
import 'common.dart';

/// The chat sidebar (☰ in the top bar), as in ChatGPT or Gemini: New chat,
/// "Bina save kiye chat" (incognito), then the chats saved on this phone
/// grouped Aaj / Kal / Pehle, newest first. Tapping one opens it in the
/// Jaanch thread; each can be deleted from its ⋮ menu, or all of them after
/// a confirm.
class ChatDrawer extends StatelessWidget {
  const ChatDrawer({super.key});

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
    final scaffold = Scaffold.of(context);

    // Each action lands in the Jaanch view, so the sidebar closes first.
    void closeThen(VoidCallback action) {
      scaffold.closeDrawer();
      action();
    }

    // Saying so when an open saved chat left History.
    void incognito() {
      final messenger = ScaffoldMessenger.maybeOf(context);
      closeThen(() {
        if (state.goIncognito()) messenger?.showSnackBar(SnackBar(content: Text(tm(lang, M.incognitoRemoved))));
      });
    }

    // Chats are newest first, so each day group is one run of the list.
    const groups = [M.groupToday, M.groupYesterday, M.groupEarlier];
    final rows = <Widget>[];
    int? group;
    for (final c in chats) {
      final g = daysAgo(c.updatedAt).clamp(0, 2);
      if (g != group) {
        group = g;
        rows.add(_GroupLabel(text: tm(lang, groups[g])));
      }
      rows.add(
        _ChatRow(
          chat: c,
          lang: lang,
          open: c.id == state.chatId,
          onOpen: () => closeThen(() => state.openChat(c)),
          onDelete: () => state.deleteChat(c.id),
        ),
      );
    }

    return Drawer(
      width: math.min(MediaQuery.sizeOf(context).width * 0.86, 340),
      backgroundColor: cc.surface,
      surfaceTintColor: Colors.transparent,
      semanticLabel: tm(lang, M.chats),
      child: SafeArea(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Padding(
              padding: const EdgeInsets.fromLTRB(12, 12, 12, 6),
              child: FilledButton.icon(
                onPressed: () => closeThen(state.newChat),
                icon: const Icon(LucideIcons.plus, size: 20),
                label: Text(tm(lang, M.newChat)),
              ),
            ),
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 8),
              child: _Action(
                icon: LucideIcons.eyeOff,
                label: tm(lang, M.incognito),
                selected: state.incognito,
                onTap: incognito,
              ),
            ),
            const SizedBox(height: 6),
            Divider(color: cc.line),
            Expanded(
              child: ListView(
                padding: const EdgeInsets.fromLTRB(8, 4, 8, 12),
                children: chats.isEmpty ? [_Empty(text: tm(lang, M.historyEmpty))] : rows,
              ),
            ),
            Container(
              padding: const EdgeInsets.fromLTRB(10, 4, 16, 12),
              decoration: BoxDecoration(border: Border(top: BorderSide(color: cc.line))),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  if (chats.isNotEmpty)
                    TextButton.icon(
                      onPressed: () => _deleteAll(context, state),
                      style: TextButton.styleFrom(foregroundColor: cc.sindoor),
                      icon: const Icon(LucideIcons.trash2, size: 18),
                      label: Text(tm(lang, M.deleteAll)),
                    ),
                  Padding(
                    padding: const EdgeInsets.fromLTRB(10, 6, 0, 0),
                    child: Text(tm(lang, M.historySub), style: body(13.5, color: cc.ink3, height: 1.35)),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

/// "Bina save kiye chat" (incognito) in the sidebar; highlighted while it is on.
class _Action extends StatelessWidget {
  const _Action({required this.icon, required this.label, required this.selected, required this.onTap});
  final IconData icon;
  final String label;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final cc = CC.of(context);
    final fg = selected ? cc.brand2 : cc.ink;
    return Semantics(
      button: true,
      selected: selected,
      label: label,
      excludeSemantics: true,
      child: Pressable(
        onTap: onTap,
        child: Container(
          constraints: const BoxConstraints(minHeight: 48),
          padding: const EdgeInsets.fromLTRB(12, 10, 12, 10),
          decoration: BoxDecoration(
            color: selected ? cc.brandSoft : Colors.transparent,
            borderRadius: BorderRadius.circular(rMd),
          ),
          child: Row(
            children: [
              Icon(icon, size: 19, color: selected ? cc.brand2 : cc.ink2),
              const SizedBox(width: 12),
              Expanded(child: Text(label, style: body(15.5, weight: FontWeight.w700, color: fg, height: 1.3))),
              if (selected) Icon(LucideIcons.check, size: 18, color: cc.brand2),
            ],
          ),
        ),
      ),
    );
  }
}

/// "Aaj", "Kal" or "Pehle" above a run of chats.
class _GroupLabel extends StatelessWidget {
  const _GroupLabel({required this.text});
  final String text;

  @override
  Widget build(BuildContext context) {
    final cc = CC.of(context);
    return Padding(
      padding: const EdgeInsets.fromLTRB(12, 12, 12, 4),
      child: Semantics(
        header: true,
        child: Text(text, style: body(13, weight: FontWeight.w700, color: cc.ink3, height: 1.3)),
      ),
    );
  }
}

/// One saved chat: what was asked and what it came to; the open one is
/// highlighted.
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
    final (icon, iconColor, outcome, outcomeColor) = switch (chat.outcome) {
      'emergency' => (LucideIcons.triangleAlert, cc.sindoor, chat.outcomeLabel ?? t(lang, K.sosPageTitle), cc.sindoor),
      'decision' => (
        LucideIcons.stethoscope,
        cc.brand2,
        chat.outcomeLabel ?? '',
        chat.level == 2 ? cc.sindoor : cc.brand2,
      ),
      'unclear' => (LucideIcons.messageCircleQuestion, cc.ink2, tm(lang, M.chatUnclear), cc.ink2),
      'question' => (LucideIcons.messageCircleQuestion, cc.ink2, tm(lang, M.chatPending), cc.ink2),
      _ => (LucideIcons.messageSquare, cc.ink3, tm(lang, M.chatNoReply), cc.ink3),
    };
    final when = chatTime(chat.updatedAt, lang);

    return Container(
      margin: const EdgeInsets.only(bottom: 2),
      decoration: BoxDecoration(
        color: open ? cc.brandSoft : Colors.transparent,
        borderRadius: BorderRadius.circular(rMd),
      ),
      child: Row(
        children: [
          Expanded(
            child: Semantics(
              button: true,
              selected: open,
              label: '${chat.title}. $outcome. $when',
              excludeSemantics: true,
              child: Pressable(
                onTap: onOpen,
                child: Padding(
                  padding: const EdgeInsets.fromLTRB(12, 10, 4, 10),
                  child: Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Padding(
                        padding: const EdgeInsets.only(top: 2),
                        child: Icon(icon, size: 18, color: iconColor),
                      ),
                      const SizedBox(width: 12),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              chat.title,
                              maxLines: 1,
                              overflow: TextOverflow.ellipsis,
                              style: body(15.5, weight: FontWeight.w700, color: cc.ink, height: 1.3),
                            ),
                            if (outcome.isNotEmpty) ...[
                              const SizedBox(height: 2),
                              Text(
                                outcome,
                                maxLines: 2,
                                overflow: TextOverflow.ellipsis,
                                style: body(13.5, weight: FontWeight.w600, color: outcomeColor, height: 1.3),
                              ),
                            ],
                          ],
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ),
          ),
          PopupMenuButton<int>(
            tooltip: tm(lang, M.chatMenu),
            icon: Icon(LucideIcons.ellipsisVertical, size: 18, color: cc.ink3),
            color: cc.surface,
            surfaceTintColor: Colors.transparent,
            onSelected: (_) => onDelete(),
            itemBuilder: (context) => [
              PopupMenuItem(
                value: 0,
                child: Row(
                  children: [
                    Icon(LucideIcons.trash2, size: 18, color: cc.sindoor),
                    const SizedBox(width: 10),
                    Text(tm(lang, M.chatDelete), style: body(15, weight: FontWeight.w700, color: cc.sindoor)),
                  ],
                ),
              ),
            ],
          ),
        ],
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
      margin: const EdgeInsets.fromLTRB(4, 8, 4, 0),
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(rLg),
        border: Border.all(color: cc.line, width: 1.5),
        color: cc.bg,
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            width: 48,
            height: 48,
            decoration: BoxDecoration(color: cc.brandSoft, borderRadius: BorderRadius.circular(14)),
            child: Icon(LucideIcons.history, size: 24, color: cc.brand2),
          ),
          const SizedBox(height: 12),
          Text(text, style: body(15, color: cc.ink2)),
        ],
      ),
    );
  }
}
