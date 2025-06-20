import telebot
import os
import pymongo
import json
from telebot import types
import hashlib
import random
import string
from datetime import datetime
import threading
import time

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
files_collection = db['files']
counters_collection = db['counters']

bot = telebot.TeleBot(BOT_TOKEN)

# --- Helper for Global IDs ---
def get_next_sequence_value(sequence_name):
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
    if config and 'admin_ids' in config:
        return config['admin_ids']
    else:
        if INITIAL_ADMIN_IDS:
            admin_collection.update_one(
                {'_id': 'bot_config'},
                {'$set': {'admin_ids': INITIAL_ADMIN_IDS}},
                upsert=True
            )
            return INITIAL_ADMIN_IDS
        return []

def is_admin(user_id):
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
    return load_language(get_user_lang_code(user_id))

# --- Bot Functions ---
def send_message(chat_id, text, reply_markup=None, parse_mode="HTML"):
    try:
        bot.send_message(chat_id, text, parse_mode=parse_mode, reply_markup=reply_markup, disable_web_page_preview=True)
    except Exception as e:
        print(f"Error sending message to {chat_id}: {e}")

def schedule_message_deletion(chat_id, message_id, delay_seconds):
    def delete_worker():
        time.sleep(delay_seconds)
        try:
            bot.delete_message(chat_id, message_id)
        except Exception as e:
            print(f"Could not delete message {message_id} in chat {chat_id}: {e}")
    threading.Thread(target=delete_worker).start()

def send_file_by_id(chat_id, file_type, file_id, caption=None):
    sent_message = None
    try:
        if file_type == "photo": sent_message = bot.send_photo(chat_id, file_id, caption=caption)
        elif file_type == "video": sent_message = bot.send_video(chat_id, file_id, caption=caption)
        elif file_type == "document": sent_message = bot.send_document(chat_id, file_id, caption=caption)
        elif file_type == "audio" or file_type == "music": sent_message = bot.send_audio(chat_id, file_id, caption=caption)
        
        if sent_message:
            config = admin_collection.find_one({'_id': 'bot_config'}) or {}
            delay = config.get('auto_delete_seconds', 0)
            if delay > 0:
                schedule_message_deletion(chat_id, sent_message.message_id, delay)
    except Exception as e:
        print(f"Error sending file by ID to {chat_id}: {e}")
    return sent_message

def send_confirmation_disclaimer(chat_id, lang_data):
    config = admin_collection.find_one({'_id': 'bot_config'}) or {}
    delay = config.get('auto_delete_seconds', 0)
    confirmation_message = None
    if delay > 0:
        time_str = f"{delay} seconds"
        if delay >= 3600:
            hours = delay // 3600; time_str = f"{hours} hour" + ("s" if hours > 1 else "")
        elif delay >= 60:
            minutes = delay // 60; time_str = f"{minutes} minute" + ("s" if minutes > 1 else "")
        confirmation_message = send_message(chat_id, lang_data["file_delivery_success_timed"].format(time=time_str))
    else:
        confirmation_message = send_message(chat_id, lang_data["file_delivery_success"])
    
    if confirmation_message and delay > 0:
        schedule_message_deletion(chat_id, confirmation_message.message_id, delay)

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

@bot.message_handler(commands=['panel'])
def panel_command_handler(message):
    if is_admin(message.from_user.id):
        lang_data = get_user_lang(message.from_user.id)
        send_message(message.chat.id, lang_data["admin_panel_welcome"], reply_markup=admin_keyboard(get_user_lang_code(message.from_user.id)))
    else:
        send_message(message.chat.id, get_user_lang(message.from_user.id)["admin_panel_access_denied"])

@bot.message_handler(commands=['getfile'])
def getfile_command_handler(message):
    user_id = message.from_user.id
    lang_data = get_user_lang(user_id)
    send_message(message.chat.id, lang_data["get_file_request_message"], reply_markup=back_keyboard(get_user_lang_code(user_id)))
    set_state(user_id, "get_file_by_id")

@bot.message_handler(commands=['createcode'])
def create_code_command_handler(message):
    user_id = message.from_user.id
    lang_data = get_user_lang(user_id)
    if not is_admin(user_id):
        send_message(message.chat.id, lang_data["admin_panel_access_denied"])
        return
    send_message(user_id, lang_data["create_code_prompt_item"], reply_markup=back_keyboard(get_user_lang_code(user_id)))
    set_state(user_id, "create_code_awaiting_item")

@bot.message_handler(commands=['redeem'])
def redeem_command_handler(message):
    user_id = message.from_user.id
    lang_data = get_user_lang(user_id)
    send_message(message.chat.id, lang_data["redeem_prompt_code"], reply_markup=back_keyboard(get_user_lang_code(user_id)))
    set_state(user_id, "awaiting_redeem_code")

@bot.message_handler(commands=['addadmin', 'removeadmin', 'listadmins'])
def admin_management_commands(message):
    command = message.text.split()[0].lower()
    if command == '/addadmin': add_admin_handler(message)
    elif command == '/removeadmin': remove_admin_handler(message)
    elif command == '/listadmins': list_admins_handler(message)

def add_admin_handler(message):
    if message.from_user.id != OWNER_ID:
        send_message(message.chat.id, "❌ This command can only be used by the Bot Owner.")
        return
    try:
        target_id = int(message.text.split()[1])
        if is_admin(target_id):
            send_message(message.chat.id, f"User {target_id} is already an admin.")
            return
        admin_collection.update_one({'_id': 'bot_config'}, {'$addToSet': {'admin_ids': target_id}}, upsert=True)
        send_message(message.chat.id, f"✅ User {target_id} has been promoted to admin.")
    except (IndexError, ValueError):
        send_message(message.chat.id, "Please use the correct format: `/addadmin <user_id>`")

def remove_admin_handler(message):
    if message.from_user.id != OWNER_ID:
        send_message(message.chat.id, "❌ This command can only be used by the Bot Owner.")
        return
    try:
        target_id = int(message.text.split()[1])
        if target_id == OWNER_ID:
            send_message(message.chat.id, "You cannot remove the Bot Owner.")
            return
        result = admin_collection.update_one({'_id': 'bot_config'}, {'$pull': {'admin_ids': target_id}})
        if result.modified_count > 0:
            send_message(message.chat.id, f"🗑️ User {target_id} has been removed from admins.")
        else:
            send_message(message.chat.id, f"User {target_id} was not found in the admin list.")
    except (IndexError, ValueError):
        send_message(message.chat.id, "Please use the correct format: `/removeadmin <user_id>`")

def list_admins_handler(message):
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

@bot.message_handler(commands=['set_delete_timer'])
def set_delete_timer_command_handler(message):
    if message.from_user.id != OWNER_ID:
        send_message(message.chat.id, "❌ This command is for the Bot Owner only.")
        return
    lang_data = get_user_lang(message.from_user.id)
    config = admin_collection.find_one({'_id': 'bot_config'}) or {}
    current_setting = config.get('auto_delete_seconds', 0)
    send_message(message.chat.id, lang_data["set_delete_timer_prompt"].format(current_setting=current_setting), reply_markup=back_keyboard(get_user_lang_code(message.from_user.id)))
    set_state(message.from_user.id, "set_delete_timer")

@bot.message_handler(commands=['check_delete_timer'])
def check_delete_timer_command_handler(message):
    if message.from_user.id != OWNER_ID:
        send_message(message.chat.id, "❌ This command is for the Bot Owner only.")
        return
    lang_data = get_user_lang(message.from_user.id)
    config = admin_collection.find_one({'_id': 'bot_config'}) or {}
    seconds = config.get('auto_delete_seconds', 0)
    send_message(message.chat.id, lang_data["check_delete_timer_status"].format(seconds=seconds))

# --- State-Based Handlers ---
@bot.message_handler(content_types=['text', 'photo', 'video', 'document', 'audio'], func=lambda message: get_state(message.from_user.id) is not None)
def master_state_handler(message):
    state = get_state(message.from_user.id)
    if state == "create_code_awaiting_item": create_code_item_handler(message)
    elif state == "create_code_awaiting_limit": create_code_limit_handler(message)
    elif state == "awaiting_redeem_code": redeem_code_handler(message)
    elif state == "set_delete_timer": set_delete_timer_limit_handler(message)
    elif state == "upload": upload_media_handler(message)
    elif state == "set-caption": set_caption_handler(message)
    elif state == "delete-file": delete_file_handler(message)
    elif state == "get_file_by_id": get_file_by_id_handler(message)
    elif state == "support": support_handler(message)
    elif is_admin(message.from_user.id):
        if state == "ban_user": ban_user_message_handler(message)
        elif state == "unban_user": unban_user_message_handler(message)
        elif state == "broadcast_message": broadcast_message_handler(message)
        elif state == "forward_broadcast_message": forward_broadcast_message_handler(message)

# --- Button Handlers ---
@bot.message_handler(func=lambda message: message.content_type == 'text')
def button_handlers(message):
    lang_data = get_user_lang(message.from_user.id)
    text = message.text
    if text == lang_data["upload_button"]: upload_button_handler(message)
    elif text == lang_data["caption_button"]: caption_button_handler(message)
    elif text == lang_data["delete_button"]: delete_button_handler(message)
    elif text == lang_data["support_button"]: support_button_handler(message)
    elif text == lang_data["profile_button"]: profile_button_handler(message)
    elif text == lang_data["get_file_button"]: get_file_button_handler(message)
    elif text == lang_data["redeem_button"]: redeem_command_handler(message)
    elif text == lang_data["back_button"]: back_button_handler(message)
    elif is_admin(message.from_user.id):
        if text == lang_data["admin_stats_button"]: admin_stats_handler(message)
        elif text == lang_data["admin_bot_status_button"]: admin_bot_status_handler(message)
        elif text == lang_data["admin_ban_button"]: admin_ban_handler(message)
        elif text == lang_data["admin_unban_button"]: admin_unban_handler(message)
        elif text == lang_data["admin_broadcast_button"]: admin_broadcast_handler(message)
        elif text == lang_data["admin_forward_broadcast_button"]: admin_forward_broadcast_handler(message)

# --- Handler Implementations ---

def create_code_item_handler(message):
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

def create_code_limit_handler(message):
    user_id = message.from_user.id
    lang_data = get_user_lang(user_id)
    prize_data = get_state_data(user_id)
    if not message.text.isdigit():
        send_message(user_id, "❌ Invalid number. Please enter a number for the redemption limit.")
        return
    def generate_redeem_code():
        while True:
            code = '-'.join(''.join(random.choices(string.ascii_uppercase + string.digits, k=4)) for _ in range(3))
            if redeem_codes_collection.find_one({'_id': code}) is None: return code
    db_document = {
        '_id': generate_redeem_code(), 'item_type': prize_data['type'], 'item_content': prize_data['content'],
        'redemption_limit': int(message.text), 'redemption_count': 0, 'redeemed_by': [],
        'creator_id': user_id, 'created_at': datetime.utcnow()
    }
    redeem_codes_collection.insert_one(db_document)
    send_message(user_id, lang_data["create_code_success"].format(code=db_document['_id']), reply_markup=main_keyboard(get_user_lang_code(user_id)), parse_mode="Markdown")
    delete_state(user_id)

def redeem_code_handler(message):
    user_id = message.from_user.id
    lang_data = get_user_lang(user_id)
    user_code = message.text.strip().upper()
    code_doc = redeem_codes_collection.find_one({'_id': user_code})
    if not code_doc:
        send_message(user_id, lang_data["redeem_error_not_found"], reply_markup=main_keyboard(get_user_lang_code(user_id)))
        delete_state(user_id)
        return
    if user_id in code_doc.get('redeemed_by', []):
        send_message(user_id, lang_data["redeem_error_already_claimed"], reply_markup=main_keyboard(get_user_lang_code(user_id)))
        delete_state(user_id)
        return
    if code_doc['redemption_limit'] != 0 and code_doc['redemption_count'] >= code_doc['redemption_limit']:
        send_message(user_id, lang_data["redeem_error_limit_reached"], reply_markup=main_keyboard(get_user_lang_code(user_id)))
        delete_state(user_id)
        return
    redeem_codes_collection.update_one({'_id': user_code}, {'$inc': {'redemption_count': 1}, '$addToSet': {'redeemed_by': user_id}})
    item_type, item_content = code_doc['item_type'], code_doc['item_content']
    if item_type == 'text':
        sent_message = bot.send_message(user_id, item_content['text'])
        config = admin_collection.find_one({'_id': 'bot_config'}) or {}
        delay = config.get('auto_delete_seconds', 0)
        if delay > 0:
            schedule_message_deletion(user_id, sent_message.message_id, delay)
    else:
        send_file_by_id(user_id, item_type, item_content['file_id'])
    
    config = admin_collection.find_one({'_id': 'bot_config'}) or {}
    delay = config.get('auto_delete_seconds', 0)
    if delay > 0:
        time_str = f"{delay} seconds"
        if delay >= 3600:
            hours = delay // 3600; time_str = f"{hours} hour" + ("s" if hours > 1 else "")
        elif delay >= 60:
            minutes = delay // 60; time_str = f"{minutes} minute" + ("s" if minutes > 1 else "")
        send_message(user_id, lang_data["redeem_success_timed"].format(time=time_str), reply_markup=main_keyboard(get_user_lang_code(user_id)))
    else:
        send_message(user_id, lang_data["redeem_success"], reply_markup=main_keyboard(get_user_lang_code(user_id)))
    
    try:
        creator_id, user_info = code_doc['creator_id'], users_collection.find_one({'_id': user_id})
        remaining = "Unlimited" if code_doc['redemption_limit'] == 0 else code_doc['redemption_limit'] - (code_doc['redemption_count'] + 1)
        username = user_info.get('username', 'N/A') if user_info else 'N/A'
        notification_text = lang_data["admin_redeem_notification"].format(username=username, user_id=user_id, code=user_code, remaining=remaining)
        send_message(creator_id, notification_text)
    except Exception as e:
        print(f"Failed to send admin notification: {e}")
    delete_state(user_id)

def set_delete_timer_limit_handler(message):
    user_id = message.from_user.id
    lang_data = get_user_lang(user_id)
    if not message.text.isdigit():
        send_message(user_id, "Invalid input. Please send a number.")
        return
    seconds = int(message.text)
    admin_collection.update_one({'_id': 'bot_config'},{'$set': {'auto_delete_seconds': seconds}},upsert=True)
    send_message(user_id, lang_data["set_delete_timer_success"].format(seconds=seconds), reply_markup=main_keyboard(get_user_lang_code(user_id)))
    delete_state(user_id)

def upload_button_handler(message):
    user_id = message.from_user.id
    lang_data = get_user_lang(user_id)
    send_message(message.chat.id, lang_data["upload_request_message"], reply_markup=back_keyboard(get_user_lang_code(user_id)))
    set_state(user_id, "upload")

def upload_media_handler(message):
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
        'token': token, 'created_at': datetime.utcnow()
    }
    files_collection.insert_one(file_doc)
    download_link = f"https://t.me/{bot.get_me().username}?start=getfile_{global_file_id}_{token}"
    send_message(message.chat.id, lang_data["upload_success_message"].format(file_id=global_file_id, download_link=download_link), reply_markup=main_keyboard(get_user_lang_code(user_id)))
    delete_state(user_id)

def caption_button_handler(message):
    user_id = message.from_user.id
    lang_data = get_user_lang(user_id)
    user_doc = users_collection.find_one({'_id': user_id}, {'caption': 1})
    current_caption = user_doc.get('caption', lang_data["default_caption"]) if user_doc else lang_data["default_caption"]
    send_message(message.chat.id, lang_data["caption_request_message"].format(current_caption=current_caption), reply_markup=back_keyboard(get_user_lang_code(user_id)))
    set_state(user_id, "set-caption")

def set_caption_handler(message):
    user_id = message.from_user.id
    users_collection.update_one({'_id': user_id}, {'$set': {'caption': message.text}}, upsert=True)
    send_message(message.chat.id, get_user_lang(user_id)["caption_saved_message"], reply_markup=main_keyboard(get_user_lang_code(user_id)))
    delete_state(user_id)

def delete_button_handler(message):
    user_id = message.from_user.id
    lang_data = get_user_lang(user_id)
    send_message(message.chat.id, lang_data["delete_file_request_message"], reply_markup=back_keyboard(get_user_lang_code(user_id)))
    set_state(user_id, "delete-file")

def delete_file_handler(message):
    user_id = message.from_user.id
    lang_data = get_user_lang(user_id)
    file_id_to_delete = message.text
    if not file_id_to_delete.isdigit():
        send_message(message.chat.id, lang_data["delete_file_invalid_id"], reply_markup=back_keyboard(get_user_lang_code(user_id)))
        return
    file_doc = files_collection.find_one({'_id': int(file_id_to_delete)})
    if file_doc and (file_doc['uploader_id'] == user_id or is_admin(user_id)):
        files_collection.delete_one({'_id': int(file_id_to_delete)})
        try: bot.delete_message(STORAGE_GROUP_ID, file_doc['message_id_in_storage'])
        except Exception as e: print(f"Could not delete message from storage group: {e}")
        send_message(message.chat.id, lang_data["delete_file_success"].format(file_id=file_id_to_delete), reply_markup=main_keyboard(get_user_lang_code(user_id)))
    else:
        send_message(message.chat.id, lang_data["file_not_found"], reply_markup=main_keyboard(get_user_lang_code(user_id)))
    delete_state(user_id)

def support_button_handler(message):
    user_id = message.from_user.id
    lang_data = get_user_lang(user_id)
    send_message(message.chat.id, lang_data["support_message_request"], reply_markup=back_keyboard(get_user_lang_code(user_id)))
    set_state(user_id, "support")

def support_handler(message):
    user_id = message.from_user.id
    lang_data = get_user_lang(user_id)
    support_message = lang_data["support_message_prefix"].format(first_name=message.from_user.first_name, user_id=user_id) + message.text
    admin_markup = types.InlineKeyboardMarkup()
    admin_markup.add(types.InlineKeyboardButton(text=lang_data["support_answer_button"], callback_data=f"answer_support_{user_id}"))
    send_message(OWNER_ID, support_message, reply_markup=admin_markup)
    send_message(message.chat.id, lang_data["support_message_sent"], reply_markup=main_keyboard(get_user_lang_code(user_id)))
    delete_state(user_id)

def profile_button_handler(message):
    user_id = message.from_user.id
    lang_data = get_user_lang(user_id)
    file_count = files_collection.count_documents({'uploader_id': user_id})
    user_doc = users_collection.find_one({'_id': user_id})
    first_name = user_doc.get('first_name', message.from_user.first_name) if user_doc else message.from_user.first_name
    profile_text = lang_data["profile_message"].format(first_name=first_name, user_id=user_id, file_count=file_count)
    send_message(message.chat.id, profile_text, reply_markup=main_keyboard(get_user_lang_code(user_id)))

def get_file_button_handler(message):
    user_id = message.from_user.id
    lang_data = get_user_lang(user_id)
    send_message(message.chat.id, lang_data["get_file_request_message"], reply_markup=back_keyboard(get_user_lang_code(user_id)))
    set_state(user_id, "get_file_by_id")

def get_file_by_id_handler(message):
    user_id = message.from_user.id
    lang_data = get_user_lang(user_id)
    file_id_to_get = message.text
    if not file_id_to_get.isdigit():
        send_message(message.chat.id, lang_data["delete_file_invalid_id"])
        delete_state(user_id)
        return
    file_doc = files_collection.find_one({'_id': int(file_id_to_get)})
    if file_doc:
        send_file_by_id(user_id, file_doc["file_type"], file_doc["file_id"])
        send_confirmation_disclaimer(user_id, lang_data)
    else:
        send_message(user_id, lang_data["file_not_found"])
    delete_state(user_id)
    send_message(message.chat.id, lang_data["main_menu_back"], reply_markup=main_keyboard(get_user_lang_code(user_id)))

def back_button_handler(message):
    user_id = message.from_user.id
    delete_state(user_id)
    send_message(message.chat.id, get_user_lang(user_id)["main_menu_back"], reply_markup=main_keyboard(get_user_lang_code(user_id)))

def admin_stats_handler(message):
    user_id = message.from_user.id
    lang_data = get_user_lang(user_id)
    user_count = users_collection.count_documents({})
    config = admin_collection.find_one({'_id': 'bot_config'}) or {}
    bot_status = config.get("bot_status", lang_data["bot_status_on"])
    stats_text = lang_data["admin_stats_message"].format(user_count=user_count, bot_status=bot_status)
    send_message(message.chat.id, stats_text, reply_markup=admin_keyboard(get_user_lang_code(user_id)))

def admin_bot_status_handler(message):
    user_id = message.from_user.id
    lang_data = get_user_lang(user_id)
    config = admin_collection.find_one({'_id': 'bot_config'}) or {}
    current_status = config.get("bot_status", lang_data["bot_status_on"])
    new_status = lang_data["bot_status_on"] if current_status == lang_data["bot_status_off"] else lang_data["bot_status_off"]
    admin_collection.update_one({'_id': 'bot_config'}, {'$set': {'bot_status': new_status}}, upsert=True)
    send_message(message.chat.id, lang_data["admin_bot_status_changed"].format(bot_status=new_status), reply_markup=admin_keyboard(get_user_lang_code(user_id)))

def admin_ban_handler(message):
    user_id = message.from_user.id
    lang_data = get_user_lang(user_id)
    send_message(message.chat.id, lang_data["admin_ban_request"], reply_markup=back_keyboard(get_user_lang_code(user_id)))
    set_state(user_id, "ban_user")

def ban_user_message_handler(message):
    user_id = message.from_user.id
    lang_data = get_user_lang(user_id)
    try:
        user_id_to_ban = int(message.text)
        if user_id_to_ban == OWNER_ID or is_admin(user_id_to_ban):
            send_message(message.chat.id, "You cannot ban an admin or the Bot Owner.")
            delete_state(user_id)
            return
        users_collection.update_one({'_id': user_id_to_ban}, {'$set': {'banned': True}}, upsert=True)
        send_message(message.chat.id, lang_data["admin_ban_success"].format(user_id=user_id_to_ban), reply_markup=admin_keyboard(get_user_lang_code(user_id)))
    except ValueError:
        send_message(message.chat.id, lang_data["admin_invalid_user_id"], reply_markup=back_keyboard(get_user_lang_code(user_id)))
    delete_state(user_id)

def admin_unban_handler(message):
    user_id = message.from_user.id
    lang_data = get_user_lang(user_id)
    send_message(message.chat.id, lang_data["admin_unban_request"], reply_markup=back_keyboard(get_user_lang_code(user_id)))
    set_state(user_id, "unban_user")

def unban_user_message_handler(message):
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

def admin_broadcast_handler(message):
    user_id = message.from_user.id
    lang_data = get_user_lang(user_id)
    send_message(message.chat.id, lang_data["admin_broadcast_request"], reply_markup=back_keyboard(get_user_lang_code(user_id)))
    set_state(user_id, "broadcast_message")

def broadcast_message_handler(message):
    user_id = message.from_user.id
    lang_data = get_user_lang(user_id)
    cursor = users_collection.find({'banned': {'$ne': True}}, {'_id': 1})
    success_count, fail_count = 0, 0
    for doc in cursor:
        try: send_message(doc['_id'], message.text); success_count += 1
        except: fail_count += 1
    send_message(message.chat.id, lang_data["admin_broadcast_report"].format(success_count=success_count, fail_count=fail_count), reply_markup=admin_keyboard(get_user_lang_code(user_id)))
    delete_state(user_id)

def admin_forward_broadcast_handler(message):
    user_id = message.from_user.id
    lang_data = get_user_lang(user_id)
    send_message(message.chat.id, lang_data["admin_forward_broadcast_request"], reply_markup=back_keyboard(get_user_lang_code(user_id)))
    set_state(user_id, "forward_broadcast_message")

def forward_broadcast_message_handler(message):
    user_id = message.from_user.id
    lang_data = get_user_lang(user_id)
    cursor = users_collection.find({'banned': {'$ne': True}}, {'_id': 1})
    success_count, fail_count = 0, 0
    for doc in cursor:
        try: bot.forward_message(doc['_id'], message.chat.id, message.message_id); success_count += 1
        except: fail_count += 1
    send_message(message.chat.id, lang_data["admin_forward_broadcast_report"].format(success_count=success_count, fail_count=fail_count), reply_markup=admin_keyboard(get_user_lang_code(user_id)))
    delete_state(user_id)

# --- Main ---
if __name__ == "__main__":
    counters_collection.update_one({'_id': 'global_file_id'}, {'$setOnInsert': {'sequence_value': 0}}, upsert=True)
    get_admin_list() 
    print("Bot starting with all features enabled...")
    bot.infinity_polling()
