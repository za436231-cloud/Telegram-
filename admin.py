from helpers import *

# =====================================================================
# AUTO LOCK / UNLOCK (har minute schedule check karta hai)
# Restart ya redeploy ke time bhi lock/unlock miss nahi hota.
# Lock: LOCK_TIME se UNLOCK_TIME tak (settings.py mein UTC mein set hai)
# =====================================================================


def should_be_locked(now=None):
    """Abhi schedule ke hisaab se group locked hona chahiye ya nahi."""
    if now is None:
        now = datetime.now(timezone.utc).time()
    lock = LOCK_TIME.replace(tzinfo=None)
    unlock = UNLOCK_TIME.replace(tzinfo=None)
    if lock > unlock:
        return now >= lock or now < unlock
    return lock <= now < unlock


async def notify_admins(context, text):
    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_message(
                admin_id, text, parse_mode=ParseMode.HTML
            )
        except Exception as e:
            logging.warning("admin notify failed: %s", e)


async def apply_lock(context, gid, locked):
    perms = LOCKED if locked else UNLOCKED
    word = "lock" if locked else "unlock"
    try:
        await context.bot.set_chat_permissions(gid, perms)
    except Exception as e:
        logging.error("%s failed for %s: %s", word, gid, e)
        last = context.bot_data.get("lock_fail_at", 0)
        if tm.time() - last > 3600:
            context.bot_data["lock_fail_at"] = tm.time()
            await notify_admins(
                context,
                f"{WARN} Group <code>{gid}</code> {word} nahi ho paya:\n"
                f"<code>{esc(e)}</code>\n\n"
                "Bot ko group mein admin banao aur "
                "<b>Restrict members</b> (Ban users) permission do.",
            )
        return False

    if locked:
        text = f"{LOCK} <b>Group locked.</b> Subah 6:00 AM IST par khulega."
    else:
        text = f"{UNLOCK} <b>Group unlocked.</b> Ab messages bhej sakte ho."
    try:
        await context.bot.send_message(gid, text, parse_mode=ParseMode.HTML)
    except Exception as e:
        logging.warning("lock notice failed for %s: %s", gid, e)
    return True


async def schedule_check(context: ContextTypes.DEFAULT_TYPE):
    want = should_be_locked()
    states = context.bot_data.setdefault("lock_states", {})
    for gid in GROUP_IDS:
        last = states.get(gid)
        if last == want:
            continue
        if last is None:
            # Bot abhi start hua: group schedule se alag ho tabhi badlo
            try:
                chat = await context.bot.get_chat(gid)
            except Exception as e:
                logging.warning("get_chat failed for %s: %s", gid, e)
                continue
            can = chat.permissions.can_send_messages if chat.permissions else None
            if can is None or (not can) == want:
                states[gid] = want
                continue
        if await apply_lock(context, gid, want):
            states[gid] = want


async def lockstatus(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if msg is None or not is_admin(update):
        return
    schedule = "LOCKED" if should_be_locked() else "OPEN"
    lines = [
        f"{CAL} <b>Time (IST):</b> {now_text()}",
        f"{LOCK} <b>Schedule abhi:</b> {schedule} "
        "(12:00 AM - 6:00 AM IST lock)",
        "<b>JobQueue:</b> "
        + ("OK" if context.application.job_queue else
           "NAHI MILA (requirements.txt mein [job-queue] chahiye)"),
    ]
    for gid in GROUP_IDS:
        try:
            chat = await context.bot.get_chat(gid)
            can = chat.permissions.can_send_messages if chat.permissions else None
            state = "UNKNOWN" if can is None else ("OPEN" if can else "LOCKED")
            me = await context.bot.get_chat_member(gid, context.bot.id)
            rights = getattr(me, "can_restrict_members", None)
            lines.append(
                f"<code>{gid}</code>: group abhi {state}, "
                f"bot={esc(me.status)}, restrict_members={rights}"
            )
        except Exception as e:
            lines.append(f"<code>{gid}</code>: error {esc(e)}")
    await reply_html(msg, "\n".join(lines))


# =====================================================================
# MANUAL /lock aur /unlock (sirf ADMIN_IDS, sirf group)
# =====================================================================


async def lock_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message is None or not in_group(update) or not is_admin(update):
        return
    for gid in GROUP_IDS:
        await apply_lock(context, gid, True)


async def unlock_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message is None or not in_group(update) or not is_admin(update):
        return
    for gid in GROUP_IDS:
        await apply_lock(context, gid, False)


# =====================================================================
# /emojiid : premium emoji ki ID nikalne ke liye (sirf ADMIN_IDS)
#   Premium emoji ke saath likho: /emojiid 🎫🔐
#   ya kisi premium emoji wale message par reply karke /emojiid likho
# =====================================================================


async def emojiid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if msg is None or not is_admin(update):
        return
    target = msg.reply_to_message or msg
    found = []
    for ent in target.entities or ():
        if ent.type == "custom_emoji" and ent.custom_emoji_id:
            found.append((target.parse_entity(ent), ent.custom_emoji_id))
    for ent in target.caption_entities or ():
        if ent.type == "custom_emoji" and ent.custom_emoji_id:
            found.append(
                (target.parse_caption_entity(ent), ent.custom_emoji_id)
            )
    seen = set()
    lines = []
    for char, eid in found:
        if eid in seen:
            continue
        seen.add(eid)
        lines.append(f"{esc(char)} <code>{eid}</code>")
    if not lines:
        await reply_html(
            msg,
            f"{WARN} Premium emoji ke saath likho: <code>/emojiid</code> "
            "(emoji yahin likho), ya premium emoji wale message par "
            "reply karo.",
        )
        return
    await reply_html(msg, "\n".join(lines))
