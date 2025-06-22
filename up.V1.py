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
ADMIN_IDS_STR = os.getenv('ADMIN_IDS')
CHANNEL_ID = os.getenv('CHANNEL_ID')

# --- NEW: Process ADMIN_IDS from Heroku ---
if not all([BOT_TOKEN, MONGO_URI, ADMIN_IDS_STR, CHANNEL_ID]):
    # This will log a more helpful message if any variable is missing.
    print("FATAL ERROR: One or more environment variables (BOT_TOKEN, MONGO_URI, ADMIN_IDS, CHANNEL_ID) are not set.")
    exit()

try:
    # Split the comma-separated string and convert each ID to an integer
    ADMIN_IDS = [int(admin_id.strip()) for admin_id in ADMIN_IDS_STR.split(',')]
    if not ADMIN_IDS:
        raise ValueError("ADMIN_IDS environment variable is empty.")
    
    # The first ID in the list is the owner
    OWNER_ID = ADMIN_IDS[0] 
    print(f"Bot starting... Owner ID: {OWNER_ID}, All Admin IDs: {ADMIN_IDS}")

except (ValueError, IndexError) as e:
    print(f"FATAL ERROR: Could not process ADMIN_IDS. Please ensure it is a comma-separated list of numeric IDs. Error: {e}")
    exit()
# --- END NEW ---

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
    # Check if the user's ID is in the list loaded from the environment variable
    return user_id in ADMIN_IDS

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
        "admins": len(ADMIN_IDS), # Get count from the ADMIN_IDS list
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
    # FIX: .count() is deprecated, using count_documents
    files_cursor = db.files.find({"user_id": user_id})
    if db.files.count_documents({"user_id": user_id}) == 0:
        bot.send_message(user_id, "You have no files uploaded.")
        return
    for file in files_cursor:
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
    profile_data = get_user_profile(user_id)
    if not profile_data:
        bot.send_message(user_id, "No profile found.")
        return
    bot.send_message(user_id, f"User ID: {profile_data['user_id']}\nLanguage: {profile_data['language']}\nFiles uploaded: {profile_data['files_uploaded']}\nBanned: {profile_data['banned']}")
