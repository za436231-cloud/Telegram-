from helpers import *

# =====================================================================
# FORM SYSTEM
# =====================================================================


async def send_blank_form(message, user):
    who = mention(user.id, user.first_name)
    text = (
        f"{FILE} {who} <b>Ye form copy karke poora bharo</b> 👇\n\n"
        f"<pre>{esc(BLANK_FORM)}</pre>"
    )
    await reply_html(message, text)


async def form_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message is None or not in_group(update):
        return
    await send_blank_form(update.message, update.effective_user)


async def fees_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if msg is None or not in_group(update):
        return
    args = context.args or []
    if args:
        amount = parse_amount(" ".join(args))
        if amount is None:
            await reply_html(msg, f"{WARN} Amount sahi likho: <code>/fees 500</code>")
            return
        await reply_html(msg, fee_text(amount))
        return
    await ask_fee_amount(context, msg)


async def ask_fee_amount(context, msg):
    waiting = context.bot_data.setdefault("fee_wait", {})
    waiting[(msg.chat_id, msg.from_user.id)] = tm.time() + FEE_WAIT_SECONDS
    await reply_html(
        msg,
        f"{BAG} Deal ka <b>amount</b> bhejo (sirf number, "
        f"{FEE_WAIT_SECONDS // 60} minute ke andar).",
    )


def is_spam(context, chat_id, user_id, text):
    """Ek hi message SPAM_COUNT baar SPAM_SECONDS mein aaye to True."""
    store = context.bot_data.setdefault("spam", {})
    key = (chat_id, user_id)
    now = tm.time()
    norm = " ".join(text.lower().split())
    history = [
        (t, m) for (t, m) in store.get(key, []) if now - t <= SPAM_SECONDS
    ]
    history.append((now, norm))
    store[key] = history
    same = sum(1 for (_, m) in history if m == norm)
    if same >= SPAM_COUNT:
        store[key] = []
        return True
    # memory saaf rakho
    if len(store) > 5000:
        for k in list(store.keys()):
            if not store[k] or now - store[k][-1][0] > SPAM_SECONDS:
                store.pop(k, None)
    return False


async def form_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if msg is None or msg.from_user is None or msg.from_user.is_bot:
        return
    if not in_group(update):
        return
    text = (msg.text or msg.caption or "").strip()
    if not text:
        return
    user = msg.from_user
    chat_id = msg.chat_id

    # 0) Spam check (admin ko chhod kar)
    if user.id not in ADMIN_IDS and is_spam(context, chat_id, user.id, text):
        if not await is_group_admin(context, chat_id, user.id):
            await reply_html(
                msg,
                f"{WARN} {mention(user.id, user.first_name)} "
                "spam mat karo. Ek hi message baar baar mat bhejo.",
            )
            return

    lowered = text.lower()

    # 1) "form" likha -> khali form do
    if lowered == "form":
        await send_blank_form(msg, user)
        return

    # 2) "fees" / "fees 500" / "fees: 500" / "500 fees" -> fee calculate
    match = re.fullmatch(r"fees?\b\s*[:=\-]?\s*(.*)", lowered)
    if match:
        arg = match.group(1).strip()
        if not arg:
            await ask_fee_amount(context, msg)
            return
        amount = parse_amount(arg)
        if amount is not None:
            await reply_html(msg, fee_text(amount))
            return
    else:
        match = re.fullmatch(r"(.+?)\s+fees?", lowered)
        if match:
            amount = parse_amount(match.group(1))
            if amount is not None:
                await reply_html(msg, fee_text(amount))
                return

    # 3) fees ke baad amount ka intezaar
    waiting = context.bot_data.setdefault("fee_wait", {})
    key = (chat_id, user.id)
    if key in waiting:
        if tm.time() > waiting[key]:
            waiting.pop(key, None)
        else:
            amount = parse_amount(text)
            if amount is not None:
                waiting.pop(key, None)
                await reply_html(msg, fee_text(amount))
                return

    # 4) Bhara hua form check karo
    fields = parse_form(text)
    if fields is None:
        return

    missing = [
        name for name in FORM_REQUIRED
        if name not in fields or is_empty(fields[name])
    ]
    if "DEAL AMOUNT" not in missing:
        if find_amount(fields.get("DEAL AMOUNT", "")) is None:
            missing.append("DEAL AMOUNT")

    who = mention(user.id, user.first_name)
    if missing:
        lines = [f"{WARN} {who} form adhura hai. Ye bharo:"]
        for name in missing:
            lines.append(f"• {esc(name)}")
        lines.append("")
        lines.append("Naya form ke liye <b>form</b> likho.")
        await reply_html(msg, "\n".join(lines))
        return

    await reply_html(msg, f"{DONE} <b>{esc(FORM_OK_TEXT)}</b>")


# =====================================================================
# JOIN REQUEST (request approve hoti hai; welcome message SEND_WELCOME se)
# =====================================================================


async def join_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    req = update.chat_join_request
    if req is None or req.chat.id not in GROUP_IDS:
        return
    user = req.from_user
    try:
        await req.approve()
    except Exception as e:
        logging.warning("approve failed: %s", e)
        return

    if not SEND_WELCOME:
        return

    text = "\n".join(
        [
            f"{ce(E_JOIN, '🎉')} {mention(user.id, user.first_name)} "
            "group mein aa gaye!",
            f"{ce(E_WELCOME, '👋')} <b>Welcome!</b>",
            f"{ce(E_TRUSTED, '✅')} Deal shuru karne ke liye "
            "<b>form</b> likho.",
        ]
    )
    try:
        await context.bot.send_message(
            req.chat.id, text, parse_mode=ParseMode.HTML
        )
    except Exception as e:
        logging.warning("welcome failed: %s", e)
