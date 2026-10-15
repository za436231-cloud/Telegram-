from core import *

# =====================================================================
# /start DASHBOARD
# =====================================================================


def dashboard_text(name):
    lines = [
        f"{STAR} <b>Welcome {esc(name)}!</b>",
        DIVIDER,
        f"{SHIELD} <b>Escrow Bot for @zenoxescrowservice</b>",
        f"{CHAT} <b>Provided by @zenoxescrowservice</b>",
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


# =====================================================================
# /add AND /close (form par reply, sirf ADMIN_IDS, sirf group)
# =====================================================================


async def add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if msg is None or not in_group(update):
        return
    if not is_admin(update):
        await reply_html(msg, f"{WARN} Aap is command ke liye allowed nahi ho.")
        return

    form = msg.reply_to_message
    if form is None:
        await reply_html(
            msg,
            f"{WARN} Form par <b>reply</b> karke likho: <code>/add 400</code>",
        )
        return

    form_user = form.from_user
    if form_user is None or form_user.is_bot:
        await reply_html(msg, f"{WARN} Ye form kisi member ka hona chahiye.")
        return

    form_text = form.text or form.caption or ""
    fields = parse_fields(form_text)
    args = context.args or []

    if args:
        amount = parse_amount(args[0])
    else:
        amount = find_amount(fields.get("DEAL AMOUNT", ""))
    if amount is None:
        await reply_html(
            msg,
            f"{WARN} Amount sahi likho: <code>/add 400</code>",
        )
        return

    buyer = None
    seller = None
    if len(args) > 1:
        buyer = args[1].lstrip("@").lower()
    if len(args) > 2:
        seller = args[2].lstrip("@").lower()
    buyer = buyer or username_in(fields.get("BUYER")) or "-"
    seller = seller or username_in(fields.get("SELLER")) or "-"

    chat_id = update.effective_chat.id
    exists = db_one(
        "SELECT trade_id FROM deals "
        "WHERE group_id=? AND form_msg_id=? AND status='pending'",
        (chat_id, form.message_id),
    )
    if exists:
        await reply_html(
            msg,
            f"{WARN} Is form ka deal pehle se add hai: "
            f"<code>{exists[0]}</code>",
        )
        return

    admin = update.effective_user
    trade_id = new_trade_id()
    db_exec(
        "INSERT INTO deals (trade_id, group_id, amount, buyer, seller, "
        "escrower_id, escrower_name, status, created_at, "
        "form_msg_id, form_user_id, form_user_name) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            trade_id, chat_id, amount, buyer, seller,
            admin.id, admin.first_name or "Admin", "pending", now_text(),
            form.message_id, form_user.id, form_user.first_name or "User",
        ),
    )

    form_name = mention(form_user.id, form_user.first_name)
    lines = [
        f"{BAG} <b>Deal Added</b>",
        f"{TAGI} <b>Trade ID:</b> <code>{trade_id}</code>",
        f"{GEM} <b>Amount:</b> {inr(amount)}",
        f"{USER} <b>Form:</b> {form_name}",
    ]
    if buyer != "-":
        lines.append(f"{BUYER} <b>Buyer:</b> {tag(buyer)}")
    if seller != "-":
        lines.append(f"{SELLER} <b>Seller:</b> {tag(seller)}")
    escrower = esc(admin.first_name or "Admin")
    lines.append(f"{SHIELD} <b>Escrowed By:</b> {escrower}")
    lines.append("")
    lines.append("Close ke liye form par reply karke likho:")
    lines.append("<code>/close 360</code> (360 = release amount)")
    await reply_to_form(form, msg, "\n".join(lines))


async def close(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if msg is None or not in_group(update):
        return
    if not is_admin(update):
        await reply_html(msg, f"{WARN} Aap is command ke liye allowed nahi ho.")
        return

    args = context.args or []
    form = msg.reply_to_message
    chat_id = update.effective_chat.id
    cols = (
        "SELECT id, trade_id, amount, buyer, seller, escrower_name, "
        "form_user_id, form_user_name, form_msg_id FROM deals "
        "WHERE group_id=? AND status='pending' AND "
    )

    if form is not None and args:
        released = parse_amount(args[0])
        row = db_one(cols + "form_msg_id=?", (chat_id, form.message_id))
    elif form is None and len(args) >= 2:
        released = parse_amount(args[1])
        row = db_one(cols + "trade_id=?", (chat_id, args[0].upper()))
    else:
        await reply_html(
            msg,
            f"{WARN} Form par <b>reply</b> karke likho: "
            "<code>/close 360</code>",
        )
        return

    if released is None:
        await reply_html(
            msg, f"{WARN} Release amount sahi number mein likho."
        )
        return
    if row is None:
        await reply_html(
            msg,
            f"{WARN} Is form ka koi pending deal nahi mila. "
            "Pehle /add karo.",
        )
        return

    (deal_id, trade_id, amount, buyer, seller,
     escrower, fuid, fname, form_msg_id) = row

    if released > amount + 0.0001:
        await reply_html(
            msg,
            f"{WARN} Release amount deal amount ({inr(amount)}) "
            "se zyada nahi ho sakta.",
        )
        return

    db_exec(
        "UPDATE deals SET status='completed', closed_at=?, released=? "
        "WHERE id=?",
        (now_text(), released, deal_id),
    )

    lines = [
        f"{DONE} <b>Deal Completed</b>",
        f"{TAGI} <b>Trade ID:</b> <code>{trade_id}</code>",
        f"{GEM} <b>Amount:</b> {inr(amount)}",
        f"{FEE} <b>Fee:</b> {inr(amount - released)}",
        f"{REL} <b>Released:</b> {inr(released)}",
    ]
    if fuid:
        lines.append(f"{USER} <b>Form:</b> {mention(fuid, fname)}")
    if buyer != "-":
        lines.append(f"{BUYER} <b>Buyer:</b> {tag(buyer)}")
    if seller != "-":
        lines.append(f"{SELLER} <b>Seller:</b> {tag(seller)}")
    lines.append(f"{SHIELD} <b>Escrowed By:</b> {esc(escrower)}")
    text = "\n".join(lines)

    if form is not None:
        await reply_to_form(form, msg, text)
    else:
        await reply_html(msg, text)
