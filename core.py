import os
import re
import html
import random
import string
import sqlite3
import logging
import unicodedata
import time as tm
from contextlib import closing
from datetime import datetime, time, timedelta, timezone

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
logging.getLogger("httpx").setLevel(logging.WARNING)

# =====================================================================
# SETTINGS (sirf yahi hissa badalna hai)
# =====================================================================
# Token SIRF Railway Variables mein BOT_TOKEN naam se daalo.
# Code mein kabhi token mat likho.
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8974209978:AAFArRuAgsNeTinKTH7glOPcmJ5nPsOpLW8").strip()

# Group ke ID. Test group jodna ho to comma lagakar uska ID likho,
# jaise [-1004383728292, -100123456789]. ID /chatid se milta hai.
GROUP_IDS = [-1004383728292, -1004199368031]

# Sirf in IDs wale log /add aur /close chala sakte hain.
ADMIN_IDS = [7054168366]

# Database file. Railway Volume lagaya ho to DB_PATH=/data/bot.db rakho.
DB_PATH = os.environ.get("DB_PATH", "bot.db")

# Spam: itne second mein ek hi message itni baar bheja to warning
SPAM_COUNT = 5
SPAM_SECONDS = 60

# "fees" likhne ke baad amount bhejne ke liye kitne second milte hain
FEE_WAIT_SECONDS = 300

# Bhara hua form aane par bot ye likhega
FORM_OK_TEXT = "Maal aa gaya"

# Lock/unlock time (UTC mein): 18:30 UTC = 12:00 AM IST
# aur 00:30 UTC = 6:00 AM IST
LOCK_TIME = time(18, 30, tzinfo=timezone.utc)
UNLOCK_TIME = time(0, 30, tzinfo=timezone.utc)

IST = timezone(timedelta(hours=5, minutes=30))

# =====================================================================
# PREMIUM EMOJIS
# =====================================================================


def ce(eid, fallback):
    return f'<tg-emoji emoji-id="{eid}">{fallback}</tg-emoji>'


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

DIVIDER = "╍╍╍╍╍╍╍╍╍╍╍╍╍╍"

# =====================================================================
# LOCK / UNLOCK PERMISSIONS
# =====================================================================
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

# =====================================================================
# HELPERS
# =====================================================================


def esc(x):
    return html.escape(str(x))


def inr(x):
    return f"₹{x:,.2f}"


def money(x):
    return f"₹{x:.2f}"


def tag(x):
    return "-" if x == "-" else f"@{esc(x)}"


def mention(uid, name):
    return f'<a href="tg://user?id={uid}">{esc(name or "User")}</a>'


def user_tag(user):
    if user.username:
        return f"@{esc(user.username)}"
    return mention(user.id, user.first_name)


def now_text():
    return datetime.now(IST).strftime("%Y-%m-%d %H:%M")


def is_admin(update):
    user = update.effective_user
    return user is not None and user.id in ADMIN_IDS


def in_group(update):
    chat = update.effective_chat
    return chat is not None and chat.id in GROUP_IDS


async def reply_html(message, text, **kwargs):
    return await message.reply_text(text, parse_mode=ParseMode.HTML, **kwargs)


async def reply_to_form(form, fallback, text):
    """Form par reply karo; na ho paye to command par reply karo."""
    try:
        return await reply_html(form, text)
    except Exception as e:
        logging.warning("form reply failed: %s", e)
        return await reply_html(fallback, text)


async def is_group_admin(context, chat_id, user_id):
    try:
        member = await context.bot.get_chat_member(chat_id, user_id)
        return member.status in ("administrator", "creator")
    except Exception:
        return False


# =====================================================================
# DATABASE
# =====================================================================
G_SQL = "group_id IN (" + ",".join("?" for _ in GROUP_IDS) + ")"
G_ARGS = tuple(GROUP_IDS)


def _run(sql, params, mode):
    with closing(sqlite3.connect(DB_PATH)) as con:
        cur = con.execute(sql, params)
        if mode == "one":
            result = cur.fetchone()
        elif mode == "all":
            result = cur.fetchall()
        else:
            result = None
        con.commit()
        return result


def db_one(sql, params=()):
    return _run(sql, params, "one")


def db_all(sql, params=()):
    return _run(sql, params, "all")


def db_exec(sql, params=()):
    return _run(sql, params, None)


def init_db():
    folder = os.path.dirname(DB_PATH)
    if folder:
        os.makedirs(folder, exist_ok=True)
    db_exec(
        "CREATE TABLE IF NOT EXISTS deals ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "trade_id TEXT, group_id INTEGER, amount REAL, "
        "buyer TEXT, seller TEXT, escrower_id INTEGER, "
        "escrower_name TEXT, status TEXT, "
        "created_at TEXT, closed_at TEXT)"
    )
    extra = (
        ("form_msg_id", "INTEGER"),
        ("form_user_id", "INTEGER"),
        ("form_user_name", "TEXT"),
        ("released", "REAL"),
    )
    for col, typ in extra:
        try:
            db_exec(f"ALTER TABLE deals ADD COLUMN {col} {typ}")
        except sqlite3.OperationalError:
            pass


def new_trade_id():
    while True:
        chars = string.ascii_uppercase + string.digits
        code = "DL-" + "".join(random.choices(chars, k=6))
        if not db_one("SELECT 1 FROM deals WHERE trade_id=?", (code,)):
            return code


# =====================================================================
# PARSING (amount, form)
# =====================================================================
NUM_RE = re.compile(r"\d[\d,]*(?:\.\d+)?")


def parse_amount(text):
    """Poora text sirf ek number ho to wahi number, warna None."""
    cleaned = (text or "").lower()
    cleaned = re.sub(r"rs\.?|inr|₹|,|\s", "", cleaned)
    if not re.fullmatch(r"\d+(?:\.\d+)?", cleaned):
        return None
    value = float(cleaned)
    return value if 0 < value < 1e9 else None


def find_amount(text):
    """Text mein se pehla number nikalo (form ke amount ke liye)."""
    match = NUM_RE.search(text or "")
    if not match:
        return None
    value = float(match.group(0).replace(",", ""))
    return value if 0 < value < 1e9 else None


def username_in(text):
    match = re.search(r"@([A-Za-z0-9_]{4,32})", text or "")
    return match.group(1).lower() if match else None


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
FORM_REQUIRED = [
    "SELLER",
    "BUYER",
    "DEAL DETAIL",
    "DEAL AMOUNT",
    "EXPECTED TIME",
]

BLANK_FORM = "\n\n".join(
    [
        "ESCROW DEAL",
        "• SELLER : ",
        "• BUYER : ",
        "• DEAL DETAIL : ",
        "• DEAL AMOUNT : ",
        "• EXPECTED TIME TO COMPLETE DEAL : ",
        "• T/C (IF ANY) : ",
        "• ESCROW MORE THAN ESCROWER LIMIT AT YOUR OWN RISK",
    ]
)


def parse_fields(text):
    """'LABEL : value' wali lines se {field: value} banao."""
    norm = unicodedata.normalize("NFKC", text or "")
    values = {}
    for line in norm.splitlines():
        if ":" not in line:
            continue
        label, value = line.split(":", 1)
        label = re.sub(r"[^A-Za-z/() ]", "", label)
        label = " ".join(label.split()).upper()
        key = FORM_LABELS.get(label)
        if key and key not in values:
            values[key] = value.strip()
    return values


def parse_form(text):
    """Form jaisa message ho to fields lautao, warna None."""
    norm = unicodedata.normalize("NFKC", text or "").upper()
    if "ESCROW DEAL" not in norm and "ESCROW FORM" not in norm:
        return None
    values = parse_fields(text)
    return values if len(values) >= 3 else None


def is_empty(value):
    return re.sub(r"[\s_\-.•·:|]+", "", value or "") == ""


# =====================================================================
# FEES
# =====================================================================


def calc_fee(amount):
    """(rate text, fee amount) lautata hai."""
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


def fee_text(amount):
    rate_text, fee = calc_fee(amount)
    lines = [
        f"{BAG} <b>FEE CALCULATE</b>",
        "",
        f"{PIN} Deal: {money(amount)}",
        f"{CHART} Rate: {rate_text}",
        f"💸 Fee: {money(fee)}",
        "",
        f"{DONE} <b>Total: {money(amount + fee)}</b>",
    ]
    return "\n".join(lines)
