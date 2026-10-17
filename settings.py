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
    ReplyParameters,
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
BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()

# Group ke ID. Test group jodna ho to comma lagakar uska ID likho,
# jaise [-1004383728292, -100123456789]. ID /chatid se milta hai.
GROUP_IDS = [-1004383728292]

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

# /add aur /close mein payment ka photo
# True karoge to bina photo ke /add aur /close nahi chalenge
PAYMENT_PHOTO_REQUIRED = False
# True karoge to admin ka photo wala message result ke baad delete ho jayega
# (bot ko "Delete messages" right chahiye)
DELETE_ADMIN_PHOTO = False

# Group join request approve hone par welcome message (True = bheje)
SEND_WELCOME = False

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
DETAIL_E = ce("5257965174979042426", "📝")
TIME_E = ce("5258258882022612173", "⏲")

# /close ke emoji (exact premium emoji chahiye to /emojiid se ID nikalo)
CLOSE_ID_E = TAGI
CLOSE_ESC_E = SHIELD

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
