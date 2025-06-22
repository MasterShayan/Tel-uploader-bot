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
    """Gets the next value from a counter sequence in an atomic way."""
    if counters_collection.find_one({'_id': sequence_name}) is None:
        counters_collection.insert_one({'_id': sequence_name, 'sequence_value': 0})
    sequence_document = counters_collection.find_one_and_update(
        {'_id': sequence_name},
        {'$inc': {'sequence_value': 1}},
        return_document=pymongo.ReturnDocument.AFTER
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
        return bot.send_message(chat_id, text, parse_mode=parse_mode, reply_markup=reply_markup, disable_web_page_preview=True)
    except Exception as e:
        print(f"Error sending message to {chat_id}: {e}")
        return None

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

def send_confirmation_disclaimer(chat_id):
    lang_data = get_user_lang(chat_id)
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

# --- Force Subscription (OWNER ONLY for add/remove/list) ---
@bot.message_handler(commands=['addforcesub'])
def add_forcesub_handler(message):
    if message.from_user.id != OWNER_ID:
        send_message(message.chat.id, "Only the bot owner can use this command."); return
    send_message(message.chat.id, "Please forward a message from the channel you want to add for force subscription.")
    set_state(message.from_user.id, "awaiting_forwardsub")

@bot.message_handler(func=lambda message: get_state(message.from_user.id) == "awaiting_forwardsub" and message.forward_from_chat is not None)
def handle_forwarded_channel_message(message):
    user_id = message.from_user.id
    channel = message.forward_from_chat
    if channel.type not in ['channel', 'supergroup']:
        send_message(user_id, "The forwarded message is not from a channel or supergroup. Please try again.")
        return
    config = admin_collection.find_one({'_id': 'bot_config'}) or {}
    channels = config.get('force_sub_channel', [])
    if isinstance(channels, str):
        channels = [channels]
    channel_info = {'id': channel.id, 'username': channel.username, 'title': channel.title}
    if channel_info not in channels:
        channels.append(channel_info)
        admin_collection.update_one({'_id': 'bot_config'}, {'$set': {'force_sub_channel': channels}}, upsert=True)
        send_message(user_id, f"Channel {channel.title} added to force subscription list.")
    else:
        send_message(user_id, f"Channel {channel.title} is already in the force subscription list.")
    delete_state(user_id)

@bot.message_handler(commands=['removeforcesub'])
def remove_forcesub_handler(message):
    if message.from_user.id != OWNER_ID:
        send_message(message.chat.id, "Only the bot owner can use this command."); return
    args = message.text.split()
    if len(args) < 2:
        send_message(message.chat.id, "Usage: /removeforcesub @channelusername or channel_id"); return
    channel_identifier = args[1]
    config = admin_collection.find_one({'_id': 'bot_config'}) or {}
    channels = config.get("force_sub_channel", [])
    if isinstance(channels, str):
        channels = [channels]
    found = False
    for channel in channels:
        if (isinstance(channel, dict) and (str(channel.get('id')) == channel_identifier or (channel.get('username') and f"@{channel.get('username')}" == channel_identifier))) or channel == channel_identifier:
            channels.remove(channel)
            found = True
            break
    if found:
        admin_collection.update_one({'_id': 'bot_config'}, {'$set': {'force_sub_channel': channels}}, upsert=True)
        send_message(message.chat.id, f"Channel {channel_identifier} removed from force subscription list.")
    else:
        send_message(message.chat.id, f"Channel {channel_identifier} is not in the force subscription list.")

@bot.message_handler(commands=['listforcesub'])
def list_forcesub_handler(message):
    if message.from_user.id != OWNER_ID:
        send_message(message.chat.id, "Only the bot owner can use this command."); return
    config = admin_collection.find_one({'_id': 'bot_config'}) or {}
    channels = config.get("force_sub_channel", [])
    if isinstance(channels, str):
        channels = [channels]
    if channels:
        msg = "Current force subscription channels:\n"
        for channel in channels:
            if isinstance(channel, dict):
                if channel.get('username'):
                    msg += f"@{channel['username']} (ID: {channel['id']}, Title: {channel.get('title','')})\n"
                else:
                    msg += f"ID: {channel['id']} (Title: {channel.get('title','')})\n"
            else:
                msg += f"{channel}\n"
        send_message(message.chat.id, msg)
    else:
        send_message(message.chat.id, "No force subscription channels set.")

def get_channel_invite_link(channel):
    # channel: dict with 'id', 'username', 'title'
    if channel.get('username'):
        return f"https://t.me/{channel['username']}"
    else:
        try:
            # This requires the bot to be admin in the channel with invite rights
            invite = bot.create_chat_invite_link(channel['id'])
            return invite.invite_link
        except Exception as e:
            print(f"Failed to generate invite link for channel {channel['id']}: {e}")
            return None

def force_sub_check(message):
    user_id = message.from_user.id
    config = admin_collection.find_one({'_id': 'bot_config'}) or {}
    channels = config.get("force_sub_channel", [])
    if not channels:
        return True
    if isinstance(channels, str):
        channels = [channels]
    unjoined_channels = []
    for channel in channels:
        channel_id = channel['id'] if isinstance(channel, dict) else None
        channel_username = channel.get('username') if isinstance(channel, dict) else channel
        try:
            if channel_username:
                member = bot.get_chat_member(f"@{channel_username}", user_id)
            elif channel_id:
                member = bot.get_chat_member(channel_id, user_id)
            else:
                continue
            if member.status not in ['member', 'administrator', 'creator']:
                unjoined_channels.append(channel)
        except Exception as e:
            print(f"Error checking channel {channel}: {e}")
            unjoined_channels.append(channel)
    if not unjoined_channels:
        return True
    lang_data = get_user_lang(user_id)
    markup = types.InlineKeyboardMarkup()
    for channel in unjoined_channels:
        invite_link = get_channel_invite_link(channel) if isinstance(channel, dict) else None
        channel_title = channel.get('title') if isinstance(channel, dict) else channel
        if invite_link:
            markup.add(types.InlineKeyboardButton(
                lang_data.get("join_channel_button", f"Join {channel_title}"),
                url=invite_link
            ))
        else:
            markup.add(types.InlineKeyboardButton(
                f"Ask admin for invite to {channel_title}",
                url="https://t.me/YourSupportBotOrAdmin"
            ))
    markup.add(types.InlineKeyboardButton("✅ Verify", callback_data="verify_force_sub"))
    send_message(
        user_id,
        lang_data.get("force_sub_message", "📢 You must join these channel(s) to use the bot:"),
        reply_markup=markup
    )
    return False

@bot.callback_query_handler(func=lambda call: call.data == "verify_force_sub")
def verify_force_sub_callback(call):
    user_id = call.from_user.id
    class DummyMessage:
        def __init__(self, user_id):
            self.from_user = type('User', (), {'id': user_id})
    dummy_message = DummyMessage(user_id)
    if force_sub_check(dummy_message):
        lang_data = get_user_lang(user_id)
        bot.answer_callback_query(call.id, "Verification successful!")
        send_message(user_id, lang_data["start_message"], reply_markup=main_keyboard(get_user_lang_code(user_id)))
    else:
        lang_data = get_user_lang(user_id)
        bot.answer_callback_query(call.id, "You have not joined all required channels.")
        # Resend force sub prompt
        config = admin_collection.find_one({'_id': 'bot_config'}) or {}
        channels = config.get("force_sub_channel", [])
        if not channels:
            return
        if isinstance(channels, str):
            channels = [channels]
        markup = types.InlineKeyboardMarkup()
        for channel in channels:
            invite_link = get_channel_invite_link(channel) if isinstance(channel, dict) else None
            channel_title = channel.get('title') if isinstance(channel, dict) else channel
            if invite_link:
                markup.add(types.InlineKeyboardButton(
                    lang_data.get("join_channel_button", f"Join {channel_title}"),
                    url=invite_link
                ))
            else:
                markup.add(types.InlineKeyboardButton(
                    f"Ask admin for invite to {channel_title}",
                    url="https://t.me/YourSupportBotOrAdmin"
                ))
        markup.add(types.InlineKeyboardButton("✅ Verify", callback_data="verify_force_sub"))
        send_message(user_id, lang_data.get("force_sub_message", "Please join our channel(s) to use the bot."), reply_markup=markup)

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
        send_message(message.chat.id, "❌ This command can only be used by the Bot Owner."); return
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
        'redemption_count': 0, 'redeemed_by': [], 'creator_id': user_id, 'created_at': datetime.utcnow()
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

@bot.message_handler(func=lambda message: message.text == get_user_lang(message.from_user.id)["upload_button"])
def upload_button_handler(message):
    if not force_sub_check(message):
        return
    user_id = message.from_user.id
    lang_data = get_user_lang(user_id)
    send_message(message.chat.id, lang_data["upload_request_message"], reply_markup=back_keyboard(get_user_lang_code(user_id)))
   极 set_state(user_id, "upload")

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
        'token': token, 'created_at': datetime.utcnow()
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
    current_caption = user_d极oc.get('caption', lang_data["default_caption"]) if user_doc else lang_data["default_caption"]
    send_message(message.chat.id, lang_data["caption_request_message"].format(current_caption=current_caption), reply_markup=back_keyboard(get_user_lang_code(user_id)))
    set_state(user_id, "set-caption")

@bot.message_handler(content_types=['text'], func=lambda message: get_state(message.from_user.id) == "极set-caption")
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
    send_message(OWNER_ID, support_message)
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
    if not force_sub_check极(message):
        return
    user_id = message.from_user.id
    lang_data = get_user_lang(user极id)
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

# --- Main ---
if __name__ == "__main__":
    counters_collection.update_one({'_id': 'global_file_id'}, {'$setOnInsert': {'sequence_value': 0}}, upsert=True)
    get_admin_list()
    print("Bot starting with all features enabled...")
    bot.infinity_polling()
