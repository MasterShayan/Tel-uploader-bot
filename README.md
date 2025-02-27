# 🚀 Telegram Uploader Bot - (Version 1)

[![License: Attribution-NonCommercial-NoDerivatives 4.0 International](about:sanitized)](https://www.google.com/url?sa=E&source=gmail&q=https://creativecommons.org/licenses/by-nc-nd/4.0/)

**Welcome to the Telegram Uploader Bot\!** 🤖

This Telegram bot allows you to easily upload your files (photos, videos, documents, audio) and receive a direct download link. Developed in Python using the `Telebot` library, this source code is ideal for personal and non-commercial use.

**Key Feature:** This bot utilizes group storage, meaning it **doesn't consume any volume on your personal device or bot server**\! All uploaded files are stored in a designated Telegram group.

## ✨ Key Features

  * **Easy Upload:** Simply send your files to the bot to upload.
  * **Multi-Media Support:** Upload photos, videos, documents, and audio files.
  * **Direct Download Link:** Get a unique, direct download link after successful upload.
  * **File Deletion:** Easily delete uploaded files using their File ID.
  * **Caption Setting:** Set a custom caption for your uploaded files.
  * **Multi-Language Support:**  The bot supports Persian and English by default, with easy addition of new languages.
  * **Admin Panel:** Management features to control the bot (statistics, bot status, ban/unban users, broadcast messages, etc.) (Some features are limited in Version 1).
  * **Security:** Secure download links using security tokens.

## ⚙️ How to Use

1.  Start the bot by sending the `/start` command.
2.  Choose your preferred language from the initial menu.
3.  From the main menu, select the "☁️ Upload Media ☁️" button.
4.  Send the file (photo, video, document, or audio) you wish to upload to the bot.
5.  After successful upload, the bot will send you a message containing the File ID and a direct download link.

### Other Main Menu Buttons

  * **♻️ Caption:** Set or change the default caption for uploaded files.
  * **🗑 Delete File:** Delete uploaded files using their File ID.
  * **🗣 Support:** Send a message to the bot support (admin).
  * **⚙️ Profile:** View your user profile, including name, user ID, and the number of uploaded files.

## 🔑 Admin Panel

To access the admin panel, send the command `/panel` to the bot. (Accessible only to the admin user ID specified in the source code.)

### Admin Panel Features (Version 1 - Limited)

  * **📊 Bot Stats:** View overall bot statistics, including user count and bot status (On/Off).
  * **🚦 Turn On/Off Bot:** Change the bot status to On or Off.
  * **🚫 Ban User:** Ban a user using their numerical User ID.
  * **✅ Unban User:** Unban a banned user using their numerical User ID.
  * **📢 Broadcast Message:** Send a text message to all bot users.
  * **📤 Forward Broadcast:** Forward a message from the admin to all bot users.
  * **⚙️ More Settings:** (Inactive in Version 1 - will be active in Version 2) - This button is inactive in Version 1. Version 2 will include more bot settings options here.

## 🌍 Multi-Language Support

The bot supports English and Persian languages by default. To add new languages or edit existing texts, follow these steps:

1.  **`languages` Folder:** In the project root, there is a folder named `languages`.
2.  **Language Files:** This folder contains `fa.json` (Persian) and `en.json` (English) files. Each `json` file contains the bot's texts for a specific language.
3.  **Adding a New Language:**
      * Create a new `json` file in the `languages` folder with the language code as the filename (e.g., `es.json` for Spanish).
      * Copy the content of either `fa.json` or `en.json` into the new file.
      * Translate the copied texts into the new language.
      * Add the new language code and its name to the `LANGUAGES` dictionary in the main source file (`uploader_bot.py`).

### Example Persian Language Configuration File (`fa.json`)

```json
{
    "start_message": "👋 سلام! به ربات آپلودر خوش آمدید.\n\n📥 رسانه خود را آپلود کنید تا لینک دانلود دریافت کنید.",
    "upload_button": "☁️ آپلود رسانه ☁️",
    "caption_button": "♻️ کپشن",
    "delete_button": "🗑 حذف فایل",
    "support_button": "پشتیبانی 🗣",
    "profile_button": "⚙️ حساب کاربری",
    "back_button": "منوی قبل",
    "main_menu_back": "به منوی اصلی بازگشتید.",
    "upload_request_message": "لطفا رسانه خود را ارسال کنید:",
    "upload_invalid_media_type": "فقط عکس، ویدیو، سند و صدا قابل آپلود هستند.",
    "upload_success_message": "✅ فایل شما با موفقیت آپلود شد!\n\n🏷️ آیدی فایل: {file_id}\n🔗 لینک دانلود:\n{download_link}",
    "caption_request_message": "📝 لطفا کپشن مورد نظر خود را ارسال کنید:\n\nکپشن فعلی: {current_caption}\n(برای حذف کپشن، یک پیام خالی ارسال کنید)",
    "caption_saved_message": "✅ کپشن با موفقیت ذخیره شد!",
    "delete_file_request_message": "🆔 لطفا آیدی فایل مورد نظر برای حذف را ارسال کنید:",
    "delete_file_invalid_id": "❌ آیدی فایل نامعتبر است. لطفا یک عدد ارسال کنید.",
    "delete_file_success": "✅ فایل با آیدی {file_id} با موفقیت حذف شد!",
    "file_not_found": "❌ فایل با این آیدی یافت نشد.",
    "support_message_request": "💬 پیام خود را ارسال کنید تا به پشتیبانی ارسال شود:",
    "support_message_sent": "✅ پیام شما با موفقیت به پشتیبانی ارسال شد!",
    "support_message_prefix": "✉️ پیام جدید از کاربر:\n\n👤 نام: {first_name}\n🆔 آیدی: {user_id}\n\n",
    "support_answer_button": "پاسخ به کاربر",
    "support_answer_request": "💬 پاسخ خود را به کاربر با آیدی {user_id} ارسال کنید:",
    "support_answer_sent_admin": "✅ پاسخ شما به کاربر ارسال شد.",
    "support_answer_admin_prefix": "✉️ پاسخ پشتیبانی:\n\n",
    "profile_message": "👤 پروفایل کاربری شما:\n\n🏷️ نام: {first_name}\n🆔 آیدی: {user_id}\n🗂️ تعداد فایل‌های آپلود شده: {file_count}",
    "download_link_error": "❌ لینک دانلود نامعتبر است.",
    "default_caption": "بدون کپشن",
    "language_set_message": "✅ زبان ربات به {language} تغییر یافت.",
    "language_changed_alert": "زبان تغییر کرد!",
    "admin_panel_welcome": "👋 خوش آمدید به پنل مدیریت!",
    "admin_panel_access_denied": "❌ دسترسی به پنل مدیریت مجاز نیست.",
    "admin_stats_button": "📊 آمار ربات",
    "admin_bot_status_button": "🚦 روشن/خاموش کردن ربات",
    "admin_ban_button": "🚫 مسدود کردن کاربر",
    "admin_unban_button": "✅ رفع مسدودیت کاربر",
    "admin_broadcast_button": "📢 ارسال پیام همگانی",
    "admin_forward_broadcast_button": "📤 فروارد همگانی",
    "admin_settings_button": "⚙️ تنظیمات بیشتر",
    "admin_more_settings_message": "⚙️ تنظیمات بیشتر را انتخاب کنید:",
    "admin_channel_settings_button": "کانال‌ها",
    "admin_button_name_settings_button": "نام دکمه‌ها",
    "admin_text_settings_button": "متن‌های ربات",
    "admin_bot_id_settings_button": "آیدی ربات",
    "admin_stats_message": "📊 آمار ربات:\n\n👥 تعداد کاربران: {user_count}\n🚦 وضعیت ربات: {bot_status}",
    "bot_status_on": "روشن است ✅",
    "bot_status_off": "خاموش است ⛔",
    "admin_bot_status_changed": "🚦 وضعیت ربات به '{bot_status}' تغییر یافت.",
    "admin_ban_request": "🆔 آیدی عددی کاربر برای مسدود کردن را وارد کنید:",
    "admin_ban_success": "🚫 کاربر با آیدی {user_id} مسدود شد.",
    "admin_invalid_user_id": "❌ آیدی کاربر نامعتبر است.",
    "admin_unban_request": "🆔 آیدی عددی کاربر برای رفع مسدودیت را وارد کنید:",
    "admin_unban_success": "✅ کاربر با آیدی {user_id} رفع مسدودیت شد.",
    "admin_user_not_banned": "✅ کاربر مسدود نیست.",
    "admin_broadcast_request": "📢 پیام همگانی خود را ارسال کنید:",
    "admin_broadcast_report": "📢 گزارش ارسال همگانی:\n\n✅ موفق: {success_count}\n❌ ناموفق: {fail_count}",
    "admin_forward_broadcast_request": "📤 پیام خود را برای فروارد همگانی ارسال کنید:",
    "admin_forward_broadcast_report": "📤 گزارش فروارد همگانی:\n\n✅ موفق: {success_count}\n❌ ناموفق: {fail_count}"
}
```

## ❤️ Support the Developer

If you are using this source code and find it helpful, please consider supporting the developer through the following ways:

  * **Star the Repository:** Help the project gain visibility by starring this repository on [GitHub](https://github.com/MasterShayan/Tel-uploader-bot).
  * **Suggestions and Issue Reporting:** Contribute to the source code improvement by providing suggestions and reporting issues.
  * **Share the Project:** Share this project with your friends and other developers.

## 📄 License

This project is licensed under the [Attribution-NonCommercial-NoDerivatives 4.0 International License](https://www.google.com/url?sa=E&source=gmail&q=https://creativecommons.org/licenses/by-nc-nd/4.0/).

**You are free to:**

  * **Share:** Copy and redistribute the material in any medium or format.

**Under the following terms:**

  * **Attribution:** You must give appropriate credit, provide a link to the license, and indicate if changes were made. You may do so in any reasonable manner, but not in any way that suggests the licensor endorses you or your use.
  * **NonCommercial:** You may not use the material for commercial purposes.
  * **NoDerivatives:** If you remix, transform, or build upon the material, you may not distribute the modified material.

## ⚠️ Version 1 - Limitations & Version 2 Roadmap

**Please Note:** This source code is currently **Version 1**, and some sections may not be fully implemented. Specifically, the "⚙️ More Settings" button in the admin panel is inactive in this version.

**Version 2 will fully implement and debug the following features:**

  * Activation and completion of the "⚙️ More Settings" section in the admin panel, including features such as:
      * Setting up support channels
      * Changing bot button names
      * Editing bot texts
      * Changing the bot ID
  * Performance improvements and bug fixes for reported issues.
  * Adding new features based on user feedback.

**Follow the repository to receive the latest version and news about Version 2.**

## 🔗 Repository Link

[https://github.com/MasterShayan/Tel-uploader-bot](https://github.com/MasterShayan/Tel-uploader-bot)

**Thank you for your support\!** 🙏

```
```
