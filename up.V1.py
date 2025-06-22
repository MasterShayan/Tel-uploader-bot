import telebot
from telebot import types
from pymongo import MongoClient
import os
import json
import random
import string
import datetime
import time

# Load environment variables
BOT_TOKEN = os.getenv('BOT_TOKEN')
MONGO_URI = os.getenv('MONGO_URI')
ADMIN_IDS = os.getenv('ADMIN_IDS')
if not ADMIN_IDS:
    raise ValueError("ADMIN_IDS environment variable is not set!")
admin_ids_list = [int(i.strip()) for i in ADMIN_IDS.split(',') if i.strip()]
OWNER_ID = admin_ids_list[0]  # The first admin is the owner
CHANNEL_ID = os.getenv('CHANNEL_ID')

bot = telebot.TeleBot(BOT_TOKEN)
client = MongoClient(MONGO_URI)
db = client['filebot']

user_states = {}  # For tracking user states, including support replies

# Load languages
def load_language(lang_code):
    with open(f'languages/{lang_code}.json', 'r', encoding='utf-8') as f:
        return json.load(f)

def get_user_language(user_id):
    user = db.users.find_one({"user_id": user_id})
    return user.get("language", "en") if user else "en"

def t(user_id, key):
    lang = get_user_language(user_id)
    lang_data = load_language(lang)
    return lang_data.get(key, key)

# Helper functions
def generate_code(length=8):
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))

def is_admin(user_id):
    admin = db.admins.find_one({"user_id": user_id})
    return admin is not None or user_id == OWNER_ID

def is_banned(user_id):
    return db.banned.find_one({"user_id": user_id}) is not None

def force_subscribed(user_id):
    try:
        member = bot.get_chat_member(CHANNEL_ID, user_id)
        return member.status in ['member', 'administrator', 'creator']
    except Exception:
        return False

def get_file_info(file_id):
    file = db.files.find_one({"file_id": file_id})
    return file

def save_file(file_id, file_unique_id, user_id, file_type, file_name, file_size, timer):
    db.files.insert_one({
        "file_id": file_id,
        "file_unique_id": file_unique_id,
        "user_id": user_id,
        "file_type": file_type,
        "file_name": file_name,
        "file_size": file_size,
        "timer": timer,
        "upload_time": datetime.datetime.now()
    })

def get_user_profile(user_id):
    user = db.users.find_one({"user_id": user_id})
    if not user:
        return None
    return {
        "user_id": user_id,
        "language": user.get("language", "en"),
        "files_uploaded": db.files.count_documents({"user_id": user_id}),
        "banned": is_banned(user_id)
    }

def set_user_language(user_id, lang_code):
    db.users.update_one({"user_id": user_id}, {"$set": {"language": lang_code}}, upsert=True)

def add_admin(user_id):
    db.admins.update_one({"user_id": user_id}, {"$set": {"user_id": user_id}}, upsert=True)

def remove_admin(user_id):
    db.admins.delete_one({"user_id": user_id})

def ban_user(user_id):
    db.banned.update_one({"user_id": user_id}, {"$set": {"user_id": user_id}}, upsert=True)

def unban_user(user_id):
    db.banned.delete_one({"user_id": user_id})

def add_code(code, user_id=None, pool=False):
    db.codes.insert_one({
        "code": code,
        "user_id": user_id,
        "used": False,
        "pool": pool
    })

def redeem_code(user_id, code):
    code_doc = db.codes.find_one({"code": code, "used": False})
    if not code_doc:
        return False
    db.codes.update_one({"code": code}, {"$set": {"used": True, "user_id": user_id}})
    return True

def get_stats():
    return {
        "users": db.users.count_documents({}),
        "files": db.files.count_documents({}),
        "admins": db.admins.count_documents({}),
        "banned": db.banned.count_documents({})
    }

# Start command
@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.chat.id
    if is_banned(user_id):
        bot.send_message(user_id, "You are banned from using this bot.")
        return
    db.users.update_one({"user_id": user_id}, {"$set": {"user_id": user_id}}, upsert=True)
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("📤 Upload File", "📁 My Files")
    markup.row("🎁 Redeem Code", "👤 Profile")
    markup.row("🛠 Admin Panel", "Support 🗣")
    markup.row("🌐 Language")
    bot.send_message(user_id, "Welcome to the File Bot!", reply_markup=markup)

# Language selection
@bot.message_handler(func=lambda message: message.text == "🌐 Language")
def language(message):
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("English", callback_data="lang_en"))
    markup.add(types.InlineKeyboardButton("Français", callback_data="lang_fr"))
    markup.add(types.InlineKeyboardButton("Español", callback_data="lang_es"))
    bot.send_message(message.chat.id, "Select your language:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("lang_"))
def set_lang(call):
    lang_code = call.data.split("_")[1]
    set_user_language(call.from_user.id, lang_code)
    bot.answer_callback_query(call.id, "Language updated.")
    bot.send_message(call.from_user.id, "Language set successfully.")

# Upload file
@bot.message_handler(func=lambda message: message.text == "📤 Upload File")
def upload_file(message):
    bot.send_message(message.chat.id, "Send me the file you want to upload:")

@bot.message_handler(content_types=['document', 'photo', 'video', 'audio'])
def handle_file(message):
    user_id = message.chat.id
    if is_banned(user_id):
        bot.send_message(user_id, "You are banned from using this bot.")
        return
    if not force_subscribed(user_id):
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("Join Channel", url=f"https://t.me/{CHANNEL_ID.replace('@','')}"))
        bot.send_message(user_id, "Please join our channel to use the bot.", reply_markup=markup)
        return

    file_id = None
    file_unique_id = None
    file_type = None
    file_name = None
    file_size = None

    if message.document:
        file_id = message.document.file_id
        file_unique_id = message.document.file_unique_id
        file_type = "document"
        file_name = message.document.file_name
        file_size = message.document.file_size
    elif message.photo:
        file_id = message.photo[-1].file_id
        file_unique_id = message.photo[-1].file_unique_id
        file_type = "photo"
        file_name = "Photo"
        file_size = message.photo[-1].file_size
    elif message.video:
        file_id = message.video.file_id
        file_unique_id = message.video.file_unique_id
        file_type = "video"
        file_name = message.video.file_name
        file_size = message.video.file_size
    elif message.audio:
        file_id = message.audio.file_id
        file_unique_id = message.audio.file_unique_id
        file_type = "audio"
        file_name = message.audio.file_name
        file_size = message.audio.file_size

    timer = 0  # Default: no auto-delete
    save_file(file_id, file_unique_id, user_id, file_type, file_name, file_size, timer)
    link = f"https://t.me/{bot.get_me().username}?start={file_unique_id}"
    bot.send_message(user_id, f"File uploaded! Download link:\n{link}")

# My Files
@bot.message_handler(func=lambda message: message.text == "📁 My Files")
def my_files(message):
    user_id = message.chat.id
    files = db.files.find({"user_id": user_id})
    if files.count() == 0:
        bot.send_message(user_id, "You have no files uploaded.")
        return
    for file in files:
        bot.send_message(user_id, f"{file['file_name']} ({file['file_type']})")

# Redeem code
@bot.message_handler(func=lambda message: message.text == "🎁 Redeem Code")
def redeem_code_start(message):
    bot.send_message(message.chat.id, "Send the code you want to redeem:")
    user_states[message.chat.id] = {"redeem": True}

@bot.message_handler(func=lambda message: user_states.get(message.chat.id, {}).get("redeem"))
def handle_redeem_code(message):
    code = message.text.strip().upper()
    user_id = message.chat.id
    if redeem_code(user_id, code):
        bot.send_message(user_id, "Code redeemed successfully!")
    else:
        bot.send_message(user_id, "Invalid or already used code.")
    user_states.pop(user_id, None)

# Profile
@bot.message_handler(func=lambda message: message.text == "👤 Profile")
def profile(message):
    user_id = message.chat.id
    profile = get_user_profile(user_id)
    if not profile:
        bot.send_message(user_id, "No profile found.")
        return
    bot.send_message(user_id, f"User ID: {profile['user_id']}\nLanguage: {profile['language']}\nFiles uploaded: {profile['files_uploaded']}\nBanned: {profile['banned']}")

# Admin Panel
@bot.message_handler(func=lambda message: message.text == "🛠 Admin Panel")
def admin_panel(message):
    user_id = message.chat.id
    if not is_admin(user_id):
        bot.send_message(user_id, "You are not an admin.")
        return
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("Add Admin", "Remove Admin")
    markup.row("Ban User", "Unban User")
    markup.row("Broadcast", "Stats")
    markup.row("Back")
    bot.send_message(user_id, "Admin Panel:", reply_markup=markup)

@bot.message_handler(func=lambda message: message.text == "Add Admin")
def add_admin_start(message):
    user_id = message.chat.id
    if not is_admin(user_id):
        bot.send_message(user_id, "You are not an admin.")
        return
    bot.send_message(user_id, "Send the user ID to add as admin:")
    user_states[user_id] = {"add_admin": True}

@bot.message_handler(func=lambda message: user_states.get(message.chat.id, {}).get("add_admin"))
def handle_add_admin(message):
    try:
        new_admin_id = int(message.text.strip())
        add_admin(new_admin_id)
        bot.send_message(message.chat.id, "Admin added successfully.")
    except Exception:
        bot.send_message(message.chat.id, "Invalid user ID.")
    user_states.pop(message.chat.id, None)

@bot.message_handler(func=lambda message: message.text == "Remove Admin")
def remove_admin_start(message):
    user_id = message.chat.id
    if not is_admin(user_id):
        bot.send_message(user_id, "You are not an admin.")
        return
    bot.send_message(user_id, "Send the user ID to remove as admin:")
    user_states[user_id] = {"remove_admin": True}

@bot.message_handler(func=lambda message: user_states.get(message.chat.id, {}).get("remove_admin"))
def handle_remove_admin(message):
    try:
        admin_id = int(message.text.strip())
        remove_admin(admin_id)
        bot.send_message(message.chat.id, "Admin removed successfully.")
    except Exception:
        bot.send_message(message.chat.id, "Invalid user ID.")
    user_states.pop(message.chat.id, None)

@bot.message_handler(func=lambda message: message.text == "Ban User")
def ban_user_start(message):
    user_id = message.chat.id
    if not is_admin(user_id):
        bot.send_message(user_id, "You are not an admin.")
        return
    bot.send_message(user_id, "Send the user ID to ban:")
    user_states[user_id] = {"ban_user": True}

@bot.message_handler(func=lambda message: user_states.get(message.chat.id, {}).get("ban_user"))
def handle_ban_user(message):
    try:
        ban_id = int(message.text.strip())
        ban_user(ban_id)
        bot.send_message(message.chat.id, "User banned successfully.")
    except Exception:
        bot.send_message(message.chat.id, "Invalid user ID.")
    user_states.pop(message.chat.id, None)

@bot.message_handler(func=lambda message: message.text == "Unban User")
def unban_user_start(message):
    user_id = message.chat.id
    if not is_admin(user_id):
        bot.send_message(user_id, "You are not an admin.")
        return
    bot.send_message(user_id, "Send the user ID to unban:")
    user_states[user_id] = {"unban_user": True}

@bot.message_handler(func=lambda message: user_states.get(message.chat.id, {}).get("unban_user"))
def handle_unban_user(message):
    try:
        unban_id = int(message.text.strip())
        unban_user(unban_id)
        bot.send_message(message.chat.id, "User unbanned successfully.")
    except Exception:
        bot.send_message(message.chat.id, "Invalid user ID.")
    user_states.pop(message.chat.id, None)

@bot.message_handler(func=lambda message: message.text == "Broadcast")
def broadcast_start(message):
    user_id = message.chat.id
    if not is_admin(user_id):
        bot.send_message(user_id, "You are not an admin.")
        return
    bot.send_message(user_id, "Send the broadcast message:")
    user_states[user_id] = {"broadcast": True}

@bot.message_handler(func=lambda message: user_states.get(message.chat.id, {}).get("broadcast"))
def handle_broadcast(message):
    broadcast_text = message.text
    users = db.users.find({})
    for user in users:
        try:
            bot.send_message(user['user_id'], broadcast_text)
        except Exception:
            pass
    bot.send_message(message.chat.id, "Broadcast sent.")
    user_states.pop(message.chat.id, None)

@bot.message_handler(func=lambda message: message.text == "Stats")
def stats(message):
    user_id = message.chat.id
    if not is_admin(user_id):
        bot.send_message(user_id, "You are not an admin.")
        return
    s = get_stats()
    bot.send_message(user_id, f"Users: {s['users']}\nFiles: {s['files']}\nAdmins: {s['admins']}\nBanned: {s['banned']}")

@bot.message_handler(func=lambda message: message.text == "Back")
def back(message):
    start(message)

# --- SUPPORT SYSTEM (FIXED) ---

@bot.message_handler(func=lambda message: message.text == "Support 🗣")
def support_start(message):
    bot.send_message(message.chat.id, "Please send your support message:")
    user_states[message.chat.id] = {"support": True}

@bot.message_handler(func=lambda message: user_states.get(message.chat.id, {}).get("support"))
def handle_support_message(message):
    support_text = message.text
    user_id = message.chat.id

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("Answer User", callback_data=f"answer_user_{user_id}"))
    bot.send_message(OWNER_ID, f"Support message from user {user_id}:\n\n{support_text}", reply_markup=markup)
    bot.send_message(user_id, "Your message has been sent to the owner. They will reply soon.")
    user_states.pop(user_id, None)

@bot.callback_query_handler(func=lambda call: call.data.startswith("answer_user_"))
def answer_user_callback(call):
    user_id = int(call.data.split("_")[-1])
    bot.send_message(call.from_user.id, f"Please type your reply to user {user_id}:")
    user_states[call.from_user.id] = {"reply_to": user_id}
    bot.answer_callback_query(call.id, "Please type your reply.")

@bot.message_handler(func=lambda message: user_states.get(message.from_user.id, {}).get("reply_to"))
def send_reply_to_user(message):
    user_id = user_states[message.from_user.id]["reply_to"]
    try:
        bot.send_message(user_id, f"Support reply from owner:\n\n{message.text}")
        bot.send_message(message.from_user.id, "Your reply has been sent to the user.")
    except Exception as e:
        bot.send_message(message.from_user.id, f"Failed to send reply: {e}")
    user_states.pop(message.from_user.id, None)

# --- END SUPPORT SYSTEM ---

# --- SUPPORT FIX: Owner can answer user ---
@bot.callback_query_handler(func=lambda call: call.data.startswith("answer_user_"))
def answer_user_callback(call):
    user_id = int(call.data.split("_")[-1])
    bot.send_message(call.from_user.id, f"Please type your reply to user {user_id}:")
    user_states[call.from_user.id] = {"reply_to": user_id}
    bot.answer_callback_query(call.id, "Please type your reply.")

@bot.message_handler(func=lambda message: user_states.get(message.from_user.id, {}).get("reply_to"))
def send_reply_to_user(message):
    user_id = user_states[message.from_user.id]["reply_to"]
    try:
        bot.send_message(user_id, f"Support reply from owner:\n\n{message.text}")
        bot.send_message(message.from_user.id, "Your reply has been sent to the user.")
    except Exception as e:
        bot.send_message(message.from_user.id, f"Failed to send reply: {e}")
    user_states.pop(message.from_user.id, None)

# --- END SUPPORT SYSTEM ---

# Main polling loop
bot.infinity_polling()

@bot.message_handler(commands=['start'])
def start_command_handler(message):
    if not force_sub_check(message):
        return
    user_id = message.from_user.id
    lang_data = get_user_lang(user_id)
    if len(message.text.split()) > 1 and message.text.split()[1].startswith('getfile_'):
        try:
            file_info = message.text.split()[1].replace('getfile_', '')
            global_file_id, token = file_info.split('_')
            file_doc = files_collection.find_one({'_id': int(global_file_id)})
            if file_doc and file_doc["token"] == token:
                send_file_by_id(message.chat.id, file_doc["file_type"], file_doc["file_id"])
                send_confirmation_disclaimer(message.chat.id)
            else:
                send_message(message.chat.id, lang_data["download_link_error"])
        except Exception as e:
            print(f"Error in getfile link: {e}")
            send_message(message.chat.id, lang_data["download_link_error"])
    else:
        users_collection.update_one({'_id': user_id}, {'$set': {'username': message.from_user.username, 'first_name': message.from_user.first_name}}, upsert=True)
        send_message(message.chat.id, lang_data["start_message"], reply_markup=main_keyboard(DEFAULT_LANGUAGE))

@bot.message_handler(commands=['panel'])
def panel_command_handler(message):
    if not force_sub_check(message):
        return
    if is_admin(message.from_user.id):
        lang_data = get_user_lang(message.from_user.id)
        send_message(message.chat.id, lang_data["admin_panel_welcome"], reply_markup=admin_keyboard(get_user_lang_code(message.from_user.id)))
    else:
        send_message(message.chat.id, get_user_lang(message.from_user.id)["admin_panel_access_denied"])

@bot.message_handler(commands=['getfile'])
def getfile_command_handler(message):
    if not force_sub_check(message):
        return
    user_id = message.from_user.id
    lang_data = get_user_lang(user_id)
    send_message(message.chat.id, lang_data["get_file_request_message"], reply_markup=back_keyboard(get_user_lang_code(user_id)))
    set_state(user_id, "get_file_by_id")

@bot.message_handler(commands=['createcode'])
def create_code_command_handler(message):
    if not force_sub_check(message):
        return
    user_id = message.from_user.id
    lang_data = get_user_lang(user_id)
    if not is_admin(user_id):
        send_message(message.chat.id, lang_data["admin_panel_access_denied"]); return
    send_message(user_id, lang_data["create_code_prompt_item"], reply_markup=back_keyboard(get_user_lang_code(user_id)))
    set_state(user_id, "create_code_awaiting_item")

@bot.message_handler(commands=['createpool'])
def create_pool_command_handler(message):
    if not force_sub_check(message):
        return
    user_id = message.from_user.id
    lang_data = get_user_lang(user_id)
    if not is_admin(user_id):
        send_message(message.chat.id, lang_data["admin_panel_access_denied"]); return
    send_message(user_id, lang_data["create_pool_prompt_items"], reply_markup=back_keyboard(get_user_lang_code(user_id)))
    set_state(user_id, "create_pool_awaiting_items")

@bot.message_handler(commands=['redeem'])
def redeem_command_handler(message):
    if not force_sub_check(message):
        return
    user_id = message.from_user.id
    lang_data = get_user_lang(user_id)
    send_message(message.chat.id, lang_data["redeem_prompt_code"], reply_markup=back_keyboard(get_user_lang_code(user_id)))
    set_state(user_id, "awaiting_redeem_code")

@bot.message_handler(commands=['addadmin'])
def add_admin_handler(message):
    if not force_sub_check(message):
        return
    if message.from_user.id != OWNER_ID:
        send_message(message.chat.id, "❌ This command can only be used by the Bot Owner."); return
    try:
        target_id = int(message.text.split()[1])
        if is_admin(target_id):
            send_message(message.chat.id, f"User {target_id} is already an admin."); return
        admin_collection.update_one({'_id': 'bot_config'}, {'$addToSet': {'admin_ids': target_id}}, upsert=True)
        send_message(message.chat.id, f"✅ User {target_id} has been promoted to admin.")
    except (IndexError, ValueError):
        send_message(message.chat.id, "Please use the correct format: `/addadmin <user_id>`")

@bot.message_handler(commands=['removeadmin'])
def remove_admin_handler(message):
    if not force_sub_check(message):
        return
    if message.from_user.id != OWNER_ID:
        send_message(message.chat.id, "❌ This command is for the Bot Owner only."); return
    try:
        target_id = int(message.text.split()[1])
        if target_id == OWNER_ID:
            send_message(message.chat.id, "You cannot remove the Bot Owner."); return
        result = admin_collection.update_one({'_id': 'bot_config'}, {'$pull': {'admin_ids': target_id}})
        if result.modified_count > 0:
            send_message(message.chat.id, f"🗑️ User {target_id} has been removed from admins.")
        else:
            send_message(message.chat.id, f"User {target_id} was not found in the admin list.")
    except (IndexError, ValueError):
        send_message(message.chat.id, "Please use the correct format: `/removeadmin <user_id>`")

@bot.message_handler(commands=['listadmins'])
def list_admins_handler(message):
    if not force_sub_check(message):
        return
    if not is_admin(message.from_user.id):
        send_message(message.chat.id, get_user_lang(message.from_user.id)["admin_panel_access_denied"]); return
    admin_list = get_admin_list()
    if not admin_list:
        send_message(message.chat.id, "There are currently no admins configured."); return
    response_text = "👑 **Current Bot Admins** 👑\n\n"
    for admin_id in admin_list:
        if admin_id == OWNER_ID:
            response_text += f"• `{admin_id}` (Owner)\n"
        else:
            response_text += f"• `{admin_id}`\n"
    send_message(message.chat.id, response_text, parse_mode="Markdown")

@bot.message_handler(commands=['set_delete_timer'])
def set_delete_timer_command_handler(message):
    if not force_sub_check(message):
        return
    if message.from_user.id != OWNER_ID:
        send_message(message.chat.id, "❌ This command is for the Bot Owner only."); return
    lang_data = get_user_lang(message.from_user.id)
    config = admin_collection.find_one({'_id': 'bot_config'}) or {}
    current_setting = config.get('auto_delete_seconds', 0)
    send_message(message.chat.id, lang_data["set_delete_timer_prompt"].format(current_setting=current_setting), reply_markup=back_keyboard(get_user_lang_code(message.from_user.id)))
    set_state(message.from_user.id, "set_delete_timer")

@bot.message_handler(commands=['check_delete_timer'])
def check_delete_timer_command_handler(message):
    if not force_sub_check(message):
        return
    if message.from_user.id != OWNER_ID:
        send_message(message.chat.id, "❌ This command is for the Bot Owner only."); return
    lang_data = get_user_lang(message.from_user.id)
    config = admin_collection.find_one({'_id': 'bot_config'}) or {}
    seconds = config.get('auto_delete_seconds', 0)
    send_message(message.chat.id, lang_data["check_delete_timer_status"].format(seconds=seconds))

@bot.message_handler(content_types=['text', 'photo', 'video', 'document', 'audio'], func=lambda message: get_state(message.from_user.id) == "create_code_awaiting_item")
def create_code_item_handler(message):
    if not force_sub_check(message):
        return
    user_id = message.from_user.id
    lang_data = get_user_lang(user_id)
    prize_data = {}
    if message.text and not message.text.startswith('/'):
        prize_data['type'] = 'text'
        prize_data['content'] = {'text': message.text}
    else:
        file_type = message.content_type
        if file_type == 'photo': file_id = message.photo[-1].file_id
        else: file_id = getattr(message, file_type).file_id
        prize_data['type'] = file_type
        prize_data['content'] = {'file_id': file_id}
    send_message(user_id, lang_data["create_code_prompt_limit"], reply_markup=back_keyboard(get_user_lang_code(user_id)))
    set_state(user_id, "create_code_awaiting_limit", data=prize_data)

@bot.message_handler(content_types=['text'], func=lambda message: get_state(message.from_user.id) == "create_code_awaiting_limit")
def create_code_limit_handler(message):
    if not force_sub_check(message):
        return
    user_id = message.from_user.id
    lang_data = get_user_lang(user_id)
    prize_data = get_state_data(user_id)
    if not message.text.isdigit():
        send_message(user_id, "❌ Invalid number. Please enter a number for the redemption limit.")
        return
    def generate_redeem_code(pool=False):
        while True:
            prefix = "POOL-" if pool else ""
            k_range = 2 if pool else 3
            code = prefix + '-'.join(''.join(random.choices(string.ascii_uppercase + string.digits, k=4)) for _ in range(k_range))
            if redeem_codes_collection.find_one({'_id': code}) is None: return code
    is_pool = 'codes' in prize_data
    new_code = generate_redeem_code(pool=is_pool)
    db_document = {
        '_id': new_code, 'item_type': 'code_pool' if is_pool else prize_data['type'],
        'item_content': prize_data, 'redemption_limit': int(message.text),
        'redemption_count': 0, 'redeemed_by': [], 'creator_id': user_id, 'created_at': datetime.now(UTC)
    }
    redeem_codes_collection.insert_one(db_document)
    success_message = lang_data["create_pool_success"] if is_pool else lang_data["create_code_success"]
    send_message(user_id, success_message.format(code=db_document['_id']), reply_markup=main_keyboard(get_user_lang_code(user_id)), parse_mode="Markdown")
    delete_state(user_id)

@bot.message_handler(content_types=['text'], func=lambda message: get_state(message.from_user.id) == "create_pool_awaiting_items")
def create_pool_items_handler(message):
    if not force_sub_check(message):
        return
    user_id = message.from_user.id
    lang_data = get_user_lang(user_id)
    if not message.text or message.text.startswith('/'):
        send_message(user_id, "Invalid input. Please provide a list of codes, each on a new line.")
        return
    prize_codes = [line.strip() for line in message.text.splitlines() if line.strip()]
    if not prize_codes:
        send_message(user_id, "Invalid input. The list of codes cannot be empty.")
        return
    item_count = len(prize_codes)
    prize_data = {'codes': prize_codes}
    send_message(user_id, lang_data["create_pool_prompt_limit"].format(item_count=item_count), reply_markup=back_keyboard(get_user_lang_code(user_id)))
    set_state(user_id, "create_code_awaiting_limit", data=prize_data)

@bot.message_handler(content_types=['text'], func=lambda message: get_state(message.from_user.id) == "awaiting_redeem_code")
def redeem_code_handler(message):
    if not force_sub_check(message):
        return
    user_id = message.from_user.id
    lang_data = get_user_lang(user_id)
    user_code = message.text.strip().upper()
    code_doc = redeem_codes_collection.find_one({'_id': user_code})
    if not code_doc:
        send_message(user_id, lang_data["redeem_error_not_found"], reply_markup=main_keyboard(get_user_lang_code(user_id))); delete_state(user_id); return
    if user_id in code_doc.get('redeemed_by', []):
        send_message(user_id, lang_data["redeem_error_already_claimed"], reply_markup=main_keyboard(get_user_lang_code(user_id))); delete_state(user_id); return
    if code_doc['redemption_limit'] != 0 and code_doc['redemption_count'] >= code_doc['redemption_limit']:
        send_message(user_id, lang_data["redeem_error_limit_reached"], reply_markup=main_keyboard(get_user_lang_code(user_id))); delete_state(user_id); return

    item_type = code_doc['item_type']
    prize_message_sent = False

    if item_type == 'code_pool':
        if not code_doc.get('item_content', {}).get('codes'):
            send_message(user_id, lang_data["redeem_error_pool_empty"], reply_markup=main_keyboard(get_user_lang_code(user_id))); delete_state(user_id); return
        updated_doc = redeem_codes_collection.find_one_and_update(
            {'_id': user_code}, {'$pop': {'item_content.codes': -1}}
        )
        prize_text = updated_doc['item_content']['codes'][0]
        sent_message = send_message(user_id, prize_text)
        if sent_message:
            prize_message_sent = True
            config = admin_collection.find_one({'_id': 'bot_config'}) or {}
            delay = config.get('auto_delete_seconds', 0)
            if delay > 0: schedule_message_deletion(user_id, sent_message.message_id, delay)
    else:
        item_content = code_doc['item_content']
        if item_type == 'text':
            sent_message = send_message(user_id, item_content['content']['text'])
            if sent_message:
                prize_message_sent = True
                config = admin_collection.find_one({'_id': 'bot_config'}) or {}
                delay = config.get('auto_delete_seconds', 0)
                if delay > 0: schedule_message_deletion(user_id, sent_message.message_id, delay)
        else:
            sent_message = send_file_by_id(user_id, item_type, item_content['content']['file_id'])
            if sent_message: prize_message_sent = True

    if prize_message_sent:
        redeem_codes_collection.update_one({'_id': user_code}, {'$inc': {'redemption_count': 1}, '$addToSet': {'redeemed_by': user_id}})
        config = admin_collection.find_one({'_id': 'bot_config'}) or {}
        delay = config.get('auto_delete_seconds', 0)
        if delay > 0:
            time_str = f"{delay} seconds"
            if delay >= 3600: hours = delay // 3600; time_str = f"{hours} hour" + ("s" if hours > 1 else "")
            elif delay >= 60: minutes = delay // 60; time_str = f"{minutes} minute" + ("s" if minutes > 1 else "")
            send_message(user_id, lang_data["redeem_success_timed"].format(time=time_str), reply_markup=main_keyboard(get_user_lang_code(user_id)))
        else:
            send_message(user_id, lang_data["redeem_success"], reply_markup=main_keyboard(get_user_lang_code(user_id)))
        try:
            creator_id, user_info = code_doc['creator_id'], users_collection.find_one({'_id': user_id})
            remaining = "Unlimited" if code_doc['redemption_limit'] == 0 else code_doc['redemption_limit'] - (code_doc['redemption_count'] + 1)
            username = user_info.get('username', 'N/A') if user_info else 'N/A'
            notification_text = lang_data["admin_redeem_notification"].format(username=username, user_id=user_id, code=user_code, remaining=remaining)
            send_message(creator_id, notification_text)
        except Exception as e: print(f"Failed to send admin notification: {e}")

    delete_state(user_id)

@bot.message_handler(content_types=['text'], func=lambda message: get_state(message.from_user.id) == "set_delete_timer")
def set_delete_timer_limit_handler(message):
    if not force_sub_check(message):
        return
    user_id = message.from_user.id
    lang_data = get_user_lang(user_id)
    if not message.text.isdigit():
        send_message(user_id, "Invalid input. Please send a number."); return
    seconds = int(message.text)
    admin_collection.update_one({'_id': 'bot_config'},{'$set': {'auto_delete_seconds': seconds}},upsert=True)
    send_message(user_id, lang_data["set_delete_timer_success"].format(seconds=seconds), reply_markup=main_keyboard(get_user_lang_code(user_id)))
    delete_state(user_id)

@bot.message_handler(func=lambda message: message.text == get_user_lang(message.from_user.id)["upload_button"])
def upload_button_handler(message):
    if not force_sub_check(message):
        return
    user_id = message.from_user.id
    lang_data = get_user_lang(user_id)
    send_message(message.chat.id, lang_data["upload_request_message"], reply_markup=back_keyboard(get_user_lang_code(user_id)))
    set_state(user_id, "upload")

@bot.message_handler(content_types=['photo', 'video', 'document', 'audio'], func=lambda message: get_state(message.from_user.id) == "upload")
def upload_media_handler(message):
    if not force_sub_check(message):
        return
    user_id = message.from_user.id
    lang_data = get_user_lang(user_id)
    media_type, telegram_file_id = None, None
    if message.photo: media_type, telegram_file_id = "photo", message.photo[-1].file_id
    elif message.video: media_type, telegram_file_id = "video", message.video.file_id
    elif message.document: media_type, telegram_file_id = "document", message.document.file_id
    elif message.audio: media_type, telegram_file_id = "music", message.audio.file_id
    else: return
    user_doc = users_collection.find_one({'_id': user_id}, {'caption': 1})
    caption = user_doc.get('caption', lang_data["default_caption"]) if user_doc else lang_data["default_caption"]
    sent_message = bot.copy_message(STORAGE_GROUP_ID, message.chat.id, message.message_id, caption=caption)
    global_file_id = get_next_sequence_value('global_file_id')
    token = ''.join(random.choices(string.ascii_letters + string.digits, k=16))
    file_doc = {
        '_id': global_file_id, 'uploader_id': user_id, 'file_id': telegram_file_id,
        'file_type': media_type, 'message_id_in_storage': sent_message.message_id,
        'token': token, 'created_at': datetime.now(UTC)
    }
    files_collection.insert_one(file_doc)
    download_link = f"https://t.me/{bot.get_me().username}?start=getfile_{global_file_id}_{token}"
    send_message(message.chat.id, lang_data["upload_success_message"].format(file_id=global_file_id, download_link=download_link), reply_markup=main_keyboard(get_user_lang_code(user_id)))
    delete_state(user_id)

@bot.message_handler(func=lambda message: message.text == get_user_lang(message.from_user.id)["caption_button"])
def caption_button_handler(message):
    if not force_sub_check(message):
        return
    user_id = message.from_user.id
    lang_data = get_user_lang(user_id)
    user_doc = users_collection.find_one({'_id': user_id}, {'caption': 1})
    current_caption = user_doc.get('caption', lang_data["default_caption"]) if user_doc else lang_data["default_caption"]
    send_message(message.chat.id, lang_data["caption_request_message"].format(current_caption=current_caption), reply_markup=back_keyboard(get_user_lang_code(user_id)))
    set_state(user_id, "set-caption")

@bot.message_handler(content_types=['text'], func=lambda message: get_state(message.from_user.id) == "set-caption")
def set_caption_handler(message):
    if not force_sub_check(message):
        return
    user_id = message.from_user.id
    users_collection.update_one({'_id': user_id}, {'$set': {'caption': message.text}}, upsert=True)
    send_message(message.chat.id, get_user_lang(user_id)["caption_saved_message"], reply_markup=main_keyboard(get_user_lang_code(user_id)))
    delete_state(user_id)

@bot.message_handler(func=lambda message: message.text == get_user_lang(message.from_user.id)["delete_button"])
def delete_button_handler(message):
    if not force_sub_check(message):
        return
    user_id = message.from_user.id
    lang_data = get_user_lang(user_id)
    send_message(message.chat.id, lang_data["delete_file_request_message"], reply_markup=back_keyboard(get_user_lang_code(user_id)))
    set_state(user_id, "delete-file")

@bot.message_handler(content_types=['text'], func=lambda message: get_state(message.from_user.id) == "delete-file")
def delete_file_handler(message):
    if not force_sub_check(message):
        return
    user_id = message.from_user.id
    lang_data = get_user_lang(user_id)
    file_id_to_delete = message.text
    if not file_id_to_delete.isdigit():
        send_message(message.chat.id, lang_data["delete_file_invalid_id"], reply_markup=back_keyboard(get_user_lang_code(user_id))); return
    file_doc = files_collection.find_one({'_id': int(file_id_to_delete)})
    if file_doc and (file_doc['uploader_id'] == user_id or is_admin(user_id)):
        files_collection.delete_one({'_id': int(file_id_to_delete)})
        try: bot.delete_message(STORAGE_GROUP_ID, file_doc['message_id_in_storage'])
        except Exception as e: print(f"Could not delete message from storage group: {e}")
        send_message(message.chat.id, lang_data["delete_file_success"].format(file_id=file_id_to_delete), reply_markup=main_keyboard(get_user_lang_code(user_id)))
    else:
        send_message(message.chat.id, lang_data["file_not_found"], reply_markup=main_keyboard(get_user_lang_code(user_id)))
    delete_state(user_id)

@bot.message_handler(func=lambda message: message.text == get_user_lang(message.from_user.id)["support_button"])
def support_button_handler(message):
    if not force_sub_check(message):
        return
    user_id = message.from_user.id
    lang_data = get_user_lang(user_id)
    send_message(message.chat.id, lang_data["support_message_request"], reply_markup=back_keyboard(get_user_lang_code(user_id)))
    set_state(user_id, "support")

@bot.message_handler(content_types=['text'], func=lambda message: get_state(message.from_user.id) == "support")
def support_handler(message):
    if not force_sub_check(message):
        return
    user_id = message.from_user.id
    lang_data = get_user_lang(user_id)
    support_message = lang_data["support_message_prefix"].format(first_name=message.from_user.first_name, user_id=user_id) + message.text
    admin_markup = types.InlineKeyboardMarkup()
    admin_markup.add(types.InlineKeyboardButton(text=lang_data["support_answer_button"], callback_data=f"answer_support_{user_id}"))
    send_message(OWNER_ID, support_message, reply_markup=admin_markup)
    send_message(message.chat.id, lang_data["support_message_sent"], reply_markup=main_keyboard(get_user_lang_code(user_id)))
    delete_state(user_id)

@bot.message_handler(func=lambda message: message.text == get_user_lang(message.from_user.id)["profile_button"])
def profile_button_handler(message):
    if not force_sub_check(message):
        return
    user_id = message.from_user.id
    lang_data = get_user_lang(user_id)
    file_count = files_collection.count_documents({'uploader_id': user_id})
    user_doc = users_collection.find_one({'_id': user_id})
    first_name = user_doc.get('first_name', message.from_user.first_name) if user_doc else message.from_user.first_name
    profile_text = lang_data["profile_message"].format(first_name=first_name, user_id=user_id, file_count=file_count)
    send_message(message.chat.id, profile_text, reply_markup=main_keyboard(get_user_lang_code(user_id)))

@bot.message_handler(func=lambda message: message.text == get_user_lang(message.from_user.id)["get_file_button"])
def get_file_button_handler(message):
    if not force_sub_check(message):
        return
    user_id = message.from_user.id
    lang_data = get_user_lang(user_id)
    send_message(message.chat.id, lang_data["get_file_request_message"], reply_markup=back_keyboard(get_user_lang_code(user_id)))
    set_state(user_id, "get_file_by_id")

@bot.message_handler(content_types=['text'], func=lambda message: get_state(message.from_user.id) == "get_file_by_id")
def get_file_by_id_handler(message):
    if not force_sub_check(message):
        return
    user_id = message.from_user.id
    lang_data = get_user_lang(user_id)
    file_id_to_get = message.text
    if not file_id_to_get.isdigit():
        send_message(message.chat.id, lang_data["delete_file_invalid_id"]); delete_state(user_id); return
    file_doc = files_collection.find_one({'_id': int(file_id_to_get)})
    if file_doc:
        send_file_by_id(user_id, file_doc["file_type"], file_doc["file_id"])
        send_confirmation_disclaimer(user_id)
    else:
        send_message(user_id, lang_data["file_not_found"])
    delete_state(user_id)
    send_message(message.chat.id, lang_data["main_menu_back"], reply_markup=main_keyboard(get_user_lang_code(user_id)))

@bot.message_handler(func=lambda message: message.text == get_user_lang(message.from_user.id)["back_button"])
def back_button_handler(message):
    if not force_sub_check(message):
        return
    user_id = message.from_user.id
    delete_state(user_id)
    send_message(message.chat.id, get_user_lang(user_id)["main_menu_back"], reply_markup=main_keyboard(get_user_lang_code(user_id)))

@bot.message_handler(func=lambda message: message.text == get_user_lang(message.from_user.id)["redeem_button"])
def redeem_button_handler(message):
    if not force_sub_check(message):
        return
    redeem_command_handler(message)

@bot.message_handler(func=lambda message: message.text == get_user_lang(message.from_user.id)["admin_stats_button"] and is_admin(message.from_user.id))
def admin_stats_handler(message):
    if not force_sub_check(message):
        return
    user_id = message.from_user.id
    lang_data = get_user_lang(user_id)
    user_count = users_collection.count_documents({})
    config = admin_collection.find_one({'_id': 'bot_config'}) or {}
    bot_status = config.get("bot_status", lang_data["bot_status_on"])
    stats_text = lang_data["admin_stats_message"].format(user_count=user_count, bot_status=bot_status)
    send_message(message.chat.id, stats_text, reply_markup=admin_keyboard(get_user_lang_code(user_id)))

@bot.message_handler(func=lambda message: message.text == get_user_lang(message.from_user.id)["admin_bot_status_button"] and is_admin(message.from_user.id))
def admin_bot_status_handler(message):
    if not force_sub_check(message):
        return
    user_id = message.from_user.id
    lang_data = get_user_lang(user_id)
    config = admin_collection.find_one({'_id': 'bot_config'}) or {}
    current_status = config.get("bot_status", lang_data["bot_status_on"])
    new_status = lang_data["bot_status_on"] if current_status == lang_data["bot_status_off"] else lang_data["bot_status_off"]
    admin_collection.update_one({'_id': 'bot_config'}, {'$set': {'bot_status': new_status}}, upsert=True)
    send_message(message.chat.id, lang_data["admin_bot_status_changed"].format(bot_status=new_status), reply_markup=admin_keyboard(get_user_lang_code(user_id)))

@bot.message_handler(func=lambda message: message.text == get_user_lang(message.from_user.id)["admin_ban_button"] and is_admin(message.from_user.id))
def admin_ban_handler(message):
    if not force_sub_check(message):
        return
    user_id = message.from_user.id
    lang_data = get_user_lang(user_id)
    send_message(message.chat.id, lang_data["admin_ban_request"], reply_markup=back_keyboard(get_user_lang_code(user_id)))
    set_state(user_id, "ban_user")

@bot.message_handler(content_types=['text'], func=lambda message: get_state(message.from_user.id) == "ban_user" and is_admin(message.from_user.id))
def ban_user_message_handler(message):
    if not force_sub_check(message):
        return
    user_id = message.from_user.id
    lang_data = get_user_lang(user_id)
    try:
        user_id_to_ban = int(message.text)
        if user_id_to_ban == OWNER_ID or is_admin(user_id_to_ban):
            send_message(message.chat.id, "You cannot ban an admin or the Bot Owner.")
            delete_state(user_id); return
        users_collection.update_one({'_id': user_id_to_ban}, {'$set': {'banned': True}}, upsert=True)
        send_message(message.chat.id, lang_data["admin_ban_success"].format(user_id=user_id_to_ban), reply_markup=admin_keyboard(get_user_lang_code(user_id)))
    except ValueError:
        send_message(message.chat.id, lang_data["admin_invalid_user_id"], reply_markup=back_keyboard(get_user_lang_code(user_id)))
    delete_state(user_id)

@bot.message_handler(func=lambda message: message.text == get_user_lang(message.from_user.id)["admin_unban_button"] and is_admin(message.from_user.id))
def admin_unban_handler(message):
    if not force_sub_check(message):
        return
    user_id = message.from_user.id
    lang_data = get_user_lang(user_id)
    send_message(message.chat.id, lang_data["admin_unban_request"], reply_markup=back_keyboard(get_user_lang_code(user_id)))
    set_state(user_id, "unban_user")

@bot.message_handler(content_types=['text'], func=lambda message: get_state(message.from_user.id) == "unban_user" and is_admin(message.from_user.id))
def unban_user_message_handler(message):
    if not force_sub_check(message):
        return
    user_id = message.from_user.id
    lang_data = get_user_lang(user_id)
    try:
        user_id_to_unban = int(message.text)
        result = users_collection.update_one({'_id': user_id_to_unban}, {'$unset': {'banned': ""}})
        if result.modified_count > 0:
            send_message(message.chat.id, lang_data["admin_unban_success"].format(user_id=user_id_to_unban), reply_markup=admin_keyboard(get_user_lang_code(user_id)))
        else:
            send_message(message.chat.id, lang_data["admin_user_not_banned"], reply_markup=admin_keyboard(get_user_lang_code(user_id)))
    except ValueError:
        send_message(message.chat.id, lang_data["admin_invalid_user_id"], reply_markup=back_keyboard(get_user_lang_code(user_id)))
    delete_state(user_id)

@bot.message_handler(func=lambda message: message.text == get_user_lang(message.from_user.id)["admin_broadcast_button"] and is_admin(message.from_user.id))
def admin_broadcast_handler(message):
    if not force_sub_check(message):
        return
    user_id = message.from_user.id
    lang_data = get_user_lang(user_id)
    send_message(message.chat.id, lang_data["admin_broadcast_request"], reply_markup=back_keyboard(get_user_lang_code(user_id)))
    set_state(user_id, "broadcast_message")

@bot.message_handler(content_types=['text'], func=lambda message: get_state(message.from_user.id) == "broadcast_message" and is_admin(message.from_user.id))
def broadcast_message_handler(message):
    if not force_sub_check(message):
        return
    user_id = message.from_user.id
    lang_data = get_user_lang(user_id)
    cursor = users_collection.find({'banned': {'$ne': True}}, {'_id': 1})
    success_count, fail_count = 0, 0
    for doc in cursor:
        try: send_message(doc['_id'], message.text); success_count += 1
        except: fail_count += 1
    send_message(message.chat.id, lang_data["admin_broadcast_report"].format(success_count=success_count, fail_count=fail_count), reply_markup=admin_keyboard(get_user_lang_code(user_id)))
    delete_state(user_id)

@bot.message_handler(func=lambda message: message.text == get_user_lang(message.from_user.id)["admin_forward_broadcast_button"] and is_admin(message.from_user.id))
def admin_forward_broadcast_handler(message):
    if not force_sub_check(message):
        return
    user_id = message.from_user.id
    lang_data = get_user_lang(user_id)
    send_message(message.chat.id, lang_data["admin_forward_broadcast_request"], reply_markup=back_keyboard(get_user_lang_code(user_id)))
    set_state(user_id, "forward_broadcast_message")

@bot.message_handler(content_types=['any'], func=lambda message: get_state(message.from_user.id) == "forward_broadcast_message" and is_admin(message.from_user.id))
def forward_broadcast_message_handler(message):
    if not force_sub_check(message):
        return
    user_id = message.from_user.id
    lang_data = get_user_lang(user_id)
    cursor = users_collection.find({'banned': {'$ne': True}}, {'_id': 1})
    success_count, fail_count = 0, 0
    for doc in cursor:
        try: bot.forward_message(doc['_id'], message.chat.id, message.message_id); success_count += 1
        except: fail_count += 1
    send_message(message.chat.id, lang_data["admin_forward_broadcast_report"].format(success_count=success_count, fail_count=fail_count), reply_markup=admin_keyboard(get_user_lang_code(user_id)))
    delete_state(user_id)

if __name__ == "__main__":
    counters_collection.update_one({'_id': 'global_file_id'}, {'$setOnInsert': {'sequence_value': 0}}, upsert=True)
    get_admin_list()
    print("Bot starting with all features enabled...")
    bot.infinity_polling()
