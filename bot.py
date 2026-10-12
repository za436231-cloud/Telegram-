import os
import json
import re
import unicodedata
import html
import asyncio
import logging
from telegram import Update, InlineKeyboardButton as Btn, InlineKeyboardMarkup as Markup
from telegram.constants import ParseMode, ChatType
from telegram.error import TelegramError, BadRequest
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    ChatJoinRequestHandler,
    ChatMemberHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

# ================= Settings =================
BOT_TOKEN = os.getenv("BOT_TOKEN", "YAHAN_APNA_BOT_TOKEN_DAALO")
# Apna Telegram user ID (@userinfobot se mil jaata hai). Kai admin ho to comma se alag karo: 123,456
OWNER_ID = os.getenv("OWNER_ID", "7054168366")
# Persistent storage ke liye (Railway/Render volume): DATA_FILE env se path do
# ============================================

OWNER_IDS = {int(x) for x in OWNER_ID.replace(" ", "").split(",") if x.isdigit()}

DATA_FILE = os.getenv(
    "DATA_FILE",
    os.path.join(os.path.dirname(os.path.abspath(file)), "data.json"),
)

EMOJI_APPROVED = "5197474765387864959"
EMOJI_USER = "5316727448644103237"
EMOJI_WELCOME = "5260341314095947411"


def ce(emoji_id: str, fallback: str) -> str:
    return f'<tg-emoji emoji-id="{emoji_id}">{fallback}</tg-emoji>'


DEFAULT_WELCOME = (
    f"{ce(EMOJI_APPROVED, '✅')} <b>Join Request Approved!</b>\n\n"
    f"{ce(EMOJI_USER, '👤')} <b>User:</b> {{user}}\n"
    f"{ce(EMOJI_WELCOME, '🎉')} <b>Welcome to the group!</b>"
)

# ---------------- Data (JSON file) ----------------
DEFAULT_DATA = {
    "groups": {},
    "approved": 0,
    "escrowers": [],
    "settings": {
        "auto_approve": True,
        "delete_seconds": 60,
        "delete_previous": True,
        "welcome_text": None,
        "escrow_enabled": True,
    },
}


def load_data() -> dict:
    data = json.loads(json.dumps(DEFAULT_DATA))
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            saved = json.load(f)
        data["groups"] = saved.get("groups", {})
        data["approved"] = saved.get("approved", 0)
        data["escrowers"] = saved.get("escrowers", [])
        data["settings"].update(saved.get("settings", {}))
    except (FileNotFoundError, json.JSONDecodeError):
        pass
    return data


def save_data() -> None:
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


data = load_data()
last_welcome = {}  # chat_id -> last welcome message id


def is_owner(user_id: int) -> bool:
    return user_id in OWNER_IDS


# ---------------- Panel UI ----------------
def onoff(v: bool) -> str:
    return "ON ✅" if v else "OFF ❌"


def menu_text() -> str:
    s = data["settings"]
    secs = s["delete_seconds"]
    return (
        "🛠 Admin Panel\n\n"
        f"Groups: {len(data['groups'])}\n"
        f"Auto-approve: {onoff(s['auto_approve'])}\n"
        f"Auto delete: {'OFF' if secs == 0 else str(secs) + ' sec'}\n"
        f"Pichla welcome delete: {onoff(s['delete_previous'])}"
    )


def main_menu() -> Markup:
    s = data["settings"]
    return Markup([
        [Btn("📨 Group mein message", callback_data="send"),
         Btn("📢 Broadcast", callback_data="bc")],
        [Btn("✏️ Welcome text", callback_data="wt"),
         Btn("⏱ Delete time", callback_data="dt")],
        [Btn(f"🔁 Pichla delete: {onoff(s['delete_previous'])}", callback_data="dp")],
        [Btn(f"✅ Auto-approve: {onoff(s['auto_approve'])}", callback_data="ap")],
        [Btn("💼 Escrow admins", callback_data="es")],
        [Btn("📊 Stats", callback_data="st")],
    ])


def back_button(text="⬅️ Panel") -> Markup:
    return Markup([[Btn(text, callback_data="menu")]])


async def edit(query, text: str, markup: Markup) -> None:
    try:
        await query.edit_message_text(text, reply_markup=markup)
    except BadRequest as e:
        if "not modified" not in str(e).lower():
            raise


# ---------------- Commands ----------------
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if is_owner(user.id):
        await update.message.reply_text(menu_text(), reply_markup=main_menu())
    else:
        await update.message.reply_text("👋 Hello! Main is group ka welcome bot hoon.")


async def cmd_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(f"Aapka ID: {update.effective_user.id}")


async def cmd_panel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_owner(update.effective_user.id):
        return
    context.user_data.pop("action", None)
    await update.message.reply_text(menu_text(), reply_markup=main_menu())


async def cmd_here(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Group mein /here likho (sirf owner) -> group panel mein add ho jaata hai."""
    if not is_owner(update.effective_user.id):
        return
    chat = update.effective_chat
    data["groups"][str(chat.id)] = chat.title or str(chat.id)
    save_data()
    await update.message.reply_text("✅ Ye group panel mein add ho gaya.")


# ---------------- Panel buttons ----------------
async def on_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    if not is_owner(q.from_user.id):
        await q.answer("Aap allowed nahi ho.", show_alert=True)
        return
    await q.answer()

    d = q.data
    s = data["settings"]

    if d == "menu":
        context.user_data.pop("action", None)
        await edit(q, menu_text(), main_menu())

    elif d == "send":
        if not data["groups"]:
            await edit(q, "Abhi koi group saved nahi hai.\nGroup mein /here likho ya bot ko group mein dobara add karo.", back_button())
            return
        rows = [[Btn(title[:40], callback_data=f"sg:{cid}")] for cid, title in list(data["groups"].items())[:30]]
        rows.append([Btn("⬅️ Panel", callback_data="menu")])
        await edit(q, "Kis group mein message bhejna hai?", Markup(rows))

    elif d.startswith("sg:"):
        cid = int(d[3:])
        context.user_data["action"] = {"type": "send", "chat_id": cid}
        title = data["groups"].get(str(cid), cid)
        await edit(q, f"'{title}' ke liye ab wo message bhejo.\n(Text, photo, video, file, sticker - kuchh bhi)", back_button("❌ Cancel"))

    elif d == "bc":
        context.user_data["action"] = {"type": "broadcast"}
        await edit(q, f"Ab wo message bhejo jo saare {len(data['groups'])} groups mein jaana hai.\n(Text, photo, video - kuchh bhi)", back_button("❌ Cancel"))

    elif d == "wt":
        context.user_data["action"] = {"type": "welcome"}
        await edit(
            q,
            "Naya welcome text bhejo.\n\n"
            "{user} likhoge to wahan user ka username/naam aa jaayega.\n"
            "{group} likhoge to group ka naam aa jaayega.\n"
            "Bold/italic/premium emoji jaisi formatting bhi chalegi.",
            Markup([
                [Btn("♻️ Default par reset", callback_data="wt_reset")],
                [Btn("❌ Cancel", callback_data="menu")],
            ]),
        )

    elif d == "wt_reset":
        s["welcome_text"] = None
        save_data()
        context.user_data.pop("action", None)
        await edit(q, "♻️ Welcome text default par aa gaya.\n\n" + menu_text(), main_menu())

    elif d == "dt":
        opts = [("Off", 0), ("30s", 30), ("1 min", 60), ("2 min", 120), ("5 min", 300), ("10 min", 600)]
        rows = [[Btn(("✅ " if s["delete_seconds"] == v else "") + n, callback_data=f"ds:{v}") for n, v in opts[:3]],
                [Btn(("✅ " if s["delete_seconds"] == v else "") + n, callback_data=f"ds:{v}") for n, v in opts[3:]],
                [Btn("⬅️ Panel", callback_data="menu")]]
        await edit(q, "Welcome message kitni der baad delete ho?", Markup(rows))

    elif d.startswith("ds:"):
        s["delete_seconds"] = int(d[3:])
        save_data()
        await edit(q, menu_text(), main_menu())

elif d == "dp":
        s["delete_previous"] = not s["delete_previous"]
        save_data()
        await edit(q, menu_text(), main_menu())

    elif d == "ap":
        s["auto_approve"] = not s["auto_approve"]
        save_data()
        await edit(q, menu_text(), main_menu())

    elif d == "es":
        context.user_data.pop("action", None)
        await edit(q, escrow_text(), escrow_menu())

    elif d == "es_tg":
        s["escrow_enabled"] = not s["escrow_enabled"]
        save_data()
        await edit(q, escrow_text(), escrow_menu())

    elif d == "es_add":
        context.user_data["action"] = {"type": "escrow_add"}
        await edit(
            q,
            "Admin ka username aur amount range bhejo:\n\n"
            "@username min max\n\n"
            "Example:\n"
            "@admin1 0 5000\n"
            "@admin2 5000 20000\n"
            "@admin3 20000 -\n\n"
            "(max ki jagah - likho to upar koi limit nahi)\n"
            "k / lakh / cr bhi chalega (jaise 5k, 2lakh).\n"
            "Ek saath kai lines bhej sakte ho.",
            Markup([[Btn("❌ Cancel", callback_data="es")]]),
        )

    elif d.startswith("esd:"):
        i = int(d[4:])
        if 0 <= i < len(data["escrowers"]):
            data["escrowers"].pop(i)
            save_data()
        await edit(q, escrow_text(), escrow_menu())

    elif d == "es_clear":
        data["escrowers"] = []
        save_data()
        await edit(q, escrow_text(), escrow_menu())

    elif d == "st":
        text = (
            "📊 Stats\n\n"
            f"Groups: {len(data['groups'])}\n"
            f"Total approved: {data['approved']}\n\n"
            + ("\n".join(f"• {t}" for t in list(data["groups"].values())[:30]) or "Koi group nahi")
        )
        await edit(q, text, back_button())


# ---------------- Owner ka message (panel action) ----------------
async def on_admin_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not is_owner(user.id):
        return
    msg = update.message
    action = context.user_data.get("action")
    if not action:
        await msg.reply_text("Panel kholne ke liye /panel likho.")
        return

    kind = action["type"]

    if kind == "send":
        try:
            await context.bot.copy_message(
                chat_id=action["chat_id"], from_chat_id=msg.chat_id, message_id=msg.message_id
            )
            result = "✅ Message bhej diya."
        except TelegramError as e:
            result = f"❌ Nahi gaya: {e}"
        context.user_data.pop("action", None)
        await msg.reply_text(result, reply_markup=back_button())

    elif kind == "broadcast":
        ok, fail = 0, 0
        for cid in list(data["groups"].keys()):
            try:
                await context.bot.copy_message(chat_id=int(cid), from_chat_id=msg.chat_id, message_id=msg.message_id)
                ok += 1
            except TelegramError:
                fail += 1
            await asyncio.sleep(0.05)
        context.user_data.pop("action", None)
        await msg.reply_text(f"📢 Broadcast ho gaya.\n✅ {ok} groups\n❌ {fail} fail", reply_markup=back_button())

    elif kind == "escrow_add":
        added = []
        for line in (msg.text or "").splitlines():
            parts = line.split()
            if len(parts) != 3:
                continue
            uname, lo, hi = parts
            lo_v = parse_amount(lo)
            if lo_v is None:
                continue
            if hi.lower() in ("-", "max", "no", "none", "inf"):
                hi_v = None
            else:
                hi_v = parse_amount(hi)
                if hi_v is None:
                    continue
            entry = {"username": uname.lstrip("@"), "min": lo_v, "max": hi_v}
            data["escrowers"].append(entry)
            added.append(f"@{entry['username']} : {fmt_range(entry)}")
        if not added:
            await msg.reply_text("❌ Format galat hai. Aise bhejo:\n@admin1 0 5000")
            return
        save_data()
        context.user_data.pop("action", None)
        await msg.reply_text(
            "✅ Add ho gaya:\n" + "\n".join(added),
            reply_markup=Markup([[Btn("💼 Escrow admins", callback_data="es")]]),
        )

    elif kind == "welcome":
        if not msg.text:
            await msg.reply_text("Sirf text bhejo.")
            return
        data["settings"]["welcome_text"] = msg.text_html
        save_data()
        context.user_data.pop("action", None)
        await msg.reply_text("✅ Welcome text save ho gaya.", reply_markup=back_button())


# ---------------- Escrow form system ----------------
AMOUNT_RE = re.compile(
    r"(\d[\d,]*(?:\.\d+)?)\s*(crores?|cr|lakhs?|lacs?|lac|l|k)?(?![a-z])",
    re.IGNORECASE,
)


def parse_amount(raw: str):
    """'5000', '5,000', '1,00,000', '₹5k', '2 lakh', '1.5cr' -> float. Na mile to None."""
    if raw is None:
        return None
    m = AMOUNT_RE.search(raw)
    if not m:
        return None
    try:
        value = float(m.group(1).replace(",", ""))
    except ValueError:
        return None
    unit = (m.group(2) or "").lower()
    if unit == "k":
        value *= 1_000
    elif unit in ("l", "lac", "lacs", "lakh", "lakhs"):
        value *= 100_000
    elif unit in ("cr", "crore", "crores"):
        value *= 10_000_000
    return value


def fmt_amt(v: float) -> str:
    return f"{v:,.0f}" if float(v).is_integer() else f"{v:,.2f}"


def fmt_range(e: dict) -> str:
    if e["max"] is None:
        return f"{fmt_amt(e['min'])} se upar"
    return f"{fmt_amt(e['min'])} - {fmt_amt(e['max'])}"


def escrow_text() -> str:
    lines = [
        "💼 Escrow admins",
        "",
        "Form mein jo DEAL AMOUNT hoga, uske hisab se neeche ka admin tag hoga.",
        "",
    ]
    if data["escrowers"]:
        for i, e in enumerate(data["escrowers"], 1):
            lines.append(f"{i}. @{e['username']} : {fmt_range(e)}")
    else:
        lines.append("Abhi koi admin add nahi hai.")
    return "\n".join(lines)


def escrow_menu() -> Markup:
    rows = [
        [Btn(f"🔍 Form detect: {onoff(data['settings']['escrow_enabled'])}", callback_data="es_tg")],
        [Btn("➕ Admin add karo", callback_data="es_add")],
    ]
    for i, e in enumerate(data["escrowers"]):
        rows.append([Btn(f"🗑 @{e['username']} ({fmt_range(e)})", callback_data=f"esd:{i}")])
    if data["escrowers"]:
        rows.append([Btn("🧹 Sab hata do", callback_data="es_clear")])
    rows.append([Btn("⬅️ Panel", callback_data="menu")])
    return Markup(rows)


def find_escrowers(amount: float) -> list:
    """Amount ke hisab se escrower dhoondo.

    1. Exact range match.
    2. Boundary par (jaise 5000 dono ranges mein) -> sabse specific (highest min) wala.
    3. Gap mein ho (jaise 5000.50 jab ranges 0-5000 aur 5001-20000 hon)
       -> neeche wala escrower, kyunki amount agle range se pehle hi hai.
    4. Sab ranges ke upar / neeche ho -> koi nahi.
    """
    escrowers = data["escrowers"]

    matches = [
        e for e in escrowers
        if e["min"] <= amount and (e["max"] is None or amount <= e["max"])
    ]
    if matches:
        best_min = max(e["min"] for e in matches)
        return [e for e in matches if e["min"] == best_min]

    # Gap check: amount kisi range ke max se upar aur kisi doosre range ke min se neeche
    lower = [e for e in escrowers if e["max"] is not None and e["max"] < amount]
    upper = [e for e in escrowers if e["min"] > amount]
    if lower and upper:
        best_max = max(e["max"] for e in lower)
        return [e for e in lower if e["max"] == best_max]

    return []


def parse_escrow_form(text: str):
    # Fancy bold letters (𝗘𝗦𝗖𝗥𝗢𝗪) ko normal letters mein badal do
    t = unicodedata.normalize("NFKC", text)
    up = t.upper()
    if not ("ESCROW" in up and "SELLER" in up and "BUYER" in up and "AMOUNT" in up):
        return None

    def field(name: str):
        m = re.search(name + r"\s*[:：\-]\s*(.+)", t, re.IGNORECASE)
        return m.group(1).strip() if m else None

    raw = field(r"DEAL\s*AMOUNT") or field(r"AMOUNT")
    amount = parse_amount(raw) if raw else None

return {
        "seller": field(r"SELLER") or "-",
        "buyer": field(r"BUYER") or "-",
        "amount": amount,
        "raw_amount": raw,
    }


async def on_group_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.message
    if not msg or not msg.text or not data["settings"]["escrow_enabled"]:
        return

    form = parse_escrow_form(msg.text)
    if not form:
        return

    amount = form["amount"]
    matches = find_escrowers(amount) if amount is not None else []

    logging.info(
        "Parsed form: %s | matches: %s | escrowers: %s",
        form, [e["username"] for e in matches], data["escrowers"],
    )

    lines = [
        "✅ Escrow form mil gaya",
        "",
        f"👤 Seller: {form['seller']}",
        f"👤 Buyer: {form['buyer']}",
    ]
    if amount is None:
        lines.append("\n⚠️ Deal amount samajh nahi aaya. Form dobara bhejo.")
    else:
        lines.append(f"💰 Amount: {fmt_amt(amount)}")
        if matches:
            tags = " ".join(f"@{e['username']}" for e in matches)
            lines.append(f"\n👑 Escrower: {tags}")
        elif not data["escrowers"]:
            lines.append("\n⚠️ Abhi koi escrower add nahi hai. Owner ko /panel → Escrow admins se add karna hoga.")
        else:
            lines.append("\n⚠️ Is amount ke liye koi escrower set nahi hai.")

    await msg.reply_text("\n".join(lines))


# ---------------- Groups track karna ----------------
async def track_groups(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    ev = update.my_chat_member
    chat = ev.chat
    if chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
        return
    status = ev.new_chat_member.status
    if status in ("member", "administrator"):
        data["groups"][str(chat.id)] = chat.title or str(chat.id)
        save_data()
    elif status in ("left", "kicked"):
        data["groups"].pop(str(chat.id), None)
        save_data()


# ---------------- Join request ----------------
async def safe_delete(bot, chat_id: int, message_id: int) -> None:
    try:
        await bot.delete_message(chat_id=chat_id, message_id=message_id)
    except TelegramError as e:
        logging.warning("Delete nahi hua (%s): %s", message_id, e)


async def delete_later(bot, chat_id: int, message_id: int, delay: int) -> None:
    await asyncio.sleep(delay)
    await safe_delete(bot, chat_id, message_id)
    if last_welcome.get(chat_id) == message_id:
        last_welcome.pop(chat_id, None)


async def approve_and_welcome(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    request = update.chat_join_request
    user = request.from_user
    chat = request.chat
    s = data["settings"]

    data["groups"][str(chat.id)] = chat.title or str(chat.id)

    if not s["auto_approve"]:
        save_data()
        return

    await request.approve()
    data["approved"] += 1
    save_data()

    if user.username:
        user_text = f"@{user.username}"
    else:
        user_text = f'<a href="tg://user?id={user.id}">{html.escape(user.first_name)}</a>'

    template = s["welcome_text"] or DEFAULT_WELCOME

    def build(tpl: str) -> str:
        return tpl.replace("{user}", user_text).replace("{group}", html.escape(chat.title or ""))

    if s["delete_previous"]:
        old_id = last_welcome.pop(chat.id, None)
        if old_id:
            await safe_delete(context.bot, chat.id, old_id)

    try:
        sent = await context.bot.send_message(chat.id, build(template), parse_mode=ParseMode.HTML)
    except TelegramError as e:
        logging.warning("Custom text fail hua (%s), default bhej raha hoon", e)
        sent = await context.bot.send_message(chat.id, build(DEFAULT_WELCOME), parse_mode=
