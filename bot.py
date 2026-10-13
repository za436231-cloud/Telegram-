import os
import html
import logging

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

BOT_TOKEN = "8746757539:AAGkqBRpDOixBP4J2vokGLDyB-C7JBmqngg"


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


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = html.escape(update.effective_user.first_name or "User")

    text = (
        f"⭐️ <b>Welcome {name}!</b>\n"
        "╍╍╍╍╍╍╍╍╍╍╍╍╍╍\n"
        "❤️ <b>Escrow Bot for @rizzlerxescrow</b>\n"
        "💬 <b>Provided by @rizzlerxescrow</b>\n"
        "\n"
        "🍑 <b>This is Your Personal Dashboard:</b>\n"
        "╍╍╍╍╍╍╍╍╍╍╍╍╍╍\n"
        "Select the option below ⚡️"
    )
    await update.message.reply_text(
        text,
        parse_mode=ParseMode.HTML,
        reply_markup=dashboard_buttons(),
    )


async def myid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"🆔 Your ID: <code>{update.effective_user.id}</code>",
        parse_mode=ParseMode.HTML,
    )


async def on_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    replies = {
        "my_status": "📊 <b>My Status</b>\nAbhi koi data nahi hai.",
        "my_deals": "📁 <b>My Deals Info</b>\nAbhi koi deal nahi hai.",
        "my_pending": "⏳ <b>My Pending Deals</b>\nAbhi koi pending deal nahi hai.",
        "global_status": "🌍 <b>Escrow Global Status</b>\nAbhi koi data nahi hai.",
    }
    text = replies.get(query.data, "Unknown option")
    await context.bot.send_message(
        chat_id=query.message.chat_id,
        text=text,
        parse_mode=ParseMode.HTML,
    )


def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("myid", myid))
    app.add_handler(CallbackQueryHandler(on_button))
    print("Bot started...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
