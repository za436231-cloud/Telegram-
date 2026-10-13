# Command: /report
import requests

BOT_TOKEN = "8746757539:AAGkqBRpDOixBP4J2vokGLDyB-C7JBmqngg"

chat_id = message.chat.id
user = message.from_user

name = user.first_name if user.first_name else "User"
uid = user.id

text = (
    "<b>📊 REPORT MENU</b>\n"
    "━━━━━━━━━━━━━━\n"
    f"👤 <b>Name:</b> {name}\n"
    f"🆔 <b>User ID:</b> <code>{uid}</code>\n"
    "━━━━━━━━━━━━━━\n"
    "Neeche se option select karo 👇"
)

buttons = {
    "inline_keyboard": [
        [
            {"text": "📅 Aaj ki Report", "callback_data": "rep_today"},
            {"text": "📆 Weekly Report", "callback_data": "rep_week"}
        ],
        [
            {"text": "👤 My Report", "callback_data": "rep_me"}
        ]
    ]
}

url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
data = {
    "chat_id": chat_id,
    "text": text,
    "parse_mode": "HTML",
    "reply_markup": buttons
}

requests.post(url, json=data)
