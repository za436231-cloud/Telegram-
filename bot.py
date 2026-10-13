chat_id = message.chat.id
user = message.from_user

name = user.first_name if user.first_name else "User"
name = name.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

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

buttons = {
    "inline_keyboard": [
        [
            {"text": "📊 My Status", "callback_data": "my_status"},
            {"text": "📁 My Deals Info", "callback_data": "my_deals"}
        ],
        [
            {"text": "⏳ My Pending Deals", "callback_data": "my_pending"}
        ],
        [
            {"text": "🌍 Escrow Global Status", "callback_data": "global_status"}
        ]
    ]
}

try:
    bot.sendMessage(text, chat_id=chat_id, parse_mode="HTML", reply_markup=buttons)
except:
    bot.sendMessage(text, chat_id=chat_id, parse_mode="HTML")
