from settings import *

# =====================================================================
# HELPERS
# =====================================================================


def esc(x):
    return html.escape(str(x))


def inr(x):
    return f"₹{x:,.2f}"


def money(x):
    return f"₹{x:.2f}"


def tag(x):
    return "-" if x == "-" else f"@{esc(x)}"


def mention(uid, name):
    return f'<a href="tg://user?id={uid}">{esc(name or "User")}</a>'


def user_tag(user):
    if user.username:
        return f"@{esc(user.username)}"
    return mention(user.id, user.first_name)


def now_text():
    return datetime.now(IST).strftime("%Y-%m-%d %H:%M")


def is_admin(update):
    user = update.effective_user
    return user is not None and user.id in ADMIN_IDS


def in_group(update):
    chat = update.effective_chat
    return chat is not None and chat.id in GROUP_IDS


async def reply_html(message, text, **kwargs):
    return await message.reply_text(text, parse_mode=ParseMode.HTML, **kwargs)


async def reply_to_form(form, fallback, text):
    """Form par reply karo; na ho paye to command par reply karo."""
    try:
        return await reply_html(form, text)
    except Exception as e:
        logging.warning("form reply failed: %s", e)
        return await reply_html(fallback, text)


async def is_group_admin(context, chat_id, user_id):
    try:
        member = await context.bot.get_chat_member(chat_id, user_id)
        return member.status in ("administrator", "creator")
    except Exception:
        return False


# =====================================================================
# DATABASE
# =====================================================================
G_SQL = "group_id IN (" + ",".join("?" for _ in GROUP_IDS) + ")"
G_ARGS = tuple(GROUP_IDS)


def _run(sql, params, mode):
    with closing(sqlite3.connect(DB_PATH)) as con:
        cur = con.execute(sql, params)
        if mode == "one":
            result = cur.fetchone()
        elif mode == "all":
            result = cur.fetchall()
        else:
            result = None
        con.commit()
        return result


def db_one(sql, params=()):
    return _run(sql, params, "one")


def db_all(sql, params=()):
    return _run(sql, params, "all")


def db_exec(sql, params=()):
    return _run(sql, params, None)


def init_db():
    folder = os.path.dirname(DB_PATH)
    if folder:
        os.makedirs(folder, exist_ok=True)
    db_exec(
        "CREATE TABLE IF NOT EXISTS deals ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "trade_id TEXT, group_id INTEGER, amount REAL, "
        "buyer TEXT, seller TEXT, escrower_id INTEGER, "
        "escrower_name TEXT, status TEXT, "
        "created_at TEXT, closed_at TEXT)"
    )
    extra = (
        ("form_msg_id", "INTEGER"),
        ("form_user_id", "INTEGER"),
        ("form_user_name", "TEXT"),
        ("released", "REAL"),
        ("buyer_show", "TEXT"),
        ("seller_show", "TEXT"),
        ("add_photo", "TEXT"),
        ("close_photo", "TEXT"),
    )
    for col, typ in extra:
        try:
            db_exec(f"ALTER TABLE deals ADD COLUMN {col} {typ}")
        except sqlite3.OperationalError:
            pass


def new_trade_id():
    n = db_one("SELECT COUNT(*) FROM deals")[0] + 1
    while True:
        code = f"DL-ZENOX-{n}"
        if not db_one("SELECT 1 FROM deals WHERE trade_id=?", (code,)):
            return code
        n += 1


# =====================================================================
# PARSING (amount, form)
# =====================================================================
NUM_RE = re.compile(r"\d[\d,]*(?:\.\d+)?")


def parse_amount(text):
    """Poora text sirf ek number ho to wahi number, warna None."""
    cleaned = (text or "").lower()
    cleaned = re.sub(r"rs\.?|inr|₹|,|\s", "", cleaned)
    if not re.fullmatch(r"\d+(?:\.\d+)?", cleaned):
        return None
    value = float(cleaned)
    return value if 0 < value < 1e9 else None


def find_amount(text):
    """Text mein se pehla number nikalo (form ke amount ke liye)."""
    match = NUM_RE.search(text or "")
    if not match:
        return None
    value = float(match.group(0).replace(",", ""))
    return value if 0 < value < 1e9 else None


def username_in(text):
    match = re.search(r"@([A-Za-z0-9_]{4,32})", text or "")
    return match.group(1).lower() if match else None


FORM_LABELS = {
    "SELLER": "SELLER",
    "BUYER": "BUYER",
    "DEAL DETAIL": "DEAL DETAIL",
    "ITEM": "DEAL DETAIL",
    "DEAL AMOUNT": "DEAL AMOUNT",
    "AMOUNT": "DEAL AMOUNT",
    "EXPECTED TIME TO COMPLETE DEAL": "EXPECTED TIME",
    "EXPECTED TIME": "EXPECTED TIME",
    "T/C (IF ANY)": "T/C",
    "T/C": "T/C",
}
FORM_REQUIRED = [
    "SELLER",
    "BUYER",
    "DEAL DETAIL",
    "DEAL AMOUNT",
    "EXPECTED TIME",
]

BLANK_FORM = "\n\n".join(
    [
        "ESCROW DEAL",
        "• SELLER : ",
        "• BUYER : ",
        "• DEAL DETAIL : ",
        "• DEAL AMOUNT : ",
        "• EXPECTED TIME TO COMPLETE DEAL : ",
        "• T/C (IF ANY) : ",
        "• ESCROW MORE THAN ESCROWER LIMIT AT YOUR OWN RISK",
    ]
)


def parse_fields(text):
    """'LABEL : value' wali lines se {field: value} banao."""
    norm = unicodedata.normalize("NFKC", text or "")
    values = {}
    for line in norm.splitlines():
        if ":" not in line:
            continue
        label, value = line.split(":", 1)
        label = re.sub(r"[^A-Za-z/() ]", "", label)
        label = " ".join(label.split()).upper()
        key = FORM_LABELS.get(label)
        if key and key not in values:
            values[key] = value.strip()
    return values


def parse_form(text):
    """Form jaisa message ho to fields lautao, warna None."""
    norm = unicodedata.normalize("NFKC", text or "").upper()
    if "ESCROW DEAL" not in norm and "ESCROW FORM" not in norm:
        return None
    values = parse_fields(text)
    return values if len(values) >= 3 else None


def is_empty(value):
    return re.sub(r"[\s_\-.•·:|]+", "", value or "") == ""


# =====================================================================
# FEES
# =====================================================================


def calc_fee(amount):
    """(rate text, fee amount) lautata hai."""
    if amount < 200:
        return "Flat ₹10", 10.0
    if amount <= 500:
        return "Flat ₹20", 20.0
    if amount <= 2000:
        rate = 4
    elif amount <= 3000:
        rate = 3.5
    else:
        rate = 3
    return f"{rate:.2f}%", amount * rate / 100


def fee_text(amount):
    rate_text, fee = calc_fee(amount)
    lines = [
        f"{BAG} <b>FEE CALCULATE</b>",
        "",
        f"{PIN} Deal: {money(amount)}",
        f"{CHART} Rate: {rate_text}",
        f"💸 Fee: {money(fee)}",
        "",
        f"{DONE} <b>Total: {money(amount + fee)}</b>",
    ]
    return "\n".join(lines)


# =====================================================================
# DISPLAY HELPERS (/add aur /close ke liye)
# =====================================================================
NO_TC = ("na", "n/a", "none", "no", "nil", "nahi", "nahin", "-")


def party_show(value):
    """Buyer/Seller ko jaisa form mein likha hai waisa dikhao."""
    value = (value or "").strip()
    if is_empty(value):
        return "-"
    found = re.search(r"@([A-Za-z0-9_]{4,32})", value)
    return "@" + found.group(1) if found else value[:60]


def shown(show, plain_name):
    if show:
        return show
    return "@" + plain_name if plain_name and plain_name != "-" else "-"


def plain(value):
    value = (value or "").strip()
    return "-" if is_empty(value) else value[:200]


def tc_show(value):
    value = (value or "").strip()
    if is_empty(value) or value.lower().strip(" .") in NO_TC:
        return "Not Provided"
    return value[:200]
