from core import *
from handlers_a import *
from handlers_b import *

# =====================================================================
# ERRORS + MAIN
# =====================================================================


async def on_error(update, context: ContextTypes.DEFAULT_TYPE):
    logging.error("Error: %s", context.error, exc_info=context.error)


def check_token():
    if not re.fullmatch(r"\d{6,}:[A-Za-z0-9_-]{30,}", BOT_TOKEN):
        raise SystemExit(
            "BOT_TOKEN set nahi hai ya galat hai. Railway Variables mein "
            "BotFather wala poora token BOT_TOKEN naam se daalo."
        )


def main():
    check_token()
    init_db()

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("myid", myid))
    app.add_handler(CommandHandler("chatid", chatid))
    app.add_handler(CommandHandler("add", add))
    app.add_handler(CommandHandler("close", close))
    app.add_handler(CommandHandler("form", form_cmd))
    app.add_handler(CommandHandler("fees", fees_cmd))
    app.add_handler(CommandHandler("lock", lock_cmd))
    app.add_handler(CommandHandler("unlock", unlock_cmd))
    app.add_handler(CallbackQueryHandler(buttons))
    app.add_handler(ChatJoinRequestHandler(join_request))
    app.add_handler(
        MessageHandler(
            (filters.TEXT | filters.CAPTION) & ~filters.COMMAND,
            form_handler,
        )
    )
    app.add_error_handler(on_error)

    if app.job_queue is None:
        logging.warning(
            "JobQueue nahi mila: auto lock/unlock band hai. "
            "requirements.txt mein python-telegram-bot[job-queue] likho."
        )
    else:
        app.job_queue.run_daily(lock_job, LOCK_TIME, name="lock")
        app.job_queue.run_daily(unlock_job, UNLOCK_TIME, name="unlock")

    logging.info("Bot start ho gaya.")
    app.run_polling(
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True,
    )


if __name__ == "__main__":
    main()
