```python
import telebot

BOT_TOKEN = "8746757539:AAGkqBRpDOixBP4J2vokGLDyB-C7JBmqngg"

bot = telebot.TeleBot(BOT_TOKEN)

@bot.message_handler(commands=['start'])
def start(message):
    bot.reply_to(
        message,
        "👋 Welcome!\n\n"
        "Bot successfully started.\n"
        "Report ke liye /getreport bhejein."
    )

@bot.message_handler(commands=['getreport'])
def get_report(message):
    bot.reply_to(
        message,
        "📊 GET REPORT\n\n"
        "✅ Bot Status: Online\n"
        "🤖 Bot: Working\n"
        "📌 Report: Successfully Generated"
    )

bot.infinity_polling()
```
