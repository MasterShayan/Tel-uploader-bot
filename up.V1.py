import telebot
import json
import os
from telebot import types
import hashlib
import random
import string

# --- Config ---
BOT_TOKEN = "token"  # Bot Token
ADMIN_PASSWORD = "pass"  # Admin Password (should be hashed in practice)
ADMIN_USER_ID = 1111  # Admin User ID
STORAGE_GROUP_ID = -1111  # Group ID for file storage
DEFAULT_LANGUAGE = "en"  # Default Language

bot = telebot.TeleBot(BOT_TOKEN)

# --- Data Files ---
USER_DATA_FILE = "user_data.json"
ADMIN_CONFIG_FILE = "admin_config.json"
LANGUAGES_FOLDER = "languages"

# --- Language Support ---
LANGUAGES = {
    "fa": "فارسی",
    "en": "English"
}

def load_language(lang_code):
    """Load language file or return to default language if error"""
    try:
        with open(os.path.join(LANGUAGES_FOLDER, f"{lang_code}.json"), "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return load_language(DEFAULT_LANGUAGE)

def get_user_lang_code(user_id):
    """Get user language code"""
    user_data = load_user_data()
    return user_data.get(str(user_id), {}).get("language", DEFAULT_LANGUAGE)

def get_user_lang(user_id):
    """Get user language data"""
    lang_code = get_user_lang_code(user_id)
    return load_language(lang_code)

# --- Data Load/Save Functions ---
def load_user_data():
    """Load user data"""
    if os.path.exists(USER_DATA_FILE):
        try:
            with open(USER_DATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_user_data(data):
    """Save user data"""
    try:
        with open(USER_DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"Error saving user data: {e}")

def load_admin_config():
    """Load admin settings"""
    if os.path.exists(ADMIN_CONFIG_FILE):
        try:
            with open(ADMIN_CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            pass
    return {"bot_status": "BOT is On ✅", "admin_password_hash": hashlib.sha256(ADMIN_PASSWORD.encode()).hexdigest()}

def save_admin_config(config):
    """Save admin settings"""
    try:
        with open(ADMIN_CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"Error saving admin config: {e}")

# --- Bot Functions ---
def send_message(chat_id, text, reply_markup=None, parse_mode="HTML"):
    """Send message with error management"""
    try:
        bot.send_message(chat_id, text, parse_mode=parse_mode, reply_markup=reply_markup, disable_web_page_preview=True)
    except Exception as e:
        print(f"Error sending message to {chat_id}: {e}")

def forward_message(chat_id, from_chat_id, message_id):
    """Forward message with error management"""
    try:
        bot.forward_message(chat_id, from_chat_id, message_id)
    except Exception as e:
        print(f"Error forwarding message to {chat_id}: {e}")

# --- State Management ---
user_states = {}

def set_state(user_id, state):
    """Set user state"""
    user_states[user_id] = state

def get_state(user_id):
    """Get user state"""
    return user_states.get(user_id)

def delete_state(user_id):
    """Delete user state"""
    user_states.pop(user_id, None)

# --- Keyboards ---
def main_keyboard(lang_code):
    lang_data = load_language(lang_code)
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton(lang_data["upload_button"]), types.KeyboardButton(lang_data["caption_button"]))
    markup.add(types.KeyboardButton(lang_data["delete_button"]), types.KeyboardButton(lang_data["support_button"]))
    markup.add(types.KeyboardButton(lang_data["profile_button"]))
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

    # Download link check
    if len(message.text.split()) > 1 and message.text.split()[1].startswith('getfile_'):
        try:
            file_info = message.text.split()[1].replace('getfile_', '')
            file_type_prefix, file_code, file_user_id, token = file_info.split('_')
            media_type_map = {"p": "photo", "v": "video", "d": "document", "m": "music"}
            media_type = media_type_map.get(file_type_prefix)

            user_data = load_user_data()
            file_data = user_data.get(file_user_id, {}).get(media_type, {}).get(file_code)
            if file_data and file_data["token"] == token:
                forward_message(message.chat.id, STORAGE_GROUP_ID, file_data["message_id_in_group"])
            else:
                send_message(message.chat.id, lang_data["download_link_error"])
        except Exception as e:
            print(f"Error in getfile: {e}")
            send_message(message.chat.id, lang_data["download_link_error"])
    else:
        send_message(message.chat.id, lang_data["start_message"], reply_markup=language_keyboard())

@bot.callback_query_handler(func=lambda call: call.data.startswith('set_lang_'))
def language_callback_handler(call):
    lang_code = call.data.split('_')[2]
    user_id = call.from_user.id
    user_data = load_user_data()
    if str(user_id) not in user_data:
        user_data[str(user_id)] = {}
    user_data[str(user_id)]["language"] = lang_code
    save_user_data(user_data)

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

    if message.photo:
        media_type, file_id = "photo", message.photo[-1].file_id
    elif message.video:
        media_type, file_id = "video", message.video.file_id
    elif message.document:
        media_type, file_id = "document", message.document.file_id
    elif message.audio:
        media_type, file_id = "music", message.audio.file_id

    if not media_type:
        send_message(message.chat.id, lang_data["upload_invalid_media_type"], reply_markup=main_keyboard(get_user_lang_code(user_id)))
        delete_state(user_id)
        return

    # Send to group and get message_id
    sent_message = bot.copy_message(STORAGE_GROUP_ID, message.chat.id, message.message_id, caption=load_user_data().get(str(user_id), {}).get("caption", lang_data["default_caption"]))
    message_id_in_group = sent_message.message_id

    user_data = load_user_data()
    if str(user_id) not in user_data:
        user_data[str(user_id)] = {"photo": {}, "video": {}, "music": {}, "document": {}}

    file_list = user_data[str(user_id)].get(media_type, {})
    file_key = str(len(file_list) + 1)
    token = ''.join(random.choices(string.ascii_letters + string.digits, k=16))  # Security token
    file_list[file_key] = {"file_id": file_id, "message_id_in_group": message_id_in_group, "token": token}
    user_data[str(user_id)][media_type] = file_list
    save_user_data(user_data)

    download_link = f"https://t.me/{bot.get_me().username}?start=getfile_{media_type[0]}_{file_key}_{user_id}_{token}"
    send_message(message.chat.id, lang_data["upload_success_message"].format(file_id=file_key, download_link=download_link), reply_markup=main_keyboard(get_user_lang_code(user_id)))
    delete_state(user_id)

@bot.message_handler(func=lambda message: message.text == get_user_lang(message.from_user.id)["caption_button"])
def caption_button_handler(message):
    user_id = message.from_user.id
    lang_data = get_user_lang(user_id)
    user_data = load_user_data()
    current_caption = user_data.get(str(user_id), {}).get("caption", lang_data["default_caption"])
    send_message(message.chat.id, lang_data["caption_request_message"].format(current_caption=current_caption), reply_markup=back_keyboard(get_user_lang_code(user_id)))
    set_state(user_id, "set-caption")

@bot.message_handler(func=lambda message: get_state(message.from_user.id) == "set-caption")
def set_caption_handler(message):
    user_id = message.from_user.id
    lang_data = get_user_lang(user_id)
    user_data = load_user_data()
    if str(user_id) not in user_data:
        user_data[str(user_id)] = {}
    user_data[str(user_id)]["caption"] = message.text
    save_user_data(user_data)
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

    user_data = load_user_data()
    if str(user_id) not in user_data:
        send_message(message.chat.id, lang_data["file_not_found"], reply_markup=main_keyboard(get_user_lang_code(user_id)))
        delete_state(user_id)
        return

    deleted = False
    for media_type in ["photo", "video", "music", "document"]:
        if file_id_to_delete in user_data[str(user_id)].get(media_type, {}):
            del user_data[str(user_id)][media_type][file_id_to_delete]
            deleted = True
            break

    if deleted:
        save_user_data(user_data)
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
    user_data = load_user_data()
    file_count = sum(len(user_data.get(str(user_id), {}).get(t, {})) for t in ["photo", "video", "music", "document"])
    profile_text = lang_data["profile_message"].format(first_name=message.from_user.first_name, user_id=user_id, file_count=file_count)
    send_message(message.chat.id, profile_text, reply_markup=main_keyboard(get_user_lang_code(user_id)))

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
    user_data = load_user_data()
    config = load_admin_config()
    stats_text = lang_data["admin_stats_message"].format(user_count=len(user_data), bot_status=config.get("bot_status", "unknown")) # "نامشخص" was translated to "unknown"
    send_message(message.chat.id, stats_text, reply_markup=admin_keyboard(get_user_lang_code(user_id)))

@bot.message_handler(func=lambda message: message.text == get_user_lang(message.from_user.id)["admin_bot_status_button"] and message.from_user.id == ADMIN_USER_ID)
def admin_bot_status_handler(message):
    user_id = message.from_user.id
    lang_data = get_user_lang(user_id)
    config = load_admin_config()
    new_status = lang_data["bot_status_on"] if config.get("bot_status") == lang_data["bot_status_off"] else lang_data["bot_status_off"]
    config["bot_status"] = new_status
    save_admin_config(config)
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
        user_data = load_user_data()
        if str(user_id_to_ban) not in user_data:
            user_data[str(user_id_to_ban)] = {}
        user_data[str(user_id_to_ban)]["banned"] = True
        save_user_data(user_data)
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
        user_data = load_user_data()
        if str(user_id_to_unban) in user_data and "banned" in user_data[str(user_id_to_unban)]:
            del user_data[str(user_id_to_unban)]["banned"]
            save_user_data(user_data)
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
    user_data = load_user_data()
    success_count, fail_count = 0, 0

    for uid in user_data:
        try:
            send_message(uid, message.text)
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
    user_data = load_user_data()
    success_count, fail_count = 0, 0

    for uid in user_data:
        try:
            forward_message(uid, message.chat.id, message.message_id)
            success_count += 1
        except:
            fail_count += 1

    send_message(message.chat.id, lang_data["admin_forward_broadcast_report"].format(success_count=success_count, fail_count=fail_count), reply_markup=admin_keyboard(get_user_lang_code(user_id)))
    delete_state(user_id)

# --- Main ---
if __name__ == "__main__":
    if not os.path.exists(LANGUAGES_FOLDER):
        os.makedirs(LANGUAGES_FOLDER)
    for lang_code in LANGUAGES:
        lang_file = os.path.join(LANGUAGES_FOLDER, f"{lang_code}.json")
        if not os.path.exists(lang_file):
            with open(lang_file, "w", encoding="utf-8") as f:
                json.dump({}, f, indent=4, ensure_ascii=False)  # Empty file for languages
    print("Bot started...")
    bot.infinity_polling()
