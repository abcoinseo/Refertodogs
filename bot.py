import telebot
from telebot import types
import sqlite3

TOKEN = "8548616406:AAHOrP5Y3mIrzQC9h69GPMShRpcWOgNHqsw"
CHANNEL_USERNAME = "@veloxstrat"
ADMIN_ID = 8101021767

bot = telebot.TeleBot(TOKEN)

# ---------- DATABASE ----------
conn = sqlite3.connect("data.db", check_same_thread=False)
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    ref_by INTEGER,
    balance INTEGER DEFAULT 0
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS withdraw (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    amount INTEGER,
    address TEXT
)
""")
conn.commit()


# ---------- FORCE JOIN ----------
def is_joined(user_id):
    try:
        member = bot.get_chat_member(CHANNEL_USERNAME, user_id)
        return member.status in ["member", "administrator", "creator"]
    except:
        return False


def join_markup():
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton(
        "✅ Join Channel", url="https://t.me/veloxstrat"))
    return markup


# ---------- START ----------
@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.chat.id
    ref = None

    if len(message.text.split()) > 1:
        ref = int(message.text.split()[1])

    cur.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
    if not cur.fetchone():
        cur.execute("INSERT INTO users (user_id, ref_by) VALUES (?,?)", (user_id, ref))
        conn.commit()

    if not is_joined(user_id):
        bot.send_message(
            user_id,
            "👋 Welcome to Refer to DOGS Bot\n\n"
            "🔒 To use this bot you must join our channel.",
            reply_markup=join_markup()
        )
        return

    main_menu(message)


# ---------- MAIN MENU ----------
def main_menu(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("🐶 My Balance", "👥 Refer")
    markup.add("💸 Withdraw")
    bot.send_message(
        message.chat.id,
        "🎉 Welcome Refer to DOGS Bot\n\nEarn DOGS by referring friends!",
        reply_markup=markup
    )


# ---------- CHECK JOIN EVERY MESSAGE ----------
@bot.message_handler(func=lambda m: True)
def checker(message):
    user_id = message.chat.id

    if not is_joined(user_id):
        bot.send_message(
            user_id,
            "❌ You must join our channel first.",
            reply_markup=join_markup()
        )
        return

    if message.text == "🐶 My Balance":
        cur.execute("SELECT balance FROM users WHERE user_id=?", (user_id,))
        bal = cur.fetchone()[0]
        bot.send_message(user_id, f"🐶 Your Balance: {bal} DOGS")

    elif message.text == "👥 Refer":
        link = f"https://t.me/{bot.get_me().username}?start={user_id}"
        bot.send_message(
            user_id,
            f"👥 Refer friends & earn 50 DOGS\n\n🔗 Your link:\n{link}"
        )

    elif message.text == "💸 Withdraw":
        cur.execute("SELECT balance FROM users WHERE user_id=?", (user_id,))
        bal = cur.fetchone()[0]

        if bal < 1000:
            bot.send_message(user_id, "❌ Minimum withdraw is 1000 DOGS")
            return

        msg = bot.send_message(
            user_id,
            "💸 Send your TON wallet address:"
        )
        bot.register_next_step_handler(msg, get_address)


# ---------- WITHDRAW FLOW ----------
def get_address(message):
    address = message.text
    msg = bot.send_message(
        message.chat.id,
        "Enter withdraw amount (1000 - 5000 DOGS):"
    )
    bot.register_next_step_handler(msg, get_amount, address)


def get_amount(message, address):
    try:
        amount = int(message.text)
        user_id = message.chat.id

        if amount < 1000 or amount > 5000:
            bot.send_message(user_id, "❌ Invalid amount")
            return

        cur.execute("SELECT balance FROM users WHERE user_id=?", (user_id,))
        bal = cur.fetchone()[0]

        if amount > bal:
            bot.send_message(user_id, "❌ Insufficient balance")
            return

        cur.execute(
            "INSERT INTO withdraw (user_id, amount, address) VALUES (?,?,?)",
            (user_id, amount, address)
        )
        conn.commit()

        wid = cur.lastrowid

        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton("✅ Approve", callback_data=f"approve_{wid}"),
            types.InlineKeyboardButton("❌ Reject", callback_data=f"reject_{wid}")
        )

        bot.send_message(
            ADMIN_ID,
            f"💸 Withdraw Request\n\n"
            f"User: {user_id}\n"
            f"Amount: {amount} DOGS\n"
            f"Address: {address}",
            reply_markup=markup
        )

        bot.send_message(user_id, "⏳ Withdraw request sent. Please wait for admin approval.")

    except:
        bot.send_message(message.chat.id, "❌ Error")


# ---------- ADMIN ACTION ----------
@bot.callback_query_handler(func=lambda c: True)
def admin_action(call):
    if call.from_user.id != ADMIN_ID:
        return

    action, wid = call.data.split("_")
    wid = int(wid)

    cur.execute("SELECT user_id, amount FROM withdraw WHERE id=?", (wid,))
    data = cur.fetchone()
    if not data:
        return

    user_id, amount = data

    if action == "approve":
        cur.execute("UPDATE users SET balance = balance - ? WHERE user_id=?", (amount, user_id))
        bot.send_message(user_id, f"✅ Withdraw Approved\n💸 {amount} DOGS sent")
    else:
        bot.send_message(user_id, "❌ Withdraw Rejected")

    cur.execute("DELETE FROM withdraw WHERE id=?", (wid,))
    conn.commit()
    bot.edit_message_text("✅ Done", call.message.chat.id, call.message.message_id)


# ---------- REFERRAL REWARD ----------
@bot.chat_member_handler()
def referral_reward(update):
    user_id = update.new_chat_member.user.id

    if is_joined(user_id):
        cur.execute("SELECT ref_by FROM users WHERE user_id=?", (user_id,))
        ref = cur.fetchone()
        if ref and ref[0]:
            cur.execute("UPDATE users SET balance = balance + 50 WHERE user_id=?", (ref[0],))
            conn.commit()


print("Bot is running...")
bot.infinity_polling()
