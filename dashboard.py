from helpers import *

# =====================================================================
# /start DASHBOARD
# =====================================================================


def dashboard_text(name):
    lines = [
        f"{STAR} <b>Welcome {esc(name)}!</b>",
        DIVIDER,
        f"{SHIELD} <b>Escrow Bot for @rizzlerxescrow</b>",
        f"{CHAT} <b>Provided by @rizzlerxescrow</b>",
        "",
        f"{SIGN} <b>This is Your Personal Dashboard:</b>",
        DIVIDER,
        f"Select the option below {BOLT}",
    ]
    return "\n".join(lines)


def dashboard_buttons():
    rows = [
        [InlineKeyboardButton("📊 Total Deal", callback_data="total_deal")],
        [InlineKeyboardButton("📁 My Deal Info", callback_data="my_deal")],
        [InlineKeyboardButton("🏆 Global Ranking", callback_data="ranking")],
    ]
    return InlineKeyboardMarkup(rows)


def back_button():
    row = [InlineKeyboardButton("🔙 Back", callback_data="back")]
    return InlineKeyboardMarkup([row])


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if msg is None:
        return
    if update.effective_chat.type != "private":
        await msg.reply_text(
            "Dashboard ke liye bot ke private chat mein /start karo."
        )
        return
    name = update.effective_user.first_name or "User"
    await msg.reply_text(
        dashboard_text(name),
        parse_mode=ParseMode.HTML,
        reply_markup=dashboard_buttons(),
    )


async def myid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message is None:
        return
    text = f"{CARD} <b>Your ID:</b> <code>{update.effective_user.id}</code>"
    await reply_html(update.message, text)


async def chatid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message is None:
        return
    text = f"{CARD} <b>Chat ID:</b> <code>{update.effective_chat.id}</code>"
    await reply_html(update.message, text)


# =====================================================================
# DASHBOARD BUTTONS (Total Deal / My Deal Info / Ranking / Back)
# =====================================================================


def total_deal_text():
    done = db_one(
        f"SELECT COUNT(*), COALESCE(SUM(amount), 0) FROM deals "
        f"WHERE {G_SQL} AND status='completed'",
        G_ARGS,
    )
    pending = db_one(
        f"SELECT COUNT(*), COALESCE(SUM(amount), 0) FROM deals "
        f"WHERE {G_SQL} AND status='pending'",
        G_ARGS,
    )
    lines = [
        f"{CHART} <b>TOTAL DEALS</b>",
        DIVIDER,
        f"{DONE} <b>Completed:</b> {done[0]}",
        f"{GEM} <b>Completed Volume:</b> {inr(done[1])}",
        f"{PIN} <b>Pending:</b> {pending[0]}",
        f"{BAG} <b>Pending Volume:</b> {inr(pending[1])}",
    ]
    return "\n".join(lines)


def my_deal_text(user):
    uname = (user.username or "").lower()
    where = f"{G_SQL} AND (form_user_id=? OR (?<>'' AND (buyer=? OR seller=?)))"
    params = G_ARGS + (user.id, uname, uname, uname)
    done = db_one(
        f"SELECT COUNT(*), COALESCE(SUM(amount), 0) FROM deals "
        f"WHERE {where} AND status='completed'",
        params,
    )
    pending = db_one(
        f"SELECT COUNT(*) FROM deals WHERE {where} AND status='pending'",
        params,
    )
    recent = db_all(
        f"SELECT trade_id, amount, status FROM deals "
        f"WHERE {where} ORDER BY id DESC LIMIT 5",
        params,
    )
    lines = [
        f"{FILE} <b>MY DEAL INFO</b>",
        DIVIDER,
        f"{DONE} <b>Completed:</b> {done[0]}",
        f"{GEM} <b>Total Volume:</b> {inr(done[1])}",
        f"{PIN} <b>Pending:</b> {pending[0]}",
    ]
    if recent:
        lines.append("")
        lines.append(f"{TREND} <b>Recent:</b>")
        for trade_id, amount, status in recent:
            mark = "✅" if status == "completed" else "⏳"
            lines.append(f"{mark} <code>{trade_id}</code> - {inr(amount)}")
    else:
        lines.append("")
        lines.append("Abhi tak koi deal nahi mila.")
    return "\n".join(lines)


def ranking_text():
    rows = db_all(
        f"SELECT form_user_id, MAX(form_user_name), COUNT(*), SUM(amount) "
        f"FROM deals WHERE {G_SQL} AND status='completed' "
        f"AND form_user_id IS NOT NULL "
        f"GROUP BY form_user_id ORDER BY SUM(amount) DESC LIMIT 10",
        G_ARGS,
    )
    lines = [f"{TREND} <b>GLOBAL RANKING</b>", DIVIDER]
    if not rows:
        lines.append("Abhi koi completed deal nahi hai.")
        return "\n".join(lines)
    medals = ["🥇", "🥈", "🥉"]
    for i, (uid, name, count, volume) in enumerate(rows):
        mark = medals[i] if i < 3 else f"{i + 1}."
        lines.append(
            f"{mark} {mention(uid, name)} - {inr(volume)} ({count} deals)"
        )
    return "\n".join(lines)


async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query is None:
        return
    data = query.data
    user = query.from_user

    try:
        await query.answer()
    except Exception:
        pass

    if data == "total_deal":
        text, markup = total_deal_text(), back_button()
    elif data == "my_deal":
        text, markup = my_deal_text(user), back_button()
    elif data == "ranking":
        text, markup = ranking_text(), back_button()
    elif data == "back":
        text = dashboard_text(user.first_name or "User")
        markup = dashboard_buttons()
    else:
        return

    try:
        await query.edit_message_text(
            text, parse_mode=ParseMode.HTML, reply_markup=markup
        )
    except Exception as e:
        # "message is not modified" jaisi galti ignore
        logging.info("edit skipped: %s", e)
