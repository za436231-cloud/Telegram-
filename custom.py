from core import *
from telegram import ReplyParameters

# =====================================================================
# CUSTOM: /add aur /close ka naya format
# (handlers_a.py ke add() aur close() ko replace karta hai)
# =====================================================================

# Form ki "T/C (IF ANY)" line padhne ke liye
FORM_LABELS["T/C (IF ANY)"] = "T/C"
FORM_LABELS["T/C"] = "T/C"

DETAIL_E = ce("5257965174979042426", "📝")
TIME_E = ce("5258258882022612173", "⏲")

# /close ke emoji. Exact premium emoji chahiye to /emojiid se ID nikal ke
# neeche ID badal do (abhi 🏷 aur 🛡 premium emoji lage hain).
CLOSE_ID_E = TAGI
CLOSE_ESC_E = SHIELD

NO_TC = ("na", "n/a", "none", "no", "nil", "nahi", "nahin", "-")

_cols_ready = False


def ensure_cols():
    """Buyer/Seller ka dikhne wala naam rakhne ke liye 2 naye column."""
    global _cols_ready
    if _cols_ready:
        return
    for col in ("buyer_show", "seller_show"):
        try:
            db_exec(f"ALTER TABLE deals ADD COLUMN {col} TEXT")
        except sqlite3.OperationalError:
            pass
    _cols_ready = True


def new_deal_id():
    n = db_one("SELECT COUNT(*) FROM deals")[0] + 1
    while True:
        code = f"DL-ZENOX-{n}"
        if not db_one("SELECT 1 FROM deals WHERE trade_id=?", (code,)):
            return code
        n += 1


def rate_label(rate_text):
    if rate_text.endswith("%"):
        return f"{float(rate_text[:-1]):.2f}%"
    return rate_text


def party_show(value):
    """Buyer/Seller ko jaisa form mein likha hai waisa dikhao."""
    value = (value or "").strip()
    if is_empty(value):
        return "-"
    found = re.search(r"@([A-Za-z0-9_]{4,32})", value)
    return "@" + found.group(1) if found else value[:60]


def plain(value):
    value = (value or "").strip()
    return "-" if is_empty(value) else value[:200]


def tc_show(value):
    value = (value or "").strip()
    if is_empty(value) or value.lower().strip(" .") in NO_TC:
        return "Not Provided"
    return value[:200]


# =====================================================================
# /add
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
            msg, f"{WARN} Amount sahi likho: <code>/add 400</code>"
        )
        return

    buyer_raw = args[1] if len(args) > 1 else fields.get("BUYER")
    seller_raw = args[2] if len(args) > 2 else fields.get("SELLER")
    buyer = (
        args[1].lstrip("@").lower() if len(args) > 1
        else username_in(fields.get("BUYER")) or "-"
    )
    seller = (
        args[2].lstrip("@").lower() if len(args) > 2
        else username_in(fields.get("SELLER")) or "-"
    )
    buyer_show = party_show(buyer_raw)
    seller_show = party_show(seller_raw)

    ensure_cols()
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
    trade_id = new_deal_id()
    db_exec(
        "INSERT INTO deals (trade_id, group_id, amount, buyer, seller, "
        "escrower_id, escrower_name, status, created_at, "
        "form_msg_id, form_user_id, form_user_name, "
        "buyer_show, seller_show) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            trade_id, chat_id, amount, buyer, seller,
            admin.id, admin.first_name or "Admin", "pending", now_text(),
            form.message_id, form_user.id, form_user.first_name or "User",
            buyer_show, seller_show,
        ),
    )

    rate_text, fee = calc_fee(amount)
    lines = [
        f"{BAG} <b>Deal Amount:</b> {inr(amount)}",
        f"{FEE} <b>Fee:</b> {rate_label(rate_text)} — {inr(fee)}",
        f"{GEM} <b>Net Release:</b> {inr(amount - fee)}",
        f"{TAGI} <b>Trade ID:</b> <code>{trade_id}</code>",
        "",
        f"{BUYER} <b>Buyer:</b> {esc(buyer_show)}",
        f"{SELLER} <b>Seller:</b> {esc(seller_show)}",
        f"{DETAIL_E} <b>Detail:</b> {esc(plain(fields.get('DEAL DETAIL')))}",
        f"{TIME_E} <b>Expected Time:</b> "
        f"{esc(plain(fields.get('EXPECTED TIME')))}",
        f"{PIN} <b>T/C:</b> {esc(tc_show(fields.get('T/C')))}",
        "",
        f"{SHIELD} <b>Escrowed By:</b> {user_tag(admin)}",
    ]
    await reply_to_form(form, msg, "\n".join(lines))


# =====================================================================
# /close
#   - form par reply:            /close 7275
#   - bot ke Deal Added par reply: /close 7275
#   - bina amount ke:            /close  (net release maan lega)
#   - trade id se:               /close DL-ZENOX-1 7275
# =====================================================================


def shown(show, plain_name):
    if show:
        return show
    return "@" + plain_name if plain_name and plain_name != "-" else "-"


async def send_done(update, context, chat_id, form_msg_id, text):
    if form_msg_id:
        try:
            return await context.bot.send_message(
                chat_id,
                text,
                parse_mode=ParseMode.HTML,
                reply_parameters=ReplyParameters(
                    message_id=form_msg_id,
                    allow_sending_without_reply=True,
                ),
            )
        except Exception as e:
            logging.warning("close reply failed: %s", e)
    return await reply_html(update.message, text)


async def close(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if msg is None or not in_group(update):
        return
    if not is_admin(update):
        await reply_html(msg, f"{WARN} Aap is command ke liye allowed nahi ho.")
        return

    ensure_cols()
    args = context.args or []
    replied = msg.reply_to_message
    chat_id = update.effective_chat.id
    cols = (
        "SELECT id, trade_id, amount, buyer, seller, escrower_name, "
        "form_user_id, form_user_name, form_msg_id, "
        "buyer_show, seller_show FROM deals "
        "WHERE group_id=? AND status='pending' AND "
    )

    row = None
    amount_arg = None
    if replied is not None:
        amount_arg = args[0] if args else None
        row = db_one(cols + "form_msg_id=?", (chat_id, replied.message_id))
        if row is None:
            body = (replied.text or replied.caption or "").upper()
            found = re.search(r"DL-[A-Z0-9-]+", body)
            if found:
                row = db_one(
                    cols + "trade_id=?", (chat_id, found.group(0))
                )
    elif args:
        row = db_one(cols + "trade_id=?", (chat_id, args[0].upper()))
        amount_arg = args[1] if len(args) > 1 else None
    else:
        await reply_html(
            msg,
            f"{WARN} Form ya Deal Added message par <b>reply</b> karke "
            "likho: <code>/close 360</code>",
        )
        return

    if row is None:
        await reply_html(
            msg,
            f"{WARN} Is form ka koi pending deal nahi mila. "
            "Pehle /add karo (ya deal pehle hi close ho chuki hai).",
        )
        return

    (deal_id, trade_id, amount, buyer, seller, escrower, fuid, fname,
     form_msg_id, buyer_show, seller_show) = row

    if amount_arg is None:
        released = amount - calc_fee(amount)[1]
    else:
        released = parse_amount(amount_arg)
        if released is None:
            await reply_html(
                msg, f"{WARN} Release amount sahi number mein likho."
            )
            return

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

    closer = update.effective_user
    if closer.username:
        closer_plain = "@" + closer.username
        closer_top = esc(closer_plain)
    else:
        closer_plain = closer.first_name or "Escrower"
        closer_top = mention(closer.id, closer_plain)

    parties = [
        p for p in (shown(buyer_show, buyer), shown(seller_show, seller))
        if p != "-"
    ]
    names = " and ".join(esc(p) for p in parties) or "Buyer and Seller"

    lines = [
        f"{DONE} <b>Deal Completed</b>",
        f"{CLOSE_ID_E} <b>Trade ID:</b> {esc(trade_id)}",
        f"{GEM} <b>Released:</b> {inr(released)}",
        f"{CLOSE_ESC_E} <b>Escrowed By:</b> {closer_top}",
        "",
        f"~ {names} are requested to drop the vouch before leaving👇🏻",
        "",
        f"<code>🤝 I Vouch {esc(closer_plain)} for {inr(released)} "
        "smooth escrow deal</code>",
    ]
    await send_done(update, context, chat_id, form_msg_id, "\n".join(lines))


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
