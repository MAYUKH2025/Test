from telegram import Update
from telegram.ext import (ApplicationBuilder, CommandHandler, ContextTypes,
                          MessageHandler, filters)
import logging
import json
import os
from dotenv import load_dotenv
from flask import Flask  # For uptime
from threading import Thread  # For keeping alive

# === UPTIME KEEP ALIVE SETUP ===
app = Flask('')


@app.route('/')
def home():
    return "✅ YuxtorBot is alive!"


def run():
    app.run(host='0.0.0.0', port=8080)


def keep_alive():
    t = Thread(target=run)
    t.start()


# === LOAD ENV VARIABLES ===
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))

# === FILES FOR PERSISTENCE ===
MESSAGE_MAP_FILE = "message_map.json"
USER_IDS_FILE = "user_ids.json"
BLOCKED_USERS_FILE = "blocked_users.json"

# === LOGGER ===
logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s',
                    level=logging.INFO)


# === LOAD/SAVE FUNCTIONS ===
def load_json_set(filename):
    if os.path.exists(filename):
        with open(filename, "r") as f:
            return set(json.load(f))
    return set()


def save_json_set(data_set, filename):
    with open(filename, "w") as f:
        json.dump(list(data_set), f)


def load_message_map():
    if os.path.exists(MESSAGE_MAP_FILE):
        with open(MESSAGE_MAP_FILE, "r") as f:
            return {int(k): v for k, v in json.load(f).items()}
    return {}


def save_message_map(data_dict):
    with open(MESSAGE_MAP_FILE, "w") as f:
        json.dump(data_dict, f)


# === GLOBAL STATE ===
message_map = load_message_map()
user_ids = load_json_set(USER_IDS_FILE)
blocked_users = load_json_set(BLOCKED_USERS_FILE)


# === COMMAND HANDLERS ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎬 *Welcome to YuxtorBot Official!*\n\n"
        "If you're looking for any movie, feel free to request it here.\n"
        "We will try our best to provide it for you. 🍿\n\n"
        "This Bot is Created By *YuxtorBot Official*.",
        parse_mode="Markdown")


async def user_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    msg = update.message

    if user.id in blocked_users:
        return

    user_ids.add(user.id)
    save_json_set(user_ids, USER_IDS_FILE)

    username = f"@{user.username}" if user.username else "No username"

    try:
        sent = await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=("📩 *New Message Received!*\n"
                  "```\n"
                  f"From    : {user.first_name}\n"
                  f"Username: {username}\n"
                  f"UserID  : {user.id}\n"
                  "```\n"
                  f"{msg.text or '[Non-text message]'}"),
            parse_mode="Markdown")
        message_map[sent.message_id] = user.id
        save_message_map(message_map)
    except Exception as e:
        logging.error(f"Could not forward user message to admin: {e}")


async def admin_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.reply_to_message:
        await update.message.reply_text(
            "⚠️ Please reply to a user's message to respond.")
        return

    original_msg_id = update.message.reply_to_message.message_id

    if original_msg_id in message_map:
        user_id = message_map[original_msg_id]
        if user_id in blocked_users:
            await update.message.reply_text(
                "🚫 This user is currently blocked. Cannot send message.")
            return
        try:
            await context.bot.send_message(chat_id=user_id,
                                           text=update.message.text)
        except Exception as e:
            await update.message.reply_text(f"❌ Failed to send message: {e}")
    else:
        await update.message.reply_text(
            "❌ Could not find user from this reply.")


async def sendall_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    await update.message.reply_text(
        "📝 Please enter the message to send to all users...")
    context.user_data["awaiting_broadcast"] = True


async def handle_admin_input(update: Update,
                             context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    if context.user_data.get("awaiting_broadcast"):
        context.user_data["awaiting_broadcast"] = False
        text = update.message.text
        count = 0

        for uid in user_ids:
            if uid in blocked_users:
                continue
            try:
                await context.bot.send_message(chat_id=uid, text=text)
                count += 1
            except Exception as e:
                logging.warning(f"Could not send to {uid}: {e}")

        await update.message.reply_text(f"✅ Message sent to {count} users.")
    else:
        await update.message.reply_text("⚠️ Please reply or use /sendall.")


async def block_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    if context.args:
        try:
            uid = int(context.args[0])
            blocked_users.add(uid)
            save_json_set(blocked_users, BLOCKED_USERS_FILE)
            await update.message.reply_text(f"🚫 User {uid} blocked.")
        except:
            await update.message.reply_text("❗ Invalid user ID.")
    else:
        await update.message.reply_text("ℹ️ Usage: /block <user_id>")


async def unblock_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    if context.args:
        try:
            uid = int(context.args[0])
            if uid in blocked_users:
                blocked_users.remove(uid)
                save_json_set(blocked_users, BLOCKED_USERS_FILE)
                await update.message.reply_text(f"✅ User {uid} unblocked.")
            else:
                await update.message.reply_text("ℹ️ User not blocked.")
        except:
            await update.message.reply_text("❗ Invalid user ID.")
    else:
        await update.message.reply_text("ℹ️ Usage: /unblock <user_id>")


async def list_blocked(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    if not blocked_users:
        await update.message.reply_text("✅ No blocked users.")
    else:
        await update.message.reply_text("🚫 Blocked Users:\n" + "\n".join(
            str(u) for u in blocked_users))


# === MAIN ===
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # Handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("sendall", sendall_command))
    app.add_handler(CommandHandler("block", block_user))
    app.add_handler(CommandHandler("unblock", unblock_user))
    app.add_handler(CommandHandler("blocked", list_blocked))

    app.add_handler(
        MessageHandler(
            filters.TEXT & filters.User(user_id=ADMIN_ID) & filters.REPLY,
            admin_reply))
    app.add_handler(
        MessageHandler(
            filters.TEXT & filters.User(user_id=ADMIN_ID) & ~filters.REPLY,
            handle_admin_input))
    app.add_handler(
        MessageHandler(filters.TEXT & (~filters.User(user_id=ADMIN_ID)),
                       user_message))

    print("✅ Bot is running...")
    app.run_polling()


if __name__ == "__main__":
    keep_alive()  # 👈 Important for UptimeRobot
    main()
