import os
import re
import html
import random
import string
import sqlite3
import logging
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

BOT_TOKEN = os.environ.get("BOT_TOKEN") or "8974209978:AAHUZicwKi75gQigVzugwvU44wSyH1DKgO0"

if "YAHAN_APNA_TOKEN" in BOT_TOKEN or ":" not in BOT_TOKEN:
    raise SystemExit("BOT_TOKEN set nahi hai ya galat hai. BotFather wala poora token daalo.")

GROUP_ID = -1004383728292
DB_PATH = os.environ.get("DB_PATH", "bot.db")

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


def tag(x):
    return "-" if x == "-" else f"@{esc(x)}"


def user_tag(user):
    if user.username:
        return f"@{esc(user.username)}"
    return f'<a href="tg://user?id={user.id}">{esc(user.first_name or "User")}</a>'


def mention(uid, name):
    return f'<a href="tg://user?id={uid}">{esc(name or "User")}</a>'


async def is_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    member = await context.bot.get_chat_member(
        update.effective_chat.id, update.effective_user.id
    )
    return member.status in ("administrator", "creator")


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


# ---------- /add and /close (form par reply, sirf admin, sirf group) ----------
async def add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if update.effective_chat.id != GROUP_ID:
        return
    if not await is_admin(update, context):
        await reply_html(msg, f"{WARN} Sirf admin ye command use kar sakta hai.")
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
        await reply_html(msg, f"{WARN} Sirf admin ye command use kar sakta hai.")
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
        f"{BAG} Total Amount: <b>{inr(done[1])}</b>\n"
        f"{FEE} Total Fee: <b>{inr(done[1] - done[3])}</b>\n"
        f"{BIG} Biggest Deal: <b>{inr(done[2])}</b>\n"
        f"{PIN} Pending: <b>{pend[0]}</b> ({inr(pend[1])})"
    )


def deal_line(t, a, r, b, s, status, when):
    icon = DONE if status == "completed" else PIN
    amt = inr(a) if r is None else f"{inr(a)} ➜ {inr(r)}"
    people = ""
    if b != "-" or s != "-":
        people = f"\n   {tag(b)} ➜ {tag(s)}"
    return f"{icon} <code>{t}</code> | {amt}{people}\n   {CAL} {esc(when)}"


def screen_my_deal(user):
    uname = (user.username or "").lower()
    uid = user.id
    where = "group_id=? AND (buyer=? OR seller=? OR escrower_id=? OR form_user_id=?)"
    params = (GROUP_ID, uname, uname, uid, uid)
    with db() as con:
        total = con.execute(f"SELECT COUNT(*) FROM deals WHERE {where}", params).fetchone()[0]
        done = con.execute(
            f"SELECT COUNT(*), COALESCE(SUM(amount),0) FROM deals WHERE {where} AND status='completed'",
            params,
        ).fetchone()
        pend = con.execute(
            f"SELECT COUNT(*), COALESCE(SUM(amount),0) FROM deals WHERE {where} AND status='pending'",
            params,
        ).fetchone()
        rows = con.execute(
            "SELECT trade_id, amount, released, buyer, seller, status, COALESCE(closed_at, created_at) "
            f"FROM deals WHERE {where} ORDER BY id DESC LIMIT 10",
            params,
        ).fetchall()

    head = (
        f"{FILE} <b>My Deal Info</b>\n"
        "╍╍╍╍╍╍╍╍╍╍╍╍╍╍\n"
        f"{CARD} Total: <b>{total}</b>\n"
        f"{DONE} Completed: <b>{done[0]}</b> ({inr(done[1])})\n"
        f"{PIN} Pending: <b>{pend[0]}</b> ({inr(pend[1])})"
    )
    if not rows:
        return head + "\n\nAbhi koi deal nahi hai."

    lines = [head, "\n<b>Last 10 Deals:</b>"]
    for t, a, r, b, s, st, w in rows:
        lines.append(deal_line(t, a, r, b, s, st, w))
    return "\n".join(lines)


def screen_ranking():
    with db() as con:
        rows = con.execute(
            "SELECT MAX(escrower_name), COUNT(*), SUM(amount) FROM deals "
            "WHERE group_id=? AND status='completed' "
            "GROUP BY escrower_id ORDER BY COUNT(*) DESC, SUM(amount) DESC LIMIT 10",
            (GROUP_ID,),
        ).fetchall()
    if not rows:
        return f"{TREND} <b>Global Ranking</b>\n\nAbhi koi completed deal nahi hai."

    medals = ["🥇", "🥈", "🥉"]
    lines = [f"{TREND} <b>Global Ranking</b> (Top Escrowers)", "╍╍╍╍╍╍╍╍╍╍╍╍╍╍"]
    for i, (name, cnt, amt) in enumerate(rows):
        rank = medals[i] if i < 3 else f"{i + 1}."
        lines.append(f"{rank} <b>{esc(name)}</b> — {cnt} deals | {inr(amt)}")
    return "\n".join(lines)


async def on_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user
    data = query.data

    if data == "back":
        text = dashboard_text(user.first_name or "User")
        markup = dashboard_buttons()
    else:
        screens = {
            "total_deal": screen_total,
            "my_deal": lambda: screen_my_deal(user),
            "ranking": screen_ranking,
        }
        fn = screens.get(data)
        text = fn() if fn else "Unknown option"
        markup = back_button()

    try:
        await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=markup)
    except Exception as e:
        logging.warning("edit failed: %s", e)


# ---------- Welcome ----------
def welcome_text(user):
    return (
        f'<tg-emoji emoji-id="{E_JOIN}">✅</tg-emoji> <b>JOIN REQUEST ACCEPT</b>\n\n'
        f'<tg-emoji emoji-id="{E_WELCOME}">👋</tg-emoji> <b>WELCOME</b> {user_tag(user)}\n\n'
        f'<tg-emoji emoji-id="{E_TRUSTED}">🛡</tg-emoji> <b>TRUSTED DEAL ESCROW SERVICE</b>'
    )


async def send_welcome(context: ContextTypes.DEFAULT_TYPE, user):
    await context.bot.send_message(
        chat_id=GROUP_ID,
        text=welcome_text(user),
        parse_mode=ParseMode.HTML,
    )


async def on_join_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    req = update.chat_join_request
    if req.chat.id != GROUP_ID:
        return
    user = req.from_user
    try:
        await req.approve()
        context.bot_data.setdefault("approved", set()).add(user.id)
        await send_welcome(context, user)
    except Exception as e:
        logging.error("Join request fail: %s", e)


async def welcome_new(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != GROUP_ID:
        return
    approved = context.bot_data.setdefault("approved", set())

    for member in update.message.new_chat_members:
        if member.is_bot:
            continue
        if member.id in approved:
            approved.discard(member.id)
            continue
        await send_welcome(context, member)


# ---------- Raat 12 baje lock, subah 6 baje unlock ----------
async def lock_group(context: ContextTypes.DEFAULT_TYPE):
    try:
        await context.bot.set_chat_permissions(GROUP_ID, LOCKED)
        await context.bot.send_message(
            chat_id=GROUP_ID,
            text=f"{LOCK} <b>Group lock ho gaya hai so jao</b>\n\nSubah open hoga 06:00",
            parse_mode=ParseMode.HTML,
        )
    except Exception as e:
        logging.error("Lock fail: %s", e)


async def unlock_group(context: ContextTypes.DEFAULT_TYPE):
    try:
        await context.bot.set_chat_permissions(GROUP_ID, UNLOCKED)
        await context.bot.send_message(
            chat_id=GROUP_ID,
            text=f"{UNLOCK} <b>Group unlock ho gaya hai</b>",
            parse_mode=ParseMode.HTML,
        )
    except Exception as e:
        logging.error("Unlock fail: %s", e)


def main():
    init_db()
    app = Application.builder().token(BOT_TOKEN).build()

    if app.job_queue is None:
        raise SystemExit(
            "JobQueue nahi mila. requirements.txt mein "
            "python-telegram-bot[job-queue]==21.6 likho aur redeploy karo."
        )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("add", add))
    app.add_handler(CommandHandler("close", close))
    app.add_handler(CallbackQueryHandler(on_button))
    app.add_handler(ChatJoinRequestHandler(on_join_request))
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome_new))

    app.job_queue.run_daily(lock_group, time=LOCK_TIME, name="lock_group")
    app.job_queue.run_daily(unlock_group, time=UNLOCK_TIME, name="unlock_group")

    print("Bot started...")
    app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)


if __name__ == "__main__":
    main()
