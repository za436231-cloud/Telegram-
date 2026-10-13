import os
import html
import logging
from datetime import time, timezone

from telegram import Update, ChatPermissions
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    MessageHandler,
    ChatJoinRequestHandler,
    filters,
    ContextTypes,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

BOT_TOKEN = "8888295842:AAHrWtTQ2weQ5LoM0QF_Y2nfbYAtFSd3XI4"   # apni token wali line yahan rakho
GROUP_ID = -1004383728292

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


def esc(x):
    return html.escape(str(x))


def user_tag(user):
    if user.username:
        return f"@{esc(user.username)}"
    return f'<a href="tg://user?id={user.id}">{esc(user.first_name or "User")}</a>'


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


# ---------- 1a) Join request aaye to accept + welcome ----------
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


# ---------- 1b) Seedha join karne wale ka welcome ----------
async def welcome_new(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != GROUP_ID:
        return
    approved = context.bot_data.setdefault("approved", set())

    for member in update.message.new_chat_members:
        if member.is_bot:
            continue
        # join request se aaya hai to welcome pehle hi ja chuka hai
        if member.id in approved:
            approved.discard(member.id)
            continue
        await send_welcome(context, member)


# ---------- 2) Raat 12 baje lock, subah 6 baje unlock ----------
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
    app = Application.builder().token(BOT_TOKEN).build()

    if app.job_queue is None:
        raise SystemExit(
            "JobQueue nahi mila. requirements.txt mein "
            "python-telegram-bot[job-queue]==21.6 likho aur redeploy karo."
        )

    app.add_handler(ChatJoinRequestHandler(on_join_request))
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome_new))

    app.job_queue.run_daily(lock_group, time=LOCK_TIME, name="lock_group")
    app.job_queue.run_daily(unlock_group, time=UNLOCK_TIME, name="unlock_group")

    print("Bot started...")
    app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)


if __name__ == "__main__":
    main()
