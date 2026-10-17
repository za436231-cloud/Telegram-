from helpers import *

# =====================================================================
# DEALS: /add aur /close (payment photo ke saath ya bina photo ke)
#
#   Form par reply karke text se:      /add 7500      /close 7275
#   Ya PHOTO bhejo aur caption mein:   /add 7500      /close 7275
#   Photo ho to bot wahi photo result ke saath post karta hai.
#
#   /close ke tareeke:
#     - form par reply:               /close 7275
#     - bot ke Deal Added par reply:  /close 7275
#     - bina amount ke:               /close   (net release maan lega)
#     - trade id se:                  /close DL-ZENOX-1 7275
# =====================================================================


# =====================================================================
# /add
# =====================================================================


async def add_deal(update, context, args, photo_id=None):
    msg = update.message
    if msg is None or not in_group(update):
        return
    if not is_admin(update):
        await reply_html(msg, f"{WARN} Aap is command ke liye allowed nahi ho.")
        return

    if PAYMENT_PHOTO_REQUIRED and photo_id is None:
        await reply_html(
            msg,
            f"{WARN} Payment ka <b>photo</b> bhejo: form par reply karke "
            "photo ke caption mein <code>/add 400</code> likho.",
        )
        return

    form = msg.reply_to_message
    if form is None:
        await reply_html(
            msg,
            f"{WARN} Form par <b>reply</b> karke likho: <code>/add 400</code>",
        )
        return

    form_user = form.from_user
    if form_user is None or form_user.is_bot:
        await reply_html(msg, f"{WARN} Ye form kisi member ka hona chahiye.")
        return

    form_text = form.text or form.caption or ""
    fields = parse_fields(form_text)

    if args:
        amount = parse_amount(args[0])
    else:
        amount = find_amount(fields.get("DEAL AMOUNT", ""))
    if amount is None:
        await reply_html(
            msg, f"{WARN} Amount sahi likho: <code>/add 400</code>"
        )
        return

    buyer_raw = args[1] if len(args) > 1 else fields.get("BUYER")
    seller_raw = args[2] if len(args) > 2 else fields.get("SELLER")
    buyer = (
        args[1].lstrip("@").lower() if len(args) > 1
        else username_in(fields.get("BUYER")) or "-"
    )
    seller = (
        args[2].lstrip("@").lower() if len(args) > 2
        else username_in(fields.get("SELLER")) or "-"
    )
    buyer_show = party_show(buyer_raw)
    seller_show = party_show(seller_raw)

    chat_id = update.effective_chat.id
    exists = db_one(
        "SELECT trade_id FROM deals "
        "WHERE group_id=? AND form_msg_id=? AND status='pending'",
        (chat_id, form.message_id),
    )
    if exists:
        await reply_html(
            msg,
            f"{WARN} Is form ka deal pehle se add hai: "
            f"<code>{exists[0]}</code>",
        )
        return

    admin = update.effective_user
    trade_id = new_trade_id()
    db_exec(
        "INSERT INTO deals (trade_id, group_id, amount, buyer, seller, "
        "escrower_id, escrower_name, status, created_at, "
        "form_msg_id, form_user_id, form_user_name, "
        "buyer_show, seller_show) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            trade_id, chat_id, amount, buyer, seller,
            admin.id, admin.first_name or "Admin", "pending", now_text(),
            form.message_id, form_user.id, form_user.first_name or "User",
            buyer_show, seller_show,
        ),
    )

    rate_text, fee = calc_fee(amount)
    lines = [
        f"{BAG} <b>Deal Amount:</b> {inr(amount)}",
        f"{FEE} <b>Fee:</b> {rate_text} — {inr(fee)}",
        f"{GEM} <b>Net Release:</b> {inr(amount - fee)}",
        f"{TAGI} <b>Trade ID:</b> <code>{trade_id}</code>",
        "",
        f"{BUYER} <b>Buyer:</b> {esc(buyer_show)}",
        f"{SELLER} <b>Seller:</b> {esc(seller_show)}",
        f"{DETAIL_E} <b>Detail:</b> {esc(plain(fields.get('DEAL DETAIL')))}",
        f"{TIME_E} <b>Expected Time:</b> "
        f"{esc(plain(fields.get('EXPECTED TIME')))}",
        f"{PIN} <b>T/C:</b> {esc(tc_show(fields.get('T/C')))}",
        "",
        f"{SHIELD} <b>Escrowed By:</b> {user_tag(admin)}",
    ]
    if photo_id:
        db_exec(
            "UPDATE deals SET add_photo=? WHERE trade_id=?",
            (photo_id, trade_id),
        )
    await send_result(
        update, context, chat_id, form.message_id, "\n".join(lines), photo_id
    )


# =====================================================================
# /close
#   - form par reply:            /close 7275
#   - bot ke Deal Added par reply: /close 7275
#   - bina amount ke:            /close  (net release maan lega)
#   - trade id se:               /close DL-ZENOX-1 7275
# =====================================================================


async def send_result(update, context, chat_id, reply_id, text, photo_id=None):
    """Result message bhejo; photo ho to photo ke caption ke saath."""
    params = {"parse_mode": ParseMode.HTML}
    if reply_id:
        params["reply_parameters"] = ReplyParameters(
            message_id=reply_id, allow_sending_without_reply=True
        )
    sent = None
    try:
        if photo_id:
            visible = len(re.sub(r"<[^>]+>", "", text))
            if visible <= 1000:
                sent = await context.bot.send_photo(
                    chat_id, photo_id, caption=text, **params
                )
            else:
                # caption bahut lamba: photo alag, text alag
                await context.bot.send_photo(
                    chat_id, photo_id,
                    **({"reply_parameters": params["reply_parameters"]}
                       if reply_id else {}),
                )
                sent = await context.bot.send_message(chat_id, text, **params)
        else:
            sent = await context.bot.send_message(chat_id, text, **params)
    except Exception as e:
        logging.warning("result send failed: %s", e)
        return await reply_html(update.message, text)

    if photo_id and DELETE_ADMIN_PHOTO:
        try:
            await update.message.delete()
        except Exception as e:
            logging.info("admin photo delete skipped: %s", e)
    return sent


async def close_deal(update, context, args, photo_id=None):
    msg = update.message
    if msg is None or not in_group(update):
        return
    if not is_admin(update):
        await reply_html(msg, f"{WARN} Aap is command ke liye allowed nahi ho.")
        return

    if PAYMENT_PHOTO_REQUIRED and photo_id is None:
        await reply_html(
            msg,
            f"{WARN} Payment ka <b>photo</b> bhejo: form par reply karke "
            "photo ke caption mein <code>/close 360</code> likho.",
        )
        return

    replied = msg.reply_to_message
    chat_id = update.effective_chat.id
    cols = (
        "SELECT id, trade_id, amount, buyer, seller, escrower_name, "
        "form_user_id, form_user_name, form_msg_id, "
        "buyer_show, seller_show FROM deals "
        "WHERE group_id=? AND status='pending' AND "
    )

    row = None
    amount_arg = None
    if replied is not None:
        amount_arg = args[0] if args else None
        row = db_one(cols + "form_msg_id=?", (chat_id, replied.message_id))
        if row is None:
            body = (replied.text or replied.caption or "").upper()
            found = re.search(r"DL-[A-Z0-9-]+", body)
            if found:
                row = db_one(
                    cols + "trade_id=?", (chat_id, found.group(0))
                )
    elif args:
        row = db_one(cols + "trade_id=?", (chat_id, args[0].upper()))
        amount_arg = args[1] if len(args) > 1 else None
    else:
        await reply_html(
            msg,
            f"{WARN} Form ya Deal Added message par <b>reply</b> karke "
            "likho: <code>/close 360</code>",
        )
        return

    if row is None:
        await reply_html(
            msg,
            f"{WARN} Is form ka koi pending deal nahi mila. "
            "Pehle /add karo (ya deal pehle hi close ho chuki hai).",
        )
        return

    (deal_id, trade_id, amount, buyer, seller, escrower, fuid, fname,
     form_msg_id, buyer_show, seller_show) = row

    if amount_arg is None:
        released = amount - calc_fee(amount)[1]
    else:
        released = parse_amount(amount_arg)
        if released is None:
            await reply_html(
                msg, f"{WARN} Release amount sahi number mein likho."
            )
            return

    if released > amount + 0.0001:
        await reply_html(
            msg,
            f"{WARN} Release amount deal amount ({inr(amount)}) "
            "se zyada nahi ho sakta.",
        )
        return

    db_exec(
        "UPDATE deals SET status='completed', closed_at=?, released=? "
        "WHERE id=?",
        (now_text(), released, deal_id),
    )

    closer = update.effective_user
    if closer.username:
        closer_plain = "@" + closer.username
        closer_top = esc(closer_plain)
    else:
        closer_plain = closer.first_name or "Escrower"
        closer_top = mention(closer.id, closer_plain)

    parties = [
        p for p in (shown(buyer_show, buyer), shown(seller_show, seller))
        if p != "-"
    ]
    names = " and ".join(esc(p) for p in parties) or "Buyer and Seller"

    lines = [
        f"{DONE} <b>Deal Completed</b>",
        f"{CLOSE_ID_E} <b>Trade ID:</b> {esc(trade_id)}",
        f"{GEM} <b>Released:</b> {inr(released)}",
        f"{CLOSE_ESC_E} <b>Escrowed By:</b> {closer_top}",
        "",
        f"~ {names} are requested to drop the vouch before leaving👇🏻",
        "",
        f"<code>🤝 I Vouch {esc(closer_plain)} for {inr(released)} "
        "smooth escrow deal</code>",
    ]
    if photo_id:
        db_exec(
            "UPDATE deals SET close_photo=? WHERE id=?", (photo_id, deal_id)
        )
    await send_result(
        update, context, chat_id, form_msg_id, "\n".join(lines), photo_id
    )


async def add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await add_deal(update, context, context.args or [])


async def close(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await close_deal(update, context, context.args or [])


async def photo_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Photo + caption mein /add ya /close."""
    msg = update.message
    if msg is None or not msg.photo:
        return
    found = re.match(
        r"^/(add|close)(?:@\w+)?(?:\s+(.*))?$",
        (msg.caption or "").strip(),
        re.S | re.I,
    )
    if not found:
        return
    args = (found.group(2) or "").split()
    photo_id = msg.photo[-1].file_id
    if found.group(1).lower() == "add":
        await add_deal(update, context, args, photo_id)
    else:
        await close_deal(update, context, args, photo_id)
