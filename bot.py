import os
import html
import telebot
from telebot import types

BOT_TOKEN = os.environ.get("BOT_TOKEN")
if not BOT_TOKEN:
    raise SystemExit("8746757539:AAGkqBRpDOixBP4J2vokGLDyB-C7JBmqngg")

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")


def dashboard_buttons():
    kb = types.InlineKeyboardMarkup()
    kb.row(
        types.InlineKeyboardButton("📊 My Status", callback_data="my_status"),
        types.InlineKeyboardButton("📁 My Deals Info", callback_data="my_deals"),
    )
    kb.row(types.InlineKeyboardButton("⏳ My Pending Deals", callback_data="my_pending"))
    kb.row(types.InlineKeyboardButton("🌍 Escrow Global Status", callback_data="global_status"))
    return kb


@bot.message_handler(commands=["start"])
def start(message):
    name = message.from_user.first_name or "User"
    name = html.escape(name)

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
    bot.send_message(message.chat.id, text, reply_markup=dashboard_buttons())


@bot.message_handler(commands=["myid"])
def myid(message):
    bot.reply_to(message, f"🆔 Your ID: <code>{message.from_user.id}</code>")


@bot.callback_query_handler(func=lambda call: True)
def on_button(call):
    bot.answer_callback_query(call.id)
    replies = {
        "my_status": "📊 <b>My Status</b>\nAbhi koi data nahi hai.",
        "my_deals": "📁 <b>My Deals Info</b>\nAbhi koi deal nahi hai.",
        "my_pending": "⏳ <b>My Pending Deals</b>\nAbhi koi pending deal nahi hai.",
        "global_status": "🌍 <b>Escrow Global Status</b>\nAbhi koi data nahi hai.",
    }
    text = replies.get(call.data, "Unknown option")
    bot.send_message(call.message.chat.id, text)


if __name__ == "__main__":
    print("Bot started...")
    bot.infinity_polling(skip_pending=True)
