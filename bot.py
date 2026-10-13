import os
import html
import random
import string
import sqlite3
import logging
from datetime import datetime

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

BOT_TOKEN = "8656406498:AAEsl02_R0wNLAp4tVMaFNZBa-KOKN3T_2Y"   # apni purani token wali line yahan rakho
GROUP_ID = -1004383728292
DB_PATH = os.environ.get("DB_PATH", "bot.db")


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


def inr(x):
    return f"₹{x:,.2f}"


def esc(x):
    return html.escape(str(x))


async def is_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    member = await context.bot.get_chat_member(
        update.effective_chat.id, update.effective_user.id
    )
    return member.status in ("administrator", "creator")


# ---------- Dashboard ----------
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
            [
                InlineKeyboardButton("📊 My Status", callback_data="my_status"),
                InlineKeyboardButton("📁 My Deals Info", callback_data="my_deals"),
            ],
            [InlineKeyboardButton("⏳ My Pending Deals", callback_data="my_pending")],
            [InlineKeyboardButton("🌍 Escrow Global Status", callback_data="global_status")],
        ]
    )


def back_button():
    return InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="back")]])


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.effective_user.first_name or "User"
    await update.message.reply_text(
        dashboard_text(name),
        parse_mode=ParseMode.HTML,
        reply_markup=dashboard_buttons(),
    )


async def myid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"🆔 Your ID: <code>{update.effective_user.id}</code>",
        parse_mode=ParseMode.HTML,
    )


# ---------- /add and /close (sirf group mein, sirf admin) ----------
async def add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if chat.id != GROUP_ID:
        return
    if not await is_admin(update, context):
        await update.message.reply_text("❌ Sirf admin ye command use kar sakta hai.")
        return

    args = context.args
    if len(args) < 3:
        await update.message.reply_text(
            "Use: <code>/add 500 @buyer @seller</code>", parse_mode=ParseMode.HTML
        )
        return
    try:
        amount = float(args[0].replace(",", ""))
    except ValueError:
        await update.message.reply_text("❌ Amount number mein likho.")
        return

    buyer = args[1].lstrip("@").lower()
    seller = args[2].lstrip("@").lower()
    trade_id = "DL-" + "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
    admin = update.effective_user
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    with db() as con:
        con.execute(
            "INSERT INTO deals (trade_id, group_id, amount, buyer, seller, escrower_id, "
            "escrower_name, status, created_at) VALUES (?,?,?,?,?,?,?,?,?)",
            (trade_id, GROUP_ID, amount, buyer, seller, admin.id,
             admin.first_name or "Admin", "pending", now),
        )

    text = (
        "💰 <b>Deal Added</b>\n"
        f"🆔 <b>Trade ID:</b> <code>{trade_id}</code>\n"
        f"💵 <b>Amount:</b> {inr(amount)}\n"
        f"👤 <b>Buyer:</b> @{esc(buyer)}\n"
        f"👤 <b>Seller:</b> @{esc(seller)}\n"
        f"🛡️ <b>Escrowed By:</b> {esc(admin.first_name or 'Admin')}\n"
        "\nDeal close karne ke liye: "
        f"<code>/close {trade_id}</code>"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)


async def close(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if chat.id != GROUP_ID:
        return
    if not await is_admin(update, context):
        await update.message.reply_text("❌ Sirf admin ye command use kar sakta hai.")
        return
    if not context.args:
        await update.message.reply_text(
            "Use: <code>/close DL-ABC123</code>", parse_mode=ParseMode.HTML
        )
        return

    trade_id = context.args[0].upper()
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    with db() as con:
        row = con.execute(
            "SELECT amount, buyer, seller, escrower_name FROM deals "
            "WHERE trade_id=? AND group_id=? AND status='pending'",
            (trade_id, GROUP_ID),
        ).fetchone()
        if not row:
            await update.message.reply_text("❌ Ye Trade ID pending deals mein nahi mili.")
            return
        con.execute(
            "UPDATE deals SET status='completed', closed_at=? WHERE trade_id=? AND group_id=?",
            (now, trade_id, GROUP_ID),
        )

    amount, buyer, seller, escrower = row
    text = (
        "✅ <b>Deal Completed</b>\n"
        f"🆔 <b>Trade ID:</b> <code>{trade_id}</code>\n"
        f"💵 <b>Released:</b> {inr(amount)}\n\n"
        f"Buyer: @{esc(buyer)}\n"
        f"Seller: @{esc(seller)}\n"
        f"Escrowed By: {esc(escrower)}"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)


# ---------- Button screens (sirf GROUP_ID ka data) ----------
def user_filter(user):
    uname = (user.username or "").lower()
    return uname, user.id


def screen_my_status(user):
    uname, uid = user_filter(user)
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
    note = ""
    if not uname:
        note = "\n\n⚠️ Aapka Telegram username set nahi hai, isliye buyer/seller deals match nahi hongi."
    return (
        "📊 <b>My Status</b> (is group ka)\n"
        "╍╍╍╍╍╍╍╍╍╍╍╍╍╍\n"
        f"📦 Total Deals: <b>{total}</b>\n"
        f"✅ Completed: <b>{done[0]}</b> ({inr(done[1])})\n"
        f"⏳ Pending: <b>{pend[0]}</b> ({inr(pend[1])})"
        f"{note}"
    )


def screen_my_deals(user):
    uname, uid = user_filter(user)
    with db() as con:
        rows = con.execute(
            "SELECT trade_id, amount, buyer, seller, closed_at FROM deals "
            "WHERE group_id=? AND status='completed' AND (buyer=? OR seller=? OR escrower_id=?) "
            "ORDER BY id DESC LIMIT 10",
            (GROUP_ID, uname, uname, uid),
        ).fetchall()
    if not rows:
        return "📁 <b>My Deals Info</b>\n\nAbhi koi completed deal nahi hai."
    lines = ["📁 <b>My Deals Info</b> (last 10)", "╍╍╍╍╍╍╍╍╍╍╍╍╍╍"]
    for t, a, b, s, c in rows:
        lines.append(
            f"🆔 <code>{t}</code> | {inr(a)}\n   @{esc(b)} ➜ @{esc(s)} | {esc(c)}"
        )
    return "\n".join(lines)


def screen_my_pending(user):
    uname, uid = user_filter(user)
    with db() as con:
        rows = con.execute(
            "SELECT trade_id, amount, buyer, seller, created_at FROM deals "
            "WHERE group_id=? AND status='pending' AND (buyer=? OR seller=? OR escrower_id=?) "
            "ORDER BY id DESC LIMIT 10",
            (GROUP_ID, uname, uname, uid),
        ).fetchall()
    if not rows:
        return "⏳ <b>My Pending Deals</b>\n\nAbhi koi pending deal nahi hai."
    lines = ["⏳ <b>My Pending Deals</b>", "╍╍╍╍╍╍╍╍╍╍╍╍╍╍"]
    for t, a, b, s, c in rows:
        lines.append(
            f"🆔 <code>{t}</code> | {inr(a)}\n   @{esc(b)} ➜ @{esc(s)} | {esc(c)}"
        )
    return "\n".join(lines)


def screen_global():
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
        top = con.execute(
            "SELECT escrower_name, COUNT(*), SUM(amount) FROM deals "
            "WHERE group_id=? AND status='completed' "
            "GROUP BY escrower_id ORDER BY COUNT(*) DESC LIMIT 1",
            (GROUP_ID,),
        ).fetchone()
    top_line = (
        f"🏆 Top Escrower: <b>{esc(top[0])}</b> ({top[1]} deals, {inr(top[2])})"
        if top
        else "🏆 Top Escrower: —"
    )
    return (
        "🌍 <b>Escrow Global Status</b> (is group ka)\n"
        "╍╍╍╍╍╍╍╍╍╍╍╍╍╍\n"
        f"📦 Total Deals: <b>{total}</b>\n"
        f"✅ Completed: <b>{done[0]}</b>\n"
        f"💰 Total Amount: <b>{inr(done[1])}</b>\n"
        f"🔝 Biggest Deal: <b>{inr(done[2])}</b>\n"
        f"⏳ Pending: <b>{pend[0]}</b> ({inr(pend[1])})\n"
        f"{top_line}"
    )


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
            "my_status": lambda: screen_my_status(user),
            "my_deals": lambda: screen_my_deals(user),
            "my_pending": lambda: screen_my_pending(user),
            "global_status": screen_global,
        }
        fn = screens.get(data)
        text = fn() if fn else "Unknown option"
        markup = back_button()

    try:
        await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=markup)
    except Exception as e:
        logging.warning("edit failed: %s", e)


def main():
    init_db()
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("myid", myid))
    app.add_handler(CommandHandler("add", add))
    app.add_handler(CommandHandler("close", close))
    app.add_handler(CallbackQueryHandler(on_button))
    print("Bot started...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
