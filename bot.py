import os
import re
import html
import random
import string
import sqlite3
import logging
import unicodedata
import time as tm
from datetime import datetime, time, timezone

from telegram import (
    Update,
    ChatPermissions,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ChatJoinRequestHandler,
    filters,
    ContextTypes,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

BOT_TOKEN = os.environ.get("BOT_TOKEN") or "8974209978:AAGHHelHWS0ZV7s9IMrMyGJ8EXzTMAyth1o"

if "YAHAN_APNA_TOKEN" in BOT_TOKEN or ":" not in BOT_TOKEN:
    raise SystemExit("BOT_TOKEN set nahi hai ya galat hai. BotFather wala poora token daalo.")

# Group ka ID. Test group mein chalana ho to us group mein /chatid likhkar ID yahan daalo.
GROUP_ID = -1004383728292
DB_PATH = os.environ.get("DB_PATH", "bot.db")

# Sirf in IDs wale log /add aur /close chala sakte hain.
# Aur admin jodna ho to comma lagakar naya ID likho, jaise [7054168366, 123456789]
ADMIN_IDS = [7054168366]

# Spam rule: itne second ke andar ek hi message itni baar bheja to warning
SPAM_COUNT = 5
SPAM_SECONDS = 60

# "fees" likhne ke baad amount bhejne ke liye kitne second milte hain
FEE_WAIT_SECONDS = 300

# Bhara hua form aane par bot ye likhega
FORM_OK_TEXT = "Maal aa gaya"

# IST 12:00 AM = 18:30 UTC (pichla din), IST 6:00 AM = 00:30 UTC
LOCK_TIME = time(18, 30, tzinfo=timezone.utc)
UNLOCK_TIME = time(0, 30, tzinfo=timezone.utc)


# ---------- Premium emojis ----------
def ce(eid, fallback):
    return f'<tg-emoji emoji-id="{eid}">{fallback}</tg-emoji>'


# Welcome
E_JOIN = "5197474765387864959"
E_WELCOME = "5316727448644103237"
E_TRUSTED = "5821077289185578407"

STAR = ce("5958376256788502078", "⭐️")
CHAT = ce("5891243564309942507", "💬")
BOLT = ce("5843553939672274145", "⚡️")
SIGN = ce("5994636050033545139", "🪧")
BAG = ce("5811989245761426317", "💰")
GEM = ce("5771755323572359189", "💎")
BIG = ce("5778546023349621090", "💎")
TAGI = ce("5985433648810171091", "🏷")
CARD = ce("5936017305585586269", "🪪")
USER = ce("5879770735999717115", "👤")
BUYER = ce("5877530150345641603", "👤")
SELLER = ce("5954175920506933873", "👤")
SHIELD = ce("5926783847453692661", "🛡")
DONE = ce("5920052658743283381", "✅")
REL = ce("5951665890079544884", "✅")
FEE = ce("5967548335542767952", "💳")
CAL = ce("5967382867632722656", "📅")
CHART = ce("5913702317667913862", "📊")
FILE = ce("5956561916573782596", "📄")
TREND = ce("5994378914636500516", "📈")
PIN = ce("5796440171364749940", "📌")
WARN = ce("5881702736843511327", "⚠️")
LOCK = ce("5879895758202735862", "🔒")
UNLOCK = ce("6034962180875490251", "🔓")

LOCKED = ChatPermissions(
    can_send_messages=False,
    can_send_audios=False,
    can_send_documents=False,
    can_send_photos=False,
    can_send_videos=False,
    can_send_video_notes=False,
    can_send_voice_notes=False,
    can_send_polls=False,
    can_send_other_messages=False,
    can_add_web_page_previews=False,
    can_invite_users=False,
    can_change_info=False,
    can_pin_messages=False,
    can_manage_topics=False,
)

UNLOCKED = ChatPermissions(
    can_send_messages=True,
    can_send_audios=True,
    can_send_documents=True,
    can_send_photos=True,
    can_send_videos=True,
    can_send_video_notes=True,
    can_send_voice_notes=True,
    can_send_polls=True,
    can_send_other_messages=True,
    can_add_web_page_previews=True,
    can_invite_users=True,
    can_change_info=False,
    can_pin_messages=False,
    can_manage_topics=False,
)


# ---------- Helpers ----------
def esc(x):
    return html.escape(str(x))


def inr(x):
    return f"₹{x:,.2f}"


def money(x):
    return f"₹{x:.2f}"


def tag(x):
    return "-" if x == "-" else f"@{esc(x)}"


def user_tag(user):
    if user.username:
        return f"@{esc(user.username)}"
    return f'<a href="tg://user?id={user.id}">{esc(user.first_name or "User")}</a>'


def mention(uid, name):
    return f'<a href="tg://user?id={uid}">{esc(name or "User")}</a>'


async def is_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Sirf ADMIN_IDS wale log hi /add aur /close chala sakte hain
    return update.effective_user.id in ADMIN_IDS


async def reply_html(message, text):
    return await message.reply_text(text, parse_mode=ParseMode.HTML)


# ---------- Database ----------
def db():
    return sqlite3.connect(DB_PATH)


def init_db():
    with db() as con:
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS deals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trade_id TEXT,
                group_id INTEGER,
                amount REAL,
                buyer TEXT,
                seller TEXT,
                escrower_id INTEGER,
                escrower_name TEXT,
                status TEXT,
                created_at TEXT,
                closed_at TEXT
            )
            """
        )
        for col, typ in (
            ("form_msg_id", "INTEGER"),
            ("form_user_id", "INTEGER"),
            ("form_user_name", "TEXT"),
            ("released", "REAL"),
        ):
            try:
                con.execute(f"ALTER TABLE deals ADD COLUMN {col} {typ}")
            except sqlite3.OperationalError:
                pass


# ---------- /start dashboard ----------
def dashboard_text(name):
    return (
        f"{STAR} <b>Welcome {esc(name)}!</b>\n"
        "╍╍╍╍╍╍╍╍╍╍╍╍╍╍\n"
        f"{SHIELD} <b>Escrow Bot for @rizzlerxescrow</b>\n"
        f"{CHAT} <b>Provided by @rizzlerxescrow</b>\n"
        "\n"
        f"{SIGN} <b>This is Your Personal Dashboard:</b>\n"
        "╍╍╍╍╍╍╍╍╍╍╍╍╍╍\n"
        f"Select the option below {BOLT}"
    )


def dashboard_buttons():
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("📊 Total Deal", callback_data="total_deal")],
            [InlineKeyboardButton("📁 My Deal Info", callback_data="my_deal")],
            [InlineKeyboardButton("🏆 Global Ranking", callback_data="ranking")],
        ]
    )


def back_button():
    return InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="back")]])


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != "private":
        await update.message.reply_text("Dashboard ke liye bot ke private chat mein /start karo.")
        return
    name = update.effective_user.first_name or "User"
    await update.message.reply_text(
        dashboard_text(name),
        parse_mode=ParseMode.HTML,
        reply_markup=dashboard_buttons(),
    )


async def myid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await reply_html(
        update.message,
        f"{CARD} <b>Your ID:</b> <code>{update.effective_user.id}</code>",
    )


async def chatid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await reply_html(
        update.message,
        f"{CARD} <b>Chat ID:</b> <code>{update.effective_chat.id}</code>",
    )


# ---------- /add and /close (form par reply, sirf ADMIN_IDS, sirf group) ----------
async def add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if update.effective_chat.id != GROUP_ID:
        return
    if not await is_admin(update, context):
        await reply_html(msg, f"{WARN} Aap is command ke liye allowed nahi ho.")
        return

    form = msg.reply_to_message
    if not form:
        await reply_html(msg, f"{WARN} Form par <b>reply</b> karke likho: <code>/add 400</code>")
        return
    if not context.args:
        await reply_html(msg, f"{WARN} Amount bhi likho: <code>/add 400</code>")
        return
    try:
        amount = float(context.args[0].replace(",", ""))
        if amount <= 0:
            raise ValueError
    except ValueError:
        await reply_html(msg, f"{WARN} Amount sahi number mein likho.")
        return

    form_user = form.from_user
    if form_user is None or form_user.is_bot:
        await reply_html(msg, f"{WARN} Ye form kisi member ka hona chahiye.")
        return

    form_text = form.text or form.caption or ""
    found = re.findall(r"@([A-Za-z0-9_]{4,32})", form_text)
    args = context.args
    buyer = args[1].lstrip("@").lower() if len(args) > 1 else (found[0].lower() if len(found) > 0 else "-")
    seller = args[2].lstrip("@").lower() if len(args) > 2 else (found[1].lower() if len(found) > 1 else "-")

    with db() as con:
        exists = con.execute(
            "SELECT trade_id FROM deals WHERE group_id=? AND form_msg_id=? AND status='pending'",
            (GROUP_ID, form.message_id),
        ).fetchone()
        if exists:
            await reply_html(
                msg, f"{WARN} Is form ka deal pehle se add hai: <code>{exists[0]}</code>"
            )
            return

        trade_id = "DL-" + "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
        admin = update.effective_user
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        con.execute(
            "INSERT INTO deals (trade_id, group_id, amount, buyer, seller, escrower_id, "
            "escrower_name, status, created_at, form_msg_id, form_user_id, form_user_name) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (trade_id, GROUP_ID, amount, buyer, seller, admin.id,
             admin.first_name or "Admin", "pending", now,
             form.message_id, form_user.id, form_user.first_name or "User"),
        )

    text = (
        f"{BAG} <b>Deal Added</b>\n"
        f"{TAGI} <b>Trade ID:</b> <code>{trade_id}</code>\n"
        f"{GEM} <b>Amount:</b> {inr(amount)}\n"
        f"{USER} <b>Form:</b> {mention(form_user.id, form_user.first_name)}\n"
    )
    if buyer != "-":
        text += f"{BUYER} <b>Buyer:</b> {tag(buyer)}\n"
    if seller != "-":
        text += f"{SELLER} <b>Seller:</b> {tag(seller)}\n"
    text += (
        f"{SHIELD} <b>Escrowed By:</b> {esc(admin.first_name or 'Admin')}\n"
        "\nClose karne ke liye form par reply karke <code>/close 360</code> jaisa likho "
        "(360 = release amount)."
    )
    await reply_html(form, text)


async def close(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if update.effective_chat.id != GROUP_ID:
        return
    if not await is_admin(update, context):
        await reply_html(msg, f"{WARN} Aap is command ke liye allowed nahi ho.")
        return

    form = msg.reply_to_message
    if not form:
        await reply_html(msg, f"{WARN} Form par <b>reply</b> karke likho: <code>/close 360</code>")
        return
    if not context.args:
        await reply_html(msg, f"{WARN} Release amount bhi likho: <code>/close 360</code>")
        return
    try:
        released = float(context.args[0].replace(",", ""))
        if released <= 0:
            raise ValueError
    except ValueError:
        await reply_html(msg, f"{WARN} Release amount sahi number mein likho.")
        return

    with db() as con:
        row = con.execute(
            "SELECT id, trade_id, amount, buyer, seller, escrower_name, form_user_id, form_user_name "
            "FROM deals WHERE group_id=? AND status='pending' AND form_msg_id=?",
            (GROUP_ID, form.message_id),
        ).fetchone()
        if not row:
            await reply_html(msg, f"{WARN} Is form ka koi pending deal nahi mila. Pehle /add karo.")
            return

        deal_id, trade_id, amount, buyer, seller, escrower, fuid, fname = row
        if released > amount:
            await reply_html(
                msg, f"{WARN} Release amount deal amount ({inr(amount)}) se zyada nahi ho sakta."
            )
            return

        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        con.execute(
            "UPDATE deals SET status='completed', closed_at=?, released=? WHERE id=?",
            (now, released, deal_id),
        )

    fee = amount - released
    text = (
        f"{DONE} <b>Deal Completed</b>\n"
        f"{TAGI} <b>Trade ID:</b> <code>{trade_id}</code>\n"
        f"{GEM} <b>Amount:</b> {inr(amount)}\n"
        f"{FEE} <b>Fee:</b> {inr(fee)}\n"
        f"{REL} <b>Released:</b> {inr(released)}\n"
    )
    if fuid:
        text += f"{USER} <b>Form:</b> {mention(fuid, fname)}\n"
    if buyer != "-":
        text += f"{BUYER} <b>Buyer:</b> {tag(buyer)}\n"
    if seller != "-":
        text += f"{SELLER} <b>Seller:</b> {tag(seller)}\n"
    text += f"{SHIELD} <b>Escrowed By:</b> {esc(escrower)}"

    await reply_html(form, text)


# ---------- Form system ----------
BLANK_FORM = (
    "ESCROW DEAL\n\n"
    "• SELLER : \n\n"
    "• BUYER : \n\n"
    "• DEAL DETAIL : \n\n"
    "• DEAL AMOUNT : \n\n"
    "• EXPECTED TIME TO COMPLETE DEAL : \n\n"
    "• T/C (IF ANY) : \n\n"
    "• ESCROW MORE THAN ESCROWER LIMIT AT YOUR OWN RISK"
)

FORM_LABELS = {
    "SELLER": "SELLER",
    "BUYER": "BUYER",
    "DEAL DETAIL": "DEAL DETAIL",
    "ITEM": "DEAL DETAIL",
    "DEAL AMOUNT": "DEAL AMOUNT",
    "AMOUNT": "DEAL AMOUNT",
    "EXPECTED TIME TO COMPLETE DEAL": "EXPECTED TIME",
    "EXPECTED TIME": "EXPECTED TIME",
}
FORM_REQUIRED = ["SELLER", "BUYER", "DEAL DETAIL", "DEAL AMOUNT", "EXPECTED TIME"]


def parse_form(text):
    """Form jaisa message ho to {field: value} lautata hai, warna None."""
    norm = unicodedata.normalize("NFKC", text)   # bold-font akshar normal ban jate hain
    if "ESCROW DEAL" not in norm.upper():
        return None
    values = {}
    for line in norm.splitlines():
        if ":" not in line:
            continue
        label, value = line.split(":", 1)
        label = re.sub(r"[^A-Za-z/() ]", "", label).strip().upper()
        key = FORM_LABELS.get(label)
        if key:
            values[key] = value.strip()
    if len(values) < 3:
        return None
    return values


def is_empty(value):
    return re.sub(r"[\s_\-.•·:|]+", "", value or "") == ""


async def send_blank_form(message, user):
    await message.reply_text(
        f"{FILE} {mention(user.id, user.first_name)} <b>Ye form copy karke poora bharo</b> 👇\n\n"
        f"<pre>{esc(BLANK_FORM)}</pre>",
        parse_mode=ParseMode.HTML,
    )


async def form_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != GROUP_ID:
        return
    await send_blank_form(update.message, update.effective_user)


async def form_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if msg is None or msg.from_user is None or msg.from_user.is_bot:
        return
    text = (msg.text or msg.caption or "").strip()
    if not text:
        return
    user = msg.from_user

    # 1) "form" likha to khali form bhejo
    if text.lower() == "form":
        await send_blank_form(msg, user)
        return

    # 2) Member ne form bheja to check karo
    values = parse_form(text)
    if values is None:
        return

    missing = [f for f in FORM_REQUIRED if is_empty(values.get(f, ""))]
    who = mention(user.id, user.first_name)

    if len(missing) == len(FORM_REQUIRED):
        await msg.reply_text(
            f"{WARN} {who} <b>Ye form khali hai!</b>\n"
            "Pehle sab details bharo, phir bhejo.\n"
            "Naya form lene ke liye <code>form</code> likho.",
            parse_mode=ParseMode.HTML,
        )
    elif missing:
        await msg.reply_text(
            f"{WARN} {who} <b>Form adhura hai!</b>\n"
            f"Ye details bharo: {esc(', '.join(missing))}",
            parse_mode=ParseMode.HTML,
        )
    else:
        await msg.reply_text(
            f"{DONE} {who} <b>{esc(FORM_OK_TEXT)}</b>",
            parse_mode=ParseMode.HTML,
        )


# ---------- Fees calculate ----------
def calc_fee(amount):
    """Rate text aur fee amount lautata hai."""
    if amount < 200:
        return "Flat ₹10", 10.0
    if amount <= 500:
        return "Flat ₹20", 20.0
    if amount <= 2000:
        rate = 4
    elif amount <= 3000:
        rate = 3.5
    else:
        rate = 3
    return f"{rate:g}%", amount * rate / 100


def parse_amount(text):
    cleaned = re.sub(r"[₹,\s]|rs\.?|inr", "", text.lower())
    try:
        value = float(cleaned)
    except ValueError:
        return None
    return value if value > 0 else None


def fee_text(amount):
    rate_text, fee = calc_fee(amount)
    return (
        f"{BAG} <b>FEE CALCULATE</b>\n\n"
        f"{PIN} Deal: {money(amount)}\n"
        f"{CHART} Rate: {rate_text}\n"
        f"💸 Fee: {money(fee)}\n\n"
        f"{DONE} <b>Total: {money(amount + fee)}</b>"
    )


async def fee_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if msg is None or msg.from_user is None or msg.from_user.is_bot:
        return
    text = (msg.text or "").strip()
    if not text:
        return

    user = msg.from_user
    low = text.lower()
    wait = context.bot_data.setdefault("fee_wait", {})
    now = tm.time()

    # sirf "fees" likha: amount pucho
    if low in ("fee", "fees"):
        wait[user.id] = now + FEE_WAIT_SECONDS
        await msg.reply_text(
            f"{BAG} {mention(user.id, user.first_name)} <b>Kitna amount hai?</b>\n"
            "Amount number mein bhejo, jaise <code>1000</code>",
            parse_mode=ParseMode.HTML,
        )
        return

    amount = None
    direct = re.match(r"^fees?\s+(.+)$", low)
    if direct:
        amount = parse_amount(direct.group(1))
    elif user.id in wait:
        if wait[user.id] < now:
            del wait[user.id]
            return
        amount = parse_amount(text)

    if amount is None:
        return

    wait.pop(user.id, None)
    await msg.reply_text(fee_text(amount), parse_mode=ParseMode.HTML)


# ---------- Spam warning ----------
async def spam_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if msg is None or msg.from_user is None or msg.from_user.is_bot:
        return
    user = msg.from_user
    if user.id in ADMIN_IDS:
        return

    if msg.text:
        key = "t:" + msg.text.strip().lower()
    elif msg.sticker:
        key = "s:" + msg.sticker.file_unique_id
    elif msg.photo:
        key = "p:" + msg.photo[-1].file_unique_id
    elif msg.caption:
        key = "c:" + msg.caption.strip().lower()
    else:
        return

    now = tm.time()
    hist = context.bot_data.setdefault("spam", {}).setdefault(user.id, [])
    hist[:] = [(t, k) for t, k in hist if now - t <= SPAM_SECONDS]
    hist.append((now, key))

    count = sum(1 for _, k in hist if k == key)
    if count < SPAM_COUNT:
        return
    hist.clear()

    # group ke admin ko warning nahi dena
    try:
        member = await context.bot.get_chat_member(GROUP_ID, user.id)
        if member.status in ("administrator", "creator"):
            return
    except Exception:
        pass

    await msg.reply_text(
        f"{WARN} {mention(user.id, user.first_name)} <b>WARNING!</b>\n"
        f"Aapne ek hi message {SPAM_COUNT} baar bheja hai. "
        "Spam mat karo, dobara karne par action liya jayega.",
        parse_mode=ParseMode.HTML,
    )


# ---------- Screens (sirf GROUP_ID ka data) ----------
def screen_total():
    with db() as con:
        total = con.execute(
            "SELECT COUNT(*) FROM deals WHERE group_id=?", (GROUP_ID,)
        ).fetchone()[0]
        done = con.execute(
            "SELECT COUNT(*), COALESCE(SUM(amount),0), COALESCE(MAX(amount),0), "
            "COALESCE(SUM(COALESCE(released, amount)),0) "
            "FROM deals WHERE group_id=? AND status='completed'",
            (GROUP_ID,),
        ).fetchone()
        pend = con.execute(
            "SELECT COUNT(*), COALESCE(SUM(amount),0) FROM deals "
            "WHERE group_id=? AND status='pending'",
            (GROUP_ID,),
        ).fetchone()
    return (
        f"{CHART} <b>Total Deal</b>\n"
        "╍╍╍╍╍╍╍╍╍╍╍╍╍╍\n"
        f"{CARD} Total Deals: <b>{total}</b>\n"
        f"{DONE} Completed: <b>{done[0]}</b>\n"
        f"{BAG} Total
