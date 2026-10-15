from core import *

# =====================================================================
# CUSTOM: /add ka naya format (handlers_a.py ke add() ko replace karta hai)
# =====================================================================

# Form ki "T/C (IF ANY)" line padhne ke liye
FORM_LABELS["T/C (IF ANY)"] = "T/C"
FORM_LABELS["T/C"] = "T/C"

NO_TC = ("na", "n/a", "none", "no", "nil", "nahi", "nahin", "-")


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
        "form_msg_id, form_user_id, form_user_name) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            trade_id, chat_id, amount, buyer, seller,
            admin.id, admin.first_name or "Admin", "pending", now_text(),
            form.message_id, form_user.id, form_user.first_name or "User",
        ),
    )

    rate_text, fee = calc_fee(amount)
    lines = [
        f"{BAG} <b>Deal Amount:</b> {inr(amount)}",
        f"📤 <b>Fee:</b> {rate_label(rate_text)} — {inr(fee)}",
        f"📤 <b>Net Release:</b> {inr(amount - fee)}",
        f"🆔 <b>Trade ID:</b> <code>{trade_id}</code>",
        "",
        f"{BUYER} <b>Buyer:</b> {esc(party_show(buyer_raw))}",
        f"{SELLER} <b>Seller:</b> {esc(party_show(seller_raw))}",
        f"📝 <b>Detail:</b> {esc(plain(fields.get('DEAL DETAIL')))}",
        f"⏱️ <b>Expected Time:</b> "
        f"{esc(plain(fields.get('EXPECTED TIME')))}",
        f"📌 <b>T/C:</b> {esc(tc_show(fields.get('T/C')))}",
        "",
        f"{SHIELD} <b>Escrowed By:</b> {user_tag(admin)}",
    ]
    await reply_to_form(form, msg, "\n".join(lines))
