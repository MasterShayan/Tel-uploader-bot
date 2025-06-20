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

bot = telebot.TeleBot(BOT_TOKEN)

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

# NEW: Function to send files by ID to remove forward tags
def send_file_by_id(chat_id, file_type, file_id, caption=None):
    try:
        if file_type == "photo":
            bot.send_photo(chat_id, file_id, caption=caption)
        elif file_type == "video":
            bot.send_video(chat_id, file_id, caption=caption)
        elif file_type == "document":
            bot.send_document(chat_id, file_id, caption=caption)
        elif file_type == "audio":
            bot.send_audio(chat_id, file_id, caption=caption)
    except Exception as e:
        print(f"Error sending file by ID to {chat_id}: {e}")


# --- State Management ---
user_states = {}
def set_state(user_id, state, data=None):
    user_states[user_id] = {'state': state, 'data': data}
def get_state(user_id): 
    return user_states.get(user_id, {}).get('state')
def get_state_data(user_id):
    return user_states.get(user_id, {}).get('data')
def delete_state(user_id): 
    user_states.pop(user_id, None)

# --- Keyboards ---
def main_keyboard(lang_code):
    lang_data = load_language(lang_code)
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    btn1 = types.KeyboardButton(lang_data["upload_button"])
    btn2 = types.KeyboardButton(lang_data["delete_button"])
    btn3 = types.KeyboardButton(lang_data["get_file_button"])
    btn4 = types.KeyboardButton(lang_data["redeem_button"])
    btn5 = types.KeyboardButton(lang_data["caption_button"])
    btn6 = types.KeyboardButton(lang_data["support_button"])
    btn7 = types.KeyboardButton(lang_data["profile_button"])
    markup.add(btn1)
    markup.add(btn2, btn3)
    markup.add(btn4, btn5)
    markup.add(btn6, btn7)
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
            file_type_prefix, file_code, file_user_id, token = file_info.split('_')
            media_type_map = {"p": "photo", "v": "video", "d": "document", "m": "music"}
            media_type = media_type_map.get(file_type_prefix)
            user_doc = users_collection.find_one({'_id': int(file_user_id)})
            if user_doc:
                file_data = user_doc.get(media_type, {}).get(file_code)
                if file_data and file_data["token"] == token:
                    # Anonymity is less critical here as it's a direct link to the user
                    forward_message(message.chat.id, STORAGE_GROUP_ID, file_data["message_id_in_group"])
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
    if command == '/addadmin':
        add_admin_handler(message)
    elif command == '/removeadmin':
        remove_admin_handler(message)
    elif command == '/listadmins':
        list_admins_handler(message)
        
def add_admin_handler(message):
    # This is now a helper, not a message handler
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
    # This is now a helper, not a message handler
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
    # This is now a helper, not a message handler
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

# --- All other handlers (state-based and button-based) ---

@bot.message_handler(content_types=['text', 'photo', 'video', 'document', 'audio'], func=lambda message: get_state(message.from_user.id) is not None)
def master_state_handler(message):
    # This single handler routes all messages for users who are in a 'state'
    state = get_state(message.from_user.id)
    if state == "create_code_awaiting_item":
        create_code_item_handler(message)
    elif state == "create_code_awaiting_limit":
        create_code_limit_handler(message)
    elif state == "awaiting_redeem_code":
        redeem_code_handler(message)
    elif state == "upload":
        upload_media_handler(message)
    elif state == "set-caption":
        set_caption_handler(message)
    elif state == "delete-file":
        delete_file_handler(message)
    elif state == "get_file_by_id":
        get_file_by_id_handler(message)
    elif state == "support":
        support_handler(message)
    elif is_admin(message.from_user.id):
        if state == "ban_user": ban_user_message_handler(message)
        elif state == "unban_user": unban_user_message_handler(message)
        elif state == "broadcast_message": broadcast_message_handler(message)
        elif state == "forward_broadcast_message": forward_broadcast_message_handler(message)

@bot.message_handler(func=lambda message: message.content_type == 'text')
def button_handlers(message):
    # This single handler routes all button clicks
    lang_data = get_user_lang(message.from_user.id)
    text = message.text
    if text == lang_data["upload_button"]: upload_button_handler(message)
    elif text == lang_data["caption_button"]: caption_button_handler(message)
    elif text == lang_data["delete_button"]: delete_button_handler(message)
    elif text == lang_data["support_button"]: support_button_handler(message)
    elif text == lang_data["profile_button"]: profile_button_handler(message)
    elif text == lang_data["get_file_button"]: get_file_button_handler(message)
    elif text == lang_data["redeem_button"]: redeem_command_and_button_handler(message) # Use the same handler as the command
    elif text == lang_data["back_button"]: back_button_handler(message)
    elif is_admin(message.from_user.id):
        if text == lang_data["admin_stats_button"]: admin_stats_handler(message)
        elif text == lang_data["admin_bot_status_button"]: admin_bot_status_handler(message)
        elif text == lang_data["admin_ban_button"]: admin_ban_handler(message)
        elif text == lang_data["admin_unban_button"]: admin_unban_handler(message)
        elif text == lang_data["admin_broadcast_button"]: admin_broadcast_handler(message)
        elif text == lang_data["admin_forward_broadcast_button"]: admin_forward_broadcast_handler(message)

# --- Handler Implementations (Helper functions called by the routers above) ---

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
        send_message(user_id, item_content['text'])
    else:
        send_file_by_id(user_id, item_type, item_content['file_id'])
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

def upload_button_handler(message):
    user_id = message.from_user.id
    lang_data = get_user_lang(user_id)
    send_message(message.chat.id, lang_data["upload_request_message"], reply_markup=back_keyboard(get_user_lang_code(user_id)))
    set_state(user_id, "upload")

def upload_media_handler(message):
    user_id = message.from_user.id
    lang_data = get_user_lang(user_id)
    media_type, file_id = None, None
    if message.photo: media_type, file_id = "photo", message.photo[-1].file_id
    elif message.video: media_type, file_id = "video", message.video.file_id
    elif message.document: media_type, file_id = "document", message.document.file_id
    elif message.audio: media_type, file_id = "music", message.audio.file_id
    user_doc = users_collection.find_one({'_id': user_id}, {'caption': 1, media_type: 1})
    caption = user_doc.get('caption', lang_data["default_caption"]) if user_doc else lang_data["default_caption"]
    sent_message = bot.copy_message(STORAGE_GROUP_ID, message.chat.id, message.message_id, caption=caption)
    message_id_in_group = sent_message.message_id
    if user_doc and media_type in user_doc and isinstance(user_doc.get(media_type), dict):
        file_key = str(len(user_doc[media_type]) + 1)
    else: file_key = '1'
    token = ''.join(random.choices(string.ascii_letters + string.digits, k=16))
    file_data_to_save = {"file_id": file_id, "message_id_in_group": message_id_in_group, "token": token}
    users_collection.update_one({'_id': user_id}, {'$set': {f"{media_type}.{file_key}": file_data_to_save}}, upsert=True)
    download_link = f"https://t.me/{bot.get_me().username}?start=getfile_{media_type[0]}_{file_key}_{user_id}_{token}"
    send_message(message.chat.id, lang_data["upload_success_message"].format(file_id=file_key, download_link=download_link), reply_markup=main_keyboard(get_user_lang_code(user_id)))
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
    user_doc = users_collection.find_one({'_id': user_id})
    if not user_doc:
        send_message(message.chat.id, lang_data["file_not_found"], reply_markup=main_keyboard(get_user_lang_code(user_id)))
        delete_state(user_id)
        return
    deleted = False
    for media_type in ["photo", "video", "music", "document"]:
        if media_type in user_doc and file_id_to_delete in user_doc[media_type]:
            users_collection.update_one({'_id': user_id}, {'$unset': {f"{media_type}.{file_id_to_delete}": ""}})
            deleted = True
            break
    if deleted: send_message(message.chat.id, lang_data["delete_file_success"].format(file_id=file_id_to_delete), reply_markup=main_keyboard(get_user_lang_code(user_id)))
    else: send_message(message.chat.id, lang_data["file_not_found"], reply_markup=main_keyboard(get_user_lang_code(user_id)))
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
    user_doc = users_collection.find_one({'_id': user_id})
    file_count = 0
    if user_doc:
        for media_type in ["photo", "video", "music", "document"]:
            if media_type in user_doc and isinstance(user_doc[media_type], dict):
                file_count += len(user_doc[media_type])
    profile_text = lang_data["profile_message"].format(first_name=message.from_user.first_name, user_id=user_id, file_count=file_count)
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
        send_message(message.chat.id, lang_data["delete_file_invalid_id"], reply_markup=back_keyboard(get_user_lang_code(user_id)))
        return
    user_doc = users_collection.find_one({'_id': user_id})
    if not user_doc:
        send_message(message.chat.id, lang_data["file_not_found"], reply_markup=main_keyboard(get_user_lang_code(user_id)))
        delete_state(user_id)
        return
    file_found = False
    for media_type in ["photo", "video", "music", "document"]:
        if media_type in user_doc and isinstance(user_doc[media_type], dict):
            if file_id_to_get in user_doc[media_type]:
                file_data = user_doc[media_type][file_id_to_get]
                send_file_by_id(user_id, media_type, file_data["file_id"])
                file_found = True
                break
    if file_found:
        delete_state(user_id)
        send_message(message.chat.id, lang_data["main_menu_back"], reply_markup=main_keyboard(get_user_lang_code(user_id)))
    else:
        send_message(message.chat.id, lang_data["file_not_found"])
        delete_state(user_id)

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
        if user_id_to_ban == OWNER_ID:
            send_message(message.chat.id, "You cannot ban the Bot Owner.")
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
        try:
            send_message(doc['_id'], message.text)
            success_count += 1
        except:
            fail_count += 1
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
        try:
            forward_message(doc['_id'], message.chat.id, message.message_id)
            success_count += 1
        except:
            fail_count += 1
    send_message(message.chat.id, lang_data["admin_forward_broadcast_report"].format(success_count=success_count, fail_count=fail_count), reply_markup=admin_keyboard(get_user_lang_code(user_id)))
    delete_state(user_id)

# --- Main ---
if __name__ == "__main__":
    get_admin_list() 
    print("Bot starting with MongoDB integration and multi-admin support...")
    bot.infinity_polling()
