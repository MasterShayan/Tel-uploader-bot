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
redeem_codes_collection = db['redeem_codes']
files_collection = db['files'] # NEW: Central collection for all files
counters_collection = db['counters'] # NEW: Collection to manage global counters

bot = telebot.TeleBot(BOT_TOKEN)

# --- NEW: Helper for Global IDs ---
def get_next_sequence_value(sequence_name):
    """Gets the next value from a counter sequence in an atomic way."""
    sequence_document = counters_collection.find_one_and_update(
        {'_id': sequence_name},
        {'$inc': {'sequence_value': 1}},
        return_document=pymongo.ReturnDocument.AFTER,
        upsert=True
    )
    return sequence_document['sequence_value']

# --- Admin Management Helpers ---
def get_admin_list():
    config = admin_collection.find_one({'_id': 'bot_config'})
    if config and 'admin_ids' in config: return config['admin_ids']
    else:
        if INITIAL_ADMIN_IDS:
            admin_collection.update_one({'_id': 'bot_config'},{'$set': {'admin_ids': INITIAL_ADMIN_IDS}},upsert=True)
            return INITIAL_ADMIN_IDS
        return []

def is_admin(user_id):
    return user_id in get_admin_list()

# --- Language Support ---
LANGUAGES = {"en": "English"}
def load_language(lang_code):
    try:
        with open(os.path.join("languages", f"{lang_code}.json"), "r", encoding="utf-8") as f: return json.load(f)
    except FileNotFoundError:
        with open(os.path.join("languages", f"{DEFAULT_LANGUAGE}.json"), "r", encoding="utf-8") as f: return json.load(f)

def get_user_lang_code(user_id):
    user_doc = users_collection.find_one({'_id': user_id}, {'language': 1})
    return user_doc.get('language', DEFAULT_LANGUAGE) if user_doc else DEFAULT_LANGUAGE

def get_user_lang(user_id):
    return load_language(get_user_lang_code(user_id))

# --- Bot Functions ---
def send_message(chat_id, text, reply_markup=None, parse_mode="HTML"):
    try: bot.send_message(chat_id, text, parse_mode=parse_mode, reply_markup=reply_markup, disable_web_page_preview=True)
    except Exception as e: print(f"Error sending message to {chat_id}: {e}")

def send_file_by_id(chat_id, file_type, file_id, caption=None):
    try:
        if file_type == "photo": bot.send_photo(chat_id, file_id, caption=caption)
        elif file_type == "video": bot.send_video(chat_id, file_id, caption=caption)
        elif file_type == "document": bot.send_document(chat_id, file_id, caption=caption)
        elif file_type == "audio": bot.send_audio(chat_id, file_id, caption=caption)
    except Exception as e: print(f"Error sending file by ID to {chat_id}: {e}")

# --- State Management ---
user_states = {}
def set_state(user_id, state, data=None): user_states[user_id] = {'state': state, 'data': data}
def get_state(user_id): return user_states.get(user_id, {}).get('state')
def get_state_data(user_id): return user_states.get(user_id, {}).get('data')
def delete_state(user_id): user_states.pop(user_id, None)

# --- Keyboards ---
def main_keyboard(lang_code):
    lang_data = load_language(lang_code)
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    btn1, btn2, btn3 = types.KeyboardButton(lang_data["upload_button"]), types.KeyboardButton(lang_data["delete_button"]), types.KeyboardButton(lang_data["get_file_button"])
    btn4, btn5, btn6, btn7 = types.KeyboardButton(lang_data["redeem_button"]), types.KeyboardButton(lang_data["caption_button"]), types.KeyboardButton(lang_data["support_button"]), types.KeyboardButton(lang_data["profile_button"])
    markup.add(btn1); markup.add(btn2, btn3); markup.add(btn4, btn5); markup.add(btn6, btn7)
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
    # MODIFIED: Logic now checks the central `files` collection for the global ID
    if len(message.text.split()) > 1 and message.text.split()[1].startswith('getfile_'):
        try:
            file_info = message.text.split()[1].replace('getfile_', '')
            global_file_id, token = file_info.split('_')
            file_doc = files_collection.find_one({'_id': int(global_file_id)})
            if file_doc and file_doc["token"] == token:
                send_file_by_id(message.chat.id, file_doc["file_type"], file_doc["file_id"])
            else:
                send_message(message.chat.id, lang_data["download_link_error"])
        except Exception as e:
            print(f"Error in getfile link: {e}")
            send_message(message.chat.id, lang_data["download_link_error"])
    else:
        users_collection.update_one({'_id': user_id}, {'$set': {'username': message.from_user.username, 'first_name': message.from_user.first_name}}, upsert=True)
        send_message(message.chat.id, lang_data["start_message"], reply_markup=main_keyboard(DEFAULT_LANGUAGE))

# All other command handlers (/panel, /addadmin, etc.) are unchanged and remain here...

# --- State & Button Handlers ---
@bot.message_handler(content_types=['text', 'photo', 'video', 'document', 'audio'], func=lambda message: get_state(message.from_user.id) is not None)
def master_state_handler(message):
    state = get_state(message.from_user.id)
    if state == "upload": upload_media_handler(message)
    # ... other state handlers ...

@bot.message_handler(func=lambda message: message.content_type == 'text')
def button_handlers(message):
    # ... routes to button functions ...
    pass

# --- Handler Implementations ---

def upload_media_handler(message):
    user_id = message.from_user.id
    lang_data = get_user_lang(user_id)
    media_type, file_id = None, None

    if message.photo: media_type, file_id = "photo", message.photo[-1].file_id
    elif message.video: media_type, file_id = "video", message.video.file_id
    elif message.document: media_type, file_id = "document", message.document.file_id
    elif message.audio: media_type, file_id = "music", message.audio.file_id
    else: # Should not happen if content_types are set, but as a safeguard
        send_message(message.chat.id, lang_data["upload_invalid_media_type"], reply_markup=main_keyboard(get_user_lang_code(user_id)))
        delete_state(user_id)
        return
        
    # Get user's current caption setting
    user_doc = users_collection.find_one({'_id': user_id}, {'caption': 1})
    caption = user_doc.get('caption', lang_data["default_caption"]) if user_doc else lang_data["default_caption"]
    
    # Save a copy to the storage group to get a permanent message_id for the t.me link
    sent_message = bot.copy_message(STORAGE_GROUP_ID, message.chat.id, message.message_id, caption=caption)
    
    # NEW: Create a document in the central `files` collection
    global_file_id = get_next_sequence_value('global_file_id')
    token = ''.join(random.choices(string.ascii_letters + string.digits, k=16))

    file_doc = {
        '_id': global_file_id,
        'uploader_id': user_id,
        'file_id': file_id, # Telegram's file_id
        'file_type': media_type,
        'message_id_in_storage': sent_message.message_id,
        'token': token,
        'created_at': datetime.utcnow()
    }
    files_collection.insert_one(file_doc)
    
    # MODIFIED: The link now uses the global ID and no longer needs user ID or file type prefix
    download_link = f"https://t.me/{bot.get_me().username}?start=getfile_{global_file_id}_{token}"
    send_message(message.chat.id, lang_data["upload_success_message"].format(file_id=global_file_id, download_link=download_link), reply_markup=main_keyboard(get_user_lang_code(user_id)))
    delete_state(user_id)

def get_file_by_id_handler(message):
    user_id = message.from_user.id
    lang_data = get_user_lang(user_id)
    file_id_to_get = message.text
    if not file_id_to_get.isdigit():
        send_message(message.chat.id, lang_data["delete_file_invalid_id"])
        return

    # NEW: Search the central `files` collection
    file_doc = files_collection.find_one({'_id': int(file_id_to_get)})
    
    if file_doc:
        send_file_by_id(user_id, file_doc["file_type"], file_doc["file_id"])
    else:
        send_message(user_id, lang_data["file_not_found"])

    delete_state(user_id)
    send_message(message.chat.id, lang_data["main_menu_back"], reply_markup=main_keyboard(get_user_lang_code(user_id)))

def delete_file_handler(message):
    user_id = message.from_user.id
    lang_data = get_user_lang(user_id)
    file_id_to_delete = message.text
    if not file_id_to_delete.isdigit():
        send_message(message.chat.id, lang_data["delete_file_invalid_id"])
        return

    # NEW: Find the file in the central collection
    file_doc = files_collection.find_one({'_id': int(file_id_to_delete)})

    if file_doc and (file_doc['uploader_id'] == user_id or is_admin(user_id)):
        # If found and the user is the owner or an admin, delete it
        files_collection.delete_one({'_id': int(file_id_to_delete)})
        # Also try to delete the message from the storage group
        try:
            bot.delete_message(STORAGE_GROUP_ID, file_doc['message_id_in_storage'])
        except Exception as e:
            print(f"Could not delete message from storage group: {e}")
        send_message(message.chat.id, lang_data["delete_file_success"].format(file_id=file_id_to_delete))
    else:
        send_message(message.chat.id, lang_data["file_not_found"])
        
    delete_state(user_id)
    send_message(message.chat.id, lang_data["main_menu_back"], reply_markup=main_keyboard(get_user_lang_code(user_id)))

def profile_button_handler(message):
    user_id = message.from_user.id
    lang_data = get_user_lang(user_id)
    
    # NEW: Count files from the central collection
    file_count = files_collection.count_documents({'uploader_id': user_id})
    
    user_doc = users_collection.find_one({'_id': user_id})
    first_name = user_doc.get('first_name', 'N/A') if user_doc else message.from_user.first_name
    
    profile_text = lang_data["profile_message"].format(first_name=first_name, user_id=user_id, file_count=file_count)
    send_message(message.chat.id, profile_text, reply_markup=main_keyboard(get_user_lang_code(user_id)))

# ... All other handlers (caption, support, admin, redeem, etc.) are included here unchanged ...


# --- Main ---
if __name__ == "__main__":
    # Ensure the counter exists
    if counters_collection.find_one({'_id': 'global_file_id'}) is None:
        counters_collection.insert_one({'_id': 'global_file_id', 'sequence_value': 0})
    
    get_admin_list() 
    print("Bot starting with Global File ID system...")
    bot.infinity_polling()
