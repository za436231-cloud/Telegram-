import os, json, re, random, time, unicodedata
from html import escape
from collections import defaultdict
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import CommandHandler, CallbackQueryHandler, ContextTypes

# ================= SETTINGS =================
ADMIN_IDS = {7054168366}        # sirf yeh IDs /add aur /close chala sakti hain (naya escrower: ID comma laga ke daalo)
FEE_PERCENT = 2.0               # Fee: 2.00%
TRADE_PREFIX = "ZENOX"          # Trade ID: DL-ZENOX-xxx
GROUP_ID = -1004383728292       # private chat mein dashboard isi group ka dikhega
DATA_FILE = os.environ.get("DATA_FILE", "deals.json")

# ================= STORAGE =================
BOT_TOKEN = os.environ.get("BOT_TOKEN") or "8888295842:AAHrWtTQ2weQ5LoM0QF_Y2nfbYAtFSd3XI4"

def load():
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"deals": []}

def save(d):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False)

# ================= HELPERS =================
def money(x):
    return f"₹{x:,.2f}"

def fmt_elapsed(sec):
    sec = int(max(sec, 0))
    d, r = divmod(sec, 86400)
    h, r = divmod(r, 3600)
    m, s = divmod(r, 60)
    parts = []
    if d: parts.append(f"{d}d")
    if h: parts.append(f"{h}h")
    if m: parts.append(f"{m}m")
    if not parts: parts.append(f"{s}s")
    return " ".join(parts)

def mention(user):
    return f'<a href="tg://user?id={user.id}">{escape(user.full_name or "User")}</a>'

def plain_name(user):
    return f"@{user.username}" if user.username else (user.full_name or "Escrower")

def pick(text, *keys):
    """Form se field nikalta hai (bold-font ko bhi normal bana deta hai)."""
    for line in (text or "").splitlines():
        line = unicodedata.normalize("NFKC", line).strip()
        for k in keys:
            m = re.match(rf"^\W*{k}\W*[:\-]\s*(.+)$", line, re.I)
            if m:
                return m.group(1).strip()
    return None

def calc(amount):
    fee = round(amount * FEE_PERCENT / 100, 2)
    return fee, round(amount - fee, 2)

# ================= /add =================
async def add_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg, user = update.effective_message, update.effective_user

    if user.id not in ADMIN_IDS:
        await msg.reply_text("⛔ Sirf authorised escrower hi /add use kar sakte hain.")
        return

    form = msg.reply_to_message
    if not form or not context.args:
        await msg.reply_text("Escrow form par reply karke likho:\n/add 400")
        return

    try:
        amount = float(context.args[0].replace(",", ""))
        if amount <= 0:
            raise ValueError
    except ValueError:
        await msg.reply_text("❌ Sahi amount likho. Example: /add 400")
        return

    ftext = form.text or form.caption or ""
    seller = pick(ftext, "seller") or "Not Provided"
    detail = pick(ftext, "item", "deal detail", "detail") or "Not Provided"
    etime = pick(ftext, r"expected time(?: to complete deal)?", "time") or "Not Provided"
    tc_raw = pick(ftext, r"t/c(?: \(if any\))?", "terms") or "na"
    tc_final = "Not Provided" if tc_raw.lower() in ("na", "n/a", "no", "none", "-") else tc_raw

    fee, net = calc(amount)

    data = load()
    used = {d["trade_id"] for d in data["deals"]}
    while True:
        trade_id = f"DL-{TRADE_PREFIX}-{random.randint(100, 999)}"
        if trade_id not in used:
            break

    buyer = form.from_user
    card = (
        f"💰 Deal Amount: {money(amount)}\n"
        f"📤 Fee: {FEE_PERCENT:.2f}% — {money(fee)}\n"
        f"📤 Net Release: {money(net)}\n"
        f"🆔 Trade ID: {trade_id}\n\n"
        f"👤 Buyer: {mention(buyer)}\n"
        f"👤 Seller: {escape(seller)}\n"
        f"📝 Detail: {escape(detail)}\n"
        f"⏱️ Expected Time: {escape(etime)}\n"
        f"• T/C (IF ANY) : {escape(tc_raw)}\n"
        f"📌 T/C: {escape(tc_final)}\n\n"
        f"🛡 Escrowed By: {mention(user)}"
    )
    sent = await form.reply_text(card, parse_mode=ParseMode.HTML)

    data["deals"].append({
        "trade_id": trade_id, "chat_id": msg.chat_id,
        "form_msg_id": form.message_id, "card_msg_id": sent.message_id,
        "buyer_id": buyer.id, "buyer_html": mention(buyer),
        "seller": seller, "amount": amount, "fee": fee, "net": net,
        "escrower_id": user.id, "start": time.time(), "status": "open",
    })
    save(data)

# ================= /close =================
async def close_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg, user = update.effective_message, update.effective_user

    if user.id not in ADMIN_IDS:
        await msg.reply_text("⛔ Sirf authorised escrower hi /close use kar sakte hain.")
        return

    ref = msg.reply_to_message
    if not ref:
        await msg.reply_text("Form (ya /add card) par reply karke likho:\n/close 360")
        return

    data = load()
    deal = None
    for d in data["deals"]:
        if (d["chat_id"] == msg.chat_id and d["status"] == "open"
                and ref.message_id in (d["form_msg_id"], d["card_msg_id"])):
            deal = d
            break
    if not deal:
        await msg.reply_text("❌ Is message par koi open deal nahi mili. Pehle /add karo.")
        return

    released = deal["net"]
    if context.args:
        try:
            released = float(context.args[0].replace(",", ""))
        except ValueError:
            await msg.reply_text("❌ Sahi amount likho. Example: /close 360")
            return

    deal.update({"status": "closed", "released": released, "end": time.time(),
                 "closer_id": user.id, "closer_name": plain_name(user)})
    save(data)

    taken = fmt_elapsed(deal["end"] - deal["start"])
    esc = escape(plain_name(user))
    text = (
        "✅ Deal Completed\n"
        f"🎫 Trade ID: {deal['trade_id']}\n"
        f"💎 Released: {money(released)}\n"
        f"🔐 Escrowed By: {mention(user)}\n"
        f"⏳ Time Taken: {taken}\n\n"
        f"~ {deal['buyer_html']} and {escape(deal['seller'])} are requested to drop the vouch before leaving👇🏻\n\n"
        f"<code>🤝 I Vouch {esc} for {money(released)} smooth escrow deal</code>"
    )
    await msg.reply_text(text, parse_mode=ParseMode.HTML)

# ================= DASHBOARD =================
def dash_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 Total Deal", callback_data="dash_total")],
        [InlineKeyboardButton("👤 My Deal Info", callback_data="dash_mine")],
        [InlineKeyboardButton("🏆 Global Ranking", callback_data="dash_rank")],
    ])

def target_chat(chat):
    return chat.id if chat.type in ("group", "supergroup") else GROUP_ID

def stats_total(chat_id):
    deals = [d for d in load()["deals"] if d["chat_id"] == chat_id]
    closed = [d for d in deals if d["status"] == "closed"]
    opened = [d for d in deals if d["status"] == "open"]
    text = (
        "📊 <b>Total Deal (This Group)</b>\n\n"
        f"✅ Closed Deals: {len(closed)}\n"
        f"⏳ Open Deals: {len(opened)}\n"
        f"💰 Total Amount: {money(sum(d['amount'] for d in closed))}\n"
        f"💎 Total Released: {money(sum(d.get('released', 0) for d in closed))}"
    )
    if deals:
        now = time.time()
        text += (
            f"\n\n🕒 Group Active: {fmt_elapsed(now - min(d['start'] for d in deals))}\n"
            f"🕘 Last Deal: {fmt_elapsed(now - max(d['start'] for d in deals))} pehle"
        )
    return text

def stats_mine(chat_id, user):
    uname = f"@{user.username}".lower() if user.username else None
    mine = [d for d in load()["deals"] if d["chat_id"] == chat_id and (
        d["buyer_id"] == user.id or d["escrower_id"] == user.id
        or d.get("closer_id") == user.id
        or (uname and d["seller"].lower() == uname))]
    closed = [d for d in mine if d["status"] == "closed"]
    return (
        f"👤 <b>My Deal Info — {escape(user.full_name or 'User')}</b>\n\n"
        f"📦 Total Deals: {len(mine)}\n"
        f"✅ Closed: {len(closed)}\n"
        f"⏳ Open: {len(mine) - len(closed)}\n"
        f"💰 Closed Amount: {money(sum(d['amount'] for d in closed))}"
    )

def stats_rank():
    board = defaultdict(lambda: [0, 0.0, ""])
    for d in load()["deals"]:
        if d["status"] == "closed":
            b = board[d.get("closer_id", d["escrower_id"])]
            b[0] += 1
            b[1] += d["amount"]
            b[2] = d.get("closer_name", "Escrower")
    top = sorted(board.values(), key=lambda b: (-b[0], -b[1]))[:5]
    if not top:
        return "🏆 <b>Global Ranking</b>\n\nAbhi koi closed deal nahi hai."
    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]
    lines = [f"{medals[i]} {escape(b[2])} — {b[0]} deals — {money(b[1])}" for i, b in enumerate(top)]
    return "🏆 <b>Global Ranking (All Groups)</b>\n\n" + "\n".join(lines)

async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    text = "👋 <b>Escrow Dashboard</b>\n\n" + stats_total(target_chat(chat))
    await update.effective_message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=dash_keyboard())

async def dash_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    cid = target_chat(q.message.chat)
    if q.data == "dash_total":
        text = stats_total(cid)
    elif q.data == "dash_mine":
        text = stats_mine(cid, q.from_user)
    else:
        text = stats_rank()
    try:
        await q.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=dash_keyboard())
    except Exception:
        pass

# ================= REGISTER =================
def register_escrow(app):
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("add", add_cmd))
    app.add_handler(CommandHandler("close", close_cmd))
    app.add_handler(CallbackQueryHandler(dash_cb, pattern="^dash_"))
