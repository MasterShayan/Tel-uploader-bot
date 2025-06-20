import telebot
import os
import pymongo
import json
from telebot import types
import hashlib
import random
import string
from datetime import datetime

# --- Config (Reading from Heroku Environment) ---
BOT_TOKEN = os.environ.get('BOT_TOKEN')
# The first ID in this list is the OWNER. Others are initial admins.
ADMIN_IDS_STR = os.environ.get('ADMIN_IDS', '0')
try:
    INITIAL_ADMIN_IDS = [int(i.strip()) for i in ADMIN_IDS_STR.split(',') if i.strip()]
    OWNER_ID = INITIAL_ADMIN_IDS[0] if INITIAL_ADMIN_IDS else 0
except (ValueError, IndexError):
    print("ERROR: Invalid ADMIN_IDS format in environment variables.")
    INITIAL_ADMIN_IDS = []
    OWNER_ID = 0

STORAGE_GROUP_ID = int(os.environ.get('STORAGE_GROUP_ID'))
MONGODB_URI = os.environ.get('MONGODB_URI')
DEFAULT_LANGUAGE = "en"

# --- MongoDB Setup ---
client = pymongo.MongoClient(MONGODB_URI)
db = client['uploader_bot_db']
users_collection = db['users']
admin_collection = db['admin_config']

bot = telebot.TeleBot(BOT_TOKEN)

# --- NEW: Admin Management Helpers ---
def get_admin_list():
    """Gets the list of admin IDs from the database, initializing it if necessary."""
    config = admin_collection.find_one({'_id': 'bot_config'})
    if config and 'admin_ids' in config:
        return config['admin_ids']
    else:
        # If no config exists, create it with the initial list from environment variables
        if INITIAL_ADMIN_IDS:
            admin_collection.update_one(
                {'_id': 'bot_config'},
                {'$set': {'admin_ids': INITIAL_ADMIN_IDS}},
                upsert=True
            )
            return INITIAL_ADMIN_IDS
        return []

def is_admin(user_id):
    """Checks if a user ID is in the admin list."""
    return user_id in get_admin_list()

# --- Language Support ---
LANGUAGES = {"en": "English"}

def load_language(lang_code):
    try:
        with open(os.path.join("languages", f"{lang_code}.json"), "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        with open(os.path.join("languages", f"{DEFAULT_LANGUAGE}.json"), "r", encoding="utf-8") as f:
            return json.load(f)

def get_user_lang_code(user_id):
    user_doc = users_collection.find_one({'_id': user_id}, {'language': 1})
    return user_doc.get('language', DEFAULT_LANGUAGE) if user_doc else DEFAULT_LANGUAGE

def get_user_lang(user_id):
    lang_code = get_user_lang_code(user_id)
    return load_language(lang_code)

# --- Bot Functions ---
def send_message(chat_id, text, reply_markup=None, parse_mode="HTML"):
    try:
        bot.send_message(chat_id, text, parse_mode=parse_mode, reply_markup=reply_markup, disable_web_page_preview=True)
    except Exception as e:
        print(f"Error sending message to {chat_id}: {e}")

def forward_message(chat_id, from_chat_id, message_id):
    try:
        bot.forward_message(chat_id, from_chat_id, message_id)
    except Exception as e:
        print(f"Error forwarding message to {chat_id}: {e}")

# --- State Management ---
user_states = {}
def set_state(user_id, state): user_states[user_id] = state
def get_state(user_id): return user_states.get(user_id)
def delete_state(user_id): user_states.pop(user_id, None)

# --- Keyboards ---
def main_keyboard(lang_code):
    lang_data = load_language(lang_code)
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton(lang_data["upload_button"]))
    markup.add(types.KeyboardButton(lang_data["delete_button"]), types.KeyboardButton(lang_data["get_file_button"]))
    markup.add(types.KeyboardButton(lang_data["caption_button"]), types.KeyboardButton(lang_data["support_button"]), types.KeyboardButton(lang_data["profile_button"]))
    return markup

def admin_keyboard(lang_code):
    lang_data = load_language(lang_code)
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton(lang_data["admin_stats_button"]), types.KeyboardButton(lang_data["admin_bot_status_button"]))
    markup.add(types.KeyboardButton(lang_data["admin_ban_button"]), types.KeyboardButton(lang_data["admin_unban_button"]))
    markup.add(types.KeyboardButton(lang_data["admin_broadcast_button"]), types.KeyboardButton(lang_data["admin_forward_broadcast_button"]))
    return markup

def back_keyboard(lang_code):
    lang_data = load_language(lang_code)
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton(lang_data["back_button"]))
    return markup

# --- Command Handlers ---
@bot.message_handler(commands=['start'])
def start_command_handler(message):
    user_id = message.from_user.id
    lang_data = get_user_lang(user_id)
    if len(message.text.split()) > 1 and message.text.split()[1].startswith('getfile_'):
        try:
            # ... (getfile link logic remains the same)
            pass # Abridged for brevity, logic is unchanged
        except Exception as e:
            print(f"Error in getfile: {e}")
            send_message(message.chat.id, lang_data["download_link_error"])
    else:
        users_collection.update_one({'_id': user_id}, {'$set': {'username': message.from_user.username, 'first_name': message.from_user.first_name}}, upsert=True)
        send_message(message.chat.id, lang_data["start_message"], reply_markup=main_keyboard(DEFAULT_LANGUAGE))

@bot.message_handler(commands=['panel'])
def panel_command_handler(message):
    if is_admin(message.from_user.id): # MODIFIED: Use new admin check
        lang_data = get_user_lang(message.from_user.id)
        send_message(message.chat.id, lang_data["admin_panel_welcome"], reply_markup=admin_keyboard(get_user_lang_code(message.from_user.id)))
    else:
        send_message(message.chat.id, get_user_lang(message.from_user.id)["admin_panel_access_denied"])

@bot.message_handler(commands=['getfile'])
def getfile_command_handler(message):
    # ... (logic remains the same)
    user_id = message.from_user.id
    lang_data = get_user_lang(user_id)
    send_message(message.chat.id, lang_data["get_file_request_message"], reply_markup=back_keyboard(get_user_lang_code(user_id)))
    set_state(user_id, "get_file_by_id")
    
# --- NEW: DYNAMIC ADMIN MANAGEMENT COMMANDS ---

@bot.message_handler(commands=['addadmin'])
def add_admin_handler(message):
    # Only the Bot Owner can use this command
    if message.from_user.id != OWNER_ID:
        send_message(message.chat.id, "❌ This command can only be used by the Bot Owner.")
        return

    try:
        # Expects command like: /addadmin 12345678
        target_id = int(message.text.split()[1])
        if is_admin(target_id):
            send_message(message.chat.id, f"User {target_id} is already an admin.")
            return
            
        # Add the new ID to the list in the database using $addToSet to avoid duplicates
        admin_collection.update_one(
            {'_id': 'bot_config'},
            {'$addToSet': {'admin_ids': target_id}},
            upsert=True
        )
        send_message(message.chat.id, f"✅ User {target_id} has been promoted to admin.")
    except (IndexError, ValueError):
        send_message(message.chat.id, "Please use the correct format: `/addadmin <user_id>`")

@bot.message_handler(commands=['removeadmin'])
def remove_admin_handler(message):
    # Only the Bot Owner can use this command
    if message.from_user.id != OWNER_ID:
        send_message(message.chat.id, "❌ This command can only be used by the Bot Owner.")
        return

    try:
        target_id = int(message.text.split()[1])
        if target_id == OWNER_ID:
            send_message(message.chat.id, "You cannot remove the Bot Owner.")
            return

        # Remove the ID from the list in the database using $pull
        result = admin_collection.update_one(
            {'_id': 'bot_config'},
            {'$pull': {'admin_ids': target_id}}
        )

        if result.modified_count > 0:
            send_message(message.chat.id, f"🗑️ User {target_id} has been removed from admins.")
        else:
            send_message(message.chat.id, f"User {target_id} was not found in the admin list.")
    except (IndexError, ValueError):
        send_message(message.chat.id, "Please use the correct format: `/removeadmin <user_id>`")

@bot.message_handler(commands=['listadmins'])
def list_admins_handler(message):
    # Only admins can see the list
    if not is_admin(message.from_user.id):
        send_message(message.chat.id, get_user_lang(message.from_user.id)["admin_panel_access_denied"])
        return
        
    admin_list = get_admin_list()
    if not admin_list:
        send_message(message.chat.id, "There are currently no admins configured.")
        return
        
    response_text = "👑 **Current Bot Admins** 👑\n\n"
    for admin_id in admin_list:
        if admin_id == OWNER_ID:
            response_text += f"• `{admin_id}` (Owner)\n"
        else:
            response_text += f"• `{admin_id}`\n"
    send_message(message.chat.id, response_text, parse_mode="Markdown")

# --- All other User and Admin handlers ---
# They will continue to work, but now any admin-specific ones should use 'is_admin()'
# For brevity, I've omitted repeating all of them, but the pattern is to replace
# 'message.from_user.id == ADMIN_USER_ID' with 'is_admin(message.from_user.id)'

# ... (rest of your handlers: upload_media_handler, caption_handler, etc.)

# --- Main ---
if __name__ == "__main__":
    # Initialize the admin list on first start if it doesn't exist
    get_admin_list() 
    print("Bot starting with MongoDB integration and multi-admin support...")
    bot.infinity_polling()
