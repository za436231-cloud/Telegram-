import os
import html
import sqlite3
import logging
from datetime import time, timezone

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
BOT_TOKEN = "8888295842:AAHrWtTQ2weQ5LoM0QF_Y2nfbYAtFSd3XI4"   # apni token wali line yahan rakho
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

BOT_TOKEN = "8888295842:AAHrWtTQ2weQ5LoM0QF_Y2nfbYAtFSd3XI4"   # apni token wali line yahan rakho
GROUP_ID = -1004383728292
DB_PATH = os.environ.get("DB_PATH", "bot.db")

# IST 12:00 AM = 18:30 UTC (pichla din), IST 6:00 AM = 00:30 UTC
LOCK_TIME = time(18, 30, tzinfo=timezone.utc)
UNLOCK_TIME = time(0, 30, tzinfo=timezone.utc)

# Premium emoji IDs
E_JOIN = "5197474765387864959"
E_WELCOME = "5316727448644103237"
E_TRUSTED = "5821077289185578407"

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


# ---------- /start dashboard ----------
def dashboard_text(name):
    return (
        f"⭐️ <b>Welcome {esc(name)}!</b>\n"
        "╍╍╍╍╍╍╍╍╍╍╍╍╍╍\n"
        "❤️ <b>Escrow Bot for @rizzlerxescrow</b>\n"
        "💬 <b>Provided by @rizzlerxescrow</b>\n"
        "\n"
        "🍑 <b>This is Your Personal Dashboard:</b>\n"
        "╍╍╍╍╍╍╍╍╍╍╍╍╍╍\n"
        "Select the option below ⚡️"
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


# ---------- Screens (sirf GROUP_ID ka data) ----------
def screen_total():
    with db() as con:
        total = con.execute(
            "SELECT COUNT(*) FROM deals WHERE group_id=?", (GROUP_ID,)
        ).fetchone()[0]
        done = con.execute(
            "SELECT COUNT(*), COALESCE(SUM(amount),0), COALESCE(MAX(amount),0) "
            "FROM deals WHERE group_id=? AND status='completed'",
            (GROUP_ID,),
        ).fetchone()
        pend = con.execute(
            "SELECT COUNT(*), COALESCE(SUM(amount),0) FROM deals "
            "WHERE group_id=? AND status='pending'",
            (GROUP_ID,),
        ).fetchone()
    return (
        "📊 <b>Total Deal</b>\n"
        "╍╍╍╍╍╍╍╍╍╍╍╍╍╍\n"
        f"📦 Total Deals: <b>{total}</b>\n"
        f"✅ Completed: <b>{done[0]}</b>\n"
        f"💰 Total Amount: <b>{inr(done[1])}</b>\n"
        f"🔝 Biggest Deal: <b>{inr(done[2])}</b>\n"
        f"⏳ Pending: <b>{pend[0]}</b> ({inr(pend[1])})"
    )


def deal_line(t, a, b, s, status, when):
    icon = "✅" if status == "completed" else "⏳"
    people = ""
    if b != "-" or s != "-":
        people = f"\n   {tag(b)} ➜ {tag(s)}"
    return f"{icon} <code>{t}</code> | {inr(a)}{people}\n   🕒 {esc(when)}"


def screen_my_deal(user):
    uname = (user.username or "").lower()
    uid = user.id
    where = "group_id=? AND (buyer=? OR seller=? OR escrower_id=?)"
    params = (GROUP_ID, uname, uname, uid)
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
            "SELECT trade_id, amount, buyer, seller, status, COALESCE(closed_at, created_at) "
            f"FROM deals WHERE {where} ORDER BY id DESC LIMIT 10",
            params,
        ).fetchall()

    head = (
        "📁 <b>My Deal Info</b>\n"
        "╍╍╍╍╍╍╍╍╍╍╍╍╍╍\n"
        f"📦 Total: <b>{total}</b>\n"
        f"✅ Completed: <b>{done[0]}</b> ({inr(done[1])})\n"
        f"⏳ Pending: <b>{pend[0]}</b> ({inr(pend[1])})"
    )
    if not uname:
        head += "\n\n⚠️ Aapka Telegram username set nahi hai, isliye buyer/seller deals match nahi hongi."
    if not rows:
        return head + "\n\nAbhi koi deal nahi hai."

    lines = [head, "\n<b>Last 10 Deals:</b>"]
    for t, a, b, s, st, w in rows:
        lines.append(deal_line(t, a, b, s, st, w))
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
        return "🏆 <b>Global Ranking</b>\n\nAbhi koi completed deal nahi hai."

    medals = ["🥇", "🥈", "🥉"]
    lines = ["🏆 <b>Global Ranking</b> (Top Escrowers)", "╍╍╍╍╍╍╍╍╍╍╍╍╍╍"]
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
            text="<b>Group lock ho gaya hai so jao</b>\n\nSubah open hoga 06:00",
            parse_mode=ParseMode.HTML,
        )
    except Exception as e:
        logging.error("Lock fail: %s", e)


async def unlock_group(context: ContextTypes.DEFAULT_TYPE):
    try:
        await context.bot.set_chat_permissions(GROUP_ID, UNLOCKED)
        await context.bot.send_message(
            chat_id=GROUP_ID,
            text="<b>Group unlock ho gaya hai</b>",
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
    app.add_handler(CallbackQueryHandler(on_button))
    app.add_handler(ChatJoinRequestHandler(on_join_request))
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome_new))

    app.job_queue.run_daily(lock_group, time=LOCK_TIME, name="lock_group")
    app.job_queue.run_daily(unlock_group, time=UNLOCK_TIME, name="unlock_group")

    print("Bot started...")
    app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)


if __name__ == "__main__":
    main()
