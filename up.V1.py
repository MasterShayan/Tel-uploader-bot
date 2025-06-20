import telebot
import os
import pymongo
import json
from telebot import types
import hashlib
import random
import string

# --- Config (Reading from Heroku Environment) ---
BOT_TOKEN = os.environ.get('BOT_TOKEN')
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD')
ADMIN_USER_ID = int(os.environ.get('ADMIN_USER_ID'))
STORAGE_GROUP_ID = int(os.environ.get('STORAGE_GROUP_ID'))
MONGODB_URI = os.environ.get('MONGODB_URI')
DEFAULT_LANGUAGE = "en"

# --- MongoDB Setup ---
client = pymongo.MongoClient(MONGODB_URI)
db = client['uploader_bot_db']  # The main database
users_collection = db['users']   # Collection for all user data
admin_collection = db['admin_config'] # Collection for bot-wide settings

bot = telebot.TeleBot(BOT_TOKEN)

# --- Language Support (English Only) ---
LANGUAGES = {
    "en": "English"
}

def load_language(lang_code):
    # This function now only needs to handle the local language JSON file.
    try:
        with open(os.path.join("languages", f"{lang_code}.json"), "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        # Fallback to default language if a user's language file is missing
        with open(os.path.join("languages", f"{DEFAULT_LANGUAGE}.json"), "r", encoding="utf-8") as f:
            return json.load(f)

def get_user_lang_code(user_id):
    """Gets user language from MongoDB."""
    user_doc = users_collection.find_one({'_id': user_id}, {'language': 1})
    if user_doc:
        return user_doc.get('language', DEFAULT_LANGUAGE)
    return DEFAULT_LANGUAGE

def get_user_lang(user_id):
    """Gets user language data based on their code."""
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

# --- State Management (Remains in-memory) ---
user_states = {}

def set_state(user_id, state):
    user_states[user_id] = state

def get_state(user_id):
    return user_states.get(user_id)

def delete_state(user_id):
    user_states.pop(user_id, None)

# --- Keyboards ---
def main_keyboard(lang_code):
    lang_data = load_language(lang_code)
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    # Row 1
    markup.add(types.KeyboardButton(lang_data["upload_button"]))
    # Row 2
    markup.add(types.KeyboardButton(lang_data["delete_button"]), types.KeyboardButton(lang_data["get_file_button"]))
    # Row 3
    markup.add(types.KeyboardButton(lang_data["caption_button"]), types.KeyboardButton(lang_data["support_button"]), types.KeyboardButton(lang_data["profile_button"]))
    return markup

def admin_keyboard(lang_code):
    lang_data = load_language(lang_code)
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton(lang_data["admin_stats_button"]), types.KeyboardButton(lang_data["admin_bot_status_button"]))
    markup.add(types.KeyboardButton(lang_data["admin_ban_button"]), types.KeyboardButton(lang_data["admin_unban_button"]))
    markup.add(types.KeyboardButton(lang_data["admin_broadcast_button"]), types.KeyboardButton(lang_data["admin_forward_broadcast_button"]))
    markup.add(types.KeyboardButton(lang_data["admin_settings_button"]))
    return markup

def back_keyboard(lang_code):
    lang_data = load_language(lang_code)
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton(lang_data["back_button"]))
    return markup

def language_keyboard():
    markup = types.InlineKeyboardMarkup()
    for lang_code, lang_name in LANGUAGES.items():
        markup.add(types.InlineKeyboardButton(text=lang_name, callback_data=f"set_lang_{lang_code}"))
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

            # Fetch user data from MongoDB
            user_doc = users_collection.find_one({'_id': int(file_user_id)})
            if user_doc:
                file_data = user_doc.get(media_type, {}).get(file_code)
                if file_data and file_data["token"] == token:
                    forward_message(message.chat.id, STORAGE_GROUP_ID, file_data["message_id_in_group"])
                else:
                    send_message(message.chat.id, lang_data["download_link_error"])
            else:
                send_message(message.chat.id, lang_data["download_link_error"])
        except Exception as e:
            print(f"Error in getfile: {e}")
            send_message(message.chat.id, lang_data["download_link_error"])
    else:
        if len(LANGUAGES) > 1:
            send_message(message.chat.id, lang_data["start_message"], reply_markup=language_keyboard())
        else:
            send_message(message.chat.id, lang_data["start_message"], reply_markup=main_keyboard(DEFAULT_LANGUAGE))

@bot.callback_query_handler(func=lambda call: call.data.startswith('set_lang_'))
def language_callback_handler(call):
    lang_code = call.data.split('_')[2]
    user_id = call.from_user.id
    
    # Update user's language in MongoDB
    users_collection.update_one({'_id': user_id}, {'$set': {'language': lang_code}}, upsert=True)

    lang_data = load_language(lang_code)
    send_message(call.message.chat.id, lang_data["language_set_message"].format(language=LANGUAGES[lang_code]), reply_markup=main_keyboard(lang_code))
    bot.answer_callback_query(call.id, lang_data["language_changed_alert"])

@bot.message_handler(commands=['panel'])
def panel_command_handler(message):
    user_id = message.from_user.id
    lang_data = get_user_lang(user_id)
    if user_id == ADMIN_USER_ID:
        send_message(message.chat.id, lang_data["admin_panel_welcome"], reply_markup=admin_keyboard(get_user_lang_code(user_id)))
    else:
        send_message(message.chat.id, lang_data["admin_panel_access_denied"])

# --- NEW: /getfile Command Handler ---
@bot.message_handler(commands=['getfile'])
def getfile_command_handler(message):
    user_id = message.from_user.id
    lang_data = get_user_lang(user_id)
    
    # Ask the user for the File ID
    send_message(message.chat.id, lang_data["get_file_request_message"], reply_markup=back_keyboard(get_user_lang_code(user_id)))
    
    # Set the user's state so the bot knows to expect a file ID next
    set_state(user_id, "get_file_by_id")

# --- User Handlers ---
@bot.message_handler(func=lambda message: message.text == get_user_lang(message.from_user.id)["upload_button"])
def upload_button_handler(message):
    user_id = message.from_user.id
    lang_data = get_user_lang(user_id)
    send_message(message.chat.id, lang_data["upload_request_message"], reply_markup=back_keyboard(get_user_lang_code(user_id)))
    set_state(user_id, "upload")

@bot.message_handler(content_types=['photo', 'video', 'document', 'audio'], func=lambda message: get_state(message.from_user.id) == "upload")
def upload_media_handler(message):
    user_id = message.from_user.id
    lang_data = get_user_lang(user_id)
    media_type, file_id = None, None

    if message.photo: media_type, file_id = "photo", message.photo[-1].file_id
    elif message.video: media_type, file_id = "video", message.video.file_id
    elif message.document: media_type, file_id = "document", message.document.file_id
    elif message.audio: media_type, file_id = "music", message.audio.file_id

    if not media_type:
        send_message(message.chat.id, lang_data["upload_invalid_media_type"], reply_markup=main_keyboard(get_user_lang_code(user_id)))
        delete_state(user_id)
        return
    
    user_doc = users_collection.find_one({'_id': user_id}, {'caption': 1, media_type: 1})
    caption = user_doc.get('caption', lang_data["default_caption"]) if user_doc else lang_data["default_caption"]
    
    sent_message = bot.copy_message(STORAGE_GROUP_ID, message.chat.id, message.message_id, caption=caption)
    message_id_in_group = sent_message.message_id
    
    if user_doc and media_type in user_doc:
        file_key = str(len(user_doc[media_type]) + 1)
    else:
        file_key = '1'
        
    token = ''.join(random.choices(string.ascii_letters + string.digits, k=16))
    file_data_to_save = {
        "file_id": file_id, "message_id_in_group": message_id_in_group, "token": token
    }
    
    users_collection.update_one(
        {'_id': user_id},
        {'$set': {f"{media_type}.{file_key}": file_data_to_save}},
        upsert=True
    )

    download_link = f"https://t.me/{bot.get_me().username}?start=getfile_{media_type[0]}_{file_key}_{user_id}_{token}"
    send_message(message.chat.id, lang_data["upload_success_message"].format(file_id=file_key, download_link=download_link), reply_markup=main_keyboard(get_user_lang_code(user_id)))
    delete_state(user_id)

@bot.message_handler(func=lambda message: message.text == get_user_lang(message.from_user.id)["caption_button"])
def caption_button_handler(message):
    user_id = message.from_user.id
    lang_data = get_user_lang(user_id)
    user_doc = users_collection.find_one({'_id': user_id}, {'caption': 1})
    current_caption = user_doc.get('caption', lang_data["default_caption"]) if user_doc else lang_data["default_caption"]
    send_message(message.chat.id, lang_data["caption_request_message"].format(current_caption=current_caption), reply_markup=back_keyboard(get_user_lang_code(user_id)))
    set_state(user_id, "set-caption")

@bot.message_handler(func=lambda message: get_state(message.from_user.id) == "set-caption")
def set_caption_handler(message):
    user_id = message.from_user.id
    lang_data = get_user_lang(user_id)
    users_collection.update_one({'_id': user_id}, {'$set': {'caption': message.text}}, upsert=True)
    send_message(message.chat.id, lang_data["caption_saved_message"], reply_markup=main_keyboard(get_user_lang_code(user_id)))
    delete_state(user_id)

@bot.message_handler(func=lambda message: message.text == get_user_lang(message.from_user.id)["delete_button"])
def delete_button_handler(message):
    user_id = message.from_user.id
    lang_data = get_user_lang(user_id)
    send_message(message.chat.id, lang_data["delete_file_request_message"], reply_markup=back_keyboard(get_user_lang_code(user_id)))
    set_state(user_id, "delete-file")

@bot.message_handler(func=lambda message: get_state(message.from_user.id) == "delete-file")
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
    
    if deleted:
        send_message(message.chat.id, lang_data["delete_file_success"].format(file_id=file_id_to_delete), reply_markup=main_keyboard(get_user_lang_code(user_id)))
    else:
        send_message(message.chat.id, lang_data["file_not_found"], reply_markup=main_keyboard(get_user_lang_code(user_id)))
    delete_state(user_id)

@bot.message_handler(func=lambda message: message.text == get_user_lang(message.from_user.id)["support_button"])
def support_button_handler(message):
    user_id = message.from_user.id
    lang_data = get_user_lang(user_id)
    send_message(message.chat.id, lang_data["support_message_request"], reply_markup=back_keyboard(get_user_lang_code(user_id)))
    set_state(user_id, "support")

@bot.message_handler(func=lambda message: get_state(message.from_user.id) == "support")
def support_handler(message):
    user_id = message.from_user.id
    lang_data = get_user_lang(user_id)
    support_message = lang_data["support_message_prefix"].format(first_name=message.from_user.first_name, user_id=user_id) + message.text

    admin_markup = types.InlineKeyboardMarkup()
    admin_markup.add(types.InlineKeyboardButton(text=lang_data["support_answer_button"], callback_data=f"answer_support_{user_id}"))
    send_message(ADMIN_USER_ID, support_message, reply_markup=admin_markup)
    send_message(message.chat.id, lang_data["support_message_sent"], reply_markup=main_keyboard(get_user_lang_code(user_id)))
    delete_state(user_id)

@bot.message_handler(func=lambda message: message.text == get_user_lang(message.from_user.id)["profile_button"])
def profile_button_handler(message):
    user_id = message.from_user.id
    lang_data = get_user_lang(user_id)
    user_doc = users_collection.find_one({'_id': user_id})
    file_count = 0
    if user_doc:
        for media_type in ["photo", "video", "music", "document"]:
            if media_type in user_doc:
                file_count += len(user_doc[media_type])
    profile_text = lang_data["profile_message"].format(first_name=message.from_user.first_name, user_id=user_id, file_count=file_count)
    send_message(message.chat.id, profile_text, reply_markup=main_keyboard(get_user_lang_code(user_id)))

@bot.message_handler(func=lambda message: message.text == get_user_lang(message.from_user.id)["get_file_button"])
def get_file_button_handler(message):
    user_id = message.from_user.id
    lang_data = get_user_lang(user_id)
    send_message(message.chat.id, lang_data["get_file_request_message"], reply_markup=back_keyboard(get_user_lang_code(user_id)))
    set_state(user_id, "get_file_by_id")

@bot.message_handler(func=lambda message: get_state(message.from_user.id) == "get_file_by_id")
def get_file_by_id_handler(message):
    user_id = message.from_user.id
    lang_data = get_user_lang(user_id)
    file_id_to_get = message.text

    if not file_id_to_get.isdigit():
        send_message(message.chat.id, lang_data["delete_file_invalid_id"], reply_markup=back_keyboard(get_user_lang_code(user_id)))
        return

    # Query the user's document from MongoDB
    user_doc = users_collection.find_one({'_id': user_id})
    if not user_doc:
        send_message(message.chat.id, lang_data["file_not_found"], reply_markup=main_keyboard(get_user_lang_code(user_id)))
        delete_state(user_id)
        return

    file_found = False
    # Search through all media types for the matching file ID
    for media_type in ["photo", "video", "music", "document"]:
        if media_type in user_doc:
            for file_key, file_data in user_doc[media_type].items():
                if file_key == file_id_to_get:
                    # File found, forward it to the user
                    message_id_in_group = file_data["message_id_in_group"]
                    forward_message(user_id, STORAGE_GROUP_ID, message_id_in_group)
                    file_found = True
                    break
        if file_found:
            break
    
    # Clean up state and notify user
    delete_state(user_id)
    send_message(message.chat.id, lang_data["main_menu_back"], reply_markup=main_keyboard(get_user_lang_code(user_id)))

    if not file_found:
        send_message(message.chat.id, lang_data["file_not_found"])

@bot.message_handler(func=lambda message: message.text == get_user_lang(message.from_user.id)["back_button"])
def back_button_handler(message):
    user_id = message.from_user.id
    lang_data = get_user_lang(user_id)
    delete_state(user_id)
    send_message(message.chat.id, lang_data["main_menu_back"], reply_markup=main_keyboard(get_user_lang_code(user_id)))

# --- Admin Handlers ---
@bot.message_handler(func=lambda message: message.text == get_user_lang(message.from_user.id)["admin_stats_button"] and message.from_user.id == ADMIN_USER_ID)
def admin_stats_handler(message):
    user_id = message.from_user.id
    lang_data = get_user_lang(user_id)
    user_count = users_collection.count_documents({})
    config = admin_collection.find_one({'_id': 'bot_config'}) or {}
    bot_status = config.get("bot_status", lang_data["bot_status_on"])
    stats_text = lang_data["admin_stats_message"].format(user_count=user_count, bot_status=bot_status)
    send_message(message.chat.id, stats_text, reply_markup=admin_keyboard(get_user_lang_code(user_id)))

@bot.message_handler(func=lambda message: message.text == get_user_lang(message.from_user.id)["admin_bot_status_button"] and message.from_user.id == ADMIN_USER_ID)
def admin_bot_status_handler(message):
    user_id = message.from_user.id
    lang_data = get_user_lang(user_id)
    config = admin_collection.find_one({'_id': 'bot_config'}) or {}
    current_status = config.get("bot_status", lang_data["bot_status_on"])
    new_status = lang_data["bot_status_on"] if current_status == lang_data["bot_status_off"] else lang_data["bot_status_off"]
    admin_collection.update_one({'_id': 'bot_config'}, {'$set': {'bot_status': new_status}}, upsert=True)
    send_message(message.chat.id, lang_data["admin_bot_status_changed"].format(bot_status=new_status), reply_markup=admin_keyboard(get_user_lang_code(user_id)))

@bot.message_handler(func=lambda message: message.text == get_user_lang(message.from_user.id)["admin_ban_button"] and message.from_user.id == ADMIN_USER_ID)
def admin_ban_handler(message):
    user_id = message.from_user.id
    lang_data = get_user_lang(user_id)
    send_message(message.chat.id, lang_data["admin_ban_request"], reply_markup=back_keyboard(get_user_lang_code(user_id)))
    set_state(user_id, "ban_user")

@bot.message_handler(func=lambda message: get_state(message.from_user.id) == "ban_user")
def ban_user_message_handler(message):
    user_id = message.from_user.id
    lang_data = get_user_lang(user_id)
    try:
        user_id_to_ban = int(message.text)
        users_collection.update_one({'_id': user_id_to_ban}, {'$set': {'banned': True}}, upsert=True)
        send_message(message.chat.id, lang_data["admin_ban_success"].format(user_id=user_id_to_ban), reply_markup=admin_keyboard(get_user_lang_code(user_id)))
    except ValueError:
        send_message(message.chat.id, lang_data["admin_invalid_user_id"], reply_markup=back_keyboard(get_user_lang_code(user_id)))
    delete_state(user_id)

@bot.message_handler(func=lambda message: message.text == get_user_lang(message.from_user.id)["admin_unban_button"] and message.from_user.id == ADMIN_USER_ID)
def admin_unban_handler(message):
    user_id = message.from_user.id
    lang_data = get_user_lang(user_id)
    send_message(message.chat.id, lang_data["admin_unban_request"], reply_markup=back_keyboard(get_user_lang_code(user_id)))
    set_state(user_id, "unban_user")

@bot.message_handler(func=lambda message: get_state(message.from_user.id) == "unban_user")
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

@bot.message_handler(func=lambda message: message.text == get_user_lang(message.from_user.id)["admin_broadcast_button"] and message.from_user.id == ADMIN_USER_ID)
def admin_broadcast_handler(message):
    user_id = message.from_user.id
    lang_data = get_user_lang(user_id)
    send_message(message.chat.id, lang_data["admin_broadcast_request"], reply_markup=back_keyboard(get_user_lang_code(user_id)))
    set_state(user_id, "broadcast_message")

@bot.message_handler(func=lambda message: get_state(message.from_user.id) == "broadcast_message")
def broadcast_message_handler(message):
    user_id = message.from_user.id
    lang_data = get_user_lang(user_id)
    # Find users who are not banned
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

@bot.message_handler(func=lambda message: message.text == get_user_lang(message.from_user.id)["admin_forward_broadcast_button"] and message.from_user.id == ADMIN_USER_ID)
def admin_forward_broadcast_handler(message):
    user_id = message.from_user.id
    lang_data = get_user_lang(user_id)
    send_message(message.chat.id, lang_data["admin_forward_broadcast_request"], reply_markup=back_keyboard(get_user_lang_code(user_id)))
    set_state(user_id, "forward_broadcast_message")

@bot.message_handler(content_types=['any'], func=lambda message: get_state(message.from_user.id) == "forward_broadcast_message")
def forward_broadcast_message_handler(message):
    user_id = message.from_user.id
    lang_data = get_user_lang(user_id)
    # Find users who are not banned
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
    # The 'languages' folder and its content should still exist for the bot's texts.
    if not os.path.exists("languages"):
        os.makedirs("languages")
        print("Warning: 'languages' directory created. Please add your en.json file.")

    print("Bot starting with MongoDB integration...")
    bot.infinity_polling()
