# 🚀 Advanced Telegram File & Post Sharer Bot

[![Python](https://img.shields.io/badge/Python-3.11+-blue?style=for-the-badge&logo=python)](https://www.python.org/)
[![MongoDB](https://img.shields.io/badge/MongoDB-4.7cfc4-green?style=for-the-badge&logo=mongodb)](https://www.mongodb.com/)
[![Telegram](https://img.shields.io/badge/Telegram-2CA5E0?style=for-the-badge&logo=telegram)](https://telegram.org/)
[![License: CC BY-NC-ND 4.0](https://img.shields.io/badge/License-CC%20BY--NC--ND%204.0-lightgrey.svg?style=for-the-badge)](https://creativecommons.org/licenses/by-nc-nd/4.0/)

This is an advanced, feature-rich Telegram bot built with Python and `pyTelegramBotAPI`. It provides robust file, post, and batch sharing, a unique redeem code/giveaway system, dynamic multi-admin controls, and a modern force-subscription system—all powered by a persistent MongoDB database backend for permanent data storage.

This project has been significantly upgraded to be a scalable and professional application suitable for cloud deployment.

## ✨ Key Features

* **Persistent Database**: Uses MongoDB Atlas to ensure no data (users, files, posts, codes) is ever lost on server restarts.
* **Three Ways to Share**:
    * **File Uploads**: Upload any media (video, photo, document, audio) to get a permanent, shareable link.
    * **Forward any Post**: Forward any message or post—with text, media, or buttons—to get a shareable link for it.
    * **Batch Link Creation**: Admins can generate a single link for a sequential range of posts from the storage channel, perfect for sharing multi-part content or entire collections at once.
* **Anonymous & Direct Delivery**: All files and posts are delivered as fresh copies, completely removing the "Forwarded from" tag to protect privacy. Users who click a link get the content directly from the bot.
* **Full-Featured Admin Panel**: Admins get a powerful dashboard with buttons to:
    * 📊 View Bot Statistics (user count, bot status).
    * 🚫 Ban & ✅ Unban users from the bot.
    * 📢 Broadcast text messages to all users.
    * 📤 Forward a message as a broadcast to all users.
    * 🚦 Toggle the bot's status On/Off.
* **Interactive Support System**: Users can send messages to support, and the bot owner receives them with a "Reply" button to answer directly through the bot.
* **Advanced Redeem Code System**:
    * **Single-Use & Limited-Use Codes**: Create codes for prizes (files or text) that can be redeemed a specific number of times.
    * **Code Pools**: Create a single code that gives a different prize from a predefined list to each user who redeems it (perfect for giveaways).
    * **Admin Notifications**: Get real-time alerts when a user redeems a code you created.
* **User-Centric Features**:
    * **Custom Captions**: Set a persistent custom caption that gets automatically applied to all your future file uploads.
    * **File Management**: Users can delete any file or post they have personally shared.
    * **User Profile**: Check your user ID and the total number of files you've uploaded.
* **Owner-Specific Controls**:
    * **Auto-Destruct Timer**: The bot owner can set a timer (in seconds) to automatically delete files/posts after they are delivered to a user.
    * **Dynamic Multi-Admin System**: The owner can promote or demote other admins using simple commands.
* **Force Subscription**: Require users to join one or more channels before they can use the bot. Admins can easily manage the channel list.

## 🤖 Bot Interface

The primary way to interact with the bot is through a clean `ReplyKeyboardMarkup` interface.

### Main Menu Buttons
* **☁️ Upload Media**: Prompts you to send a media file (photo, video, etc.) to generate a share link.
* **➡️ Forward Post**: Prompts you to forward any message to generate a share link for it.
* **🗑️ Delete File**: Asks for a File/Post ID to delete one of your shared items.
* **📂 Get File by ID**: Retrieves a file or post using its unique ID.
* **🎁 Redeem Code**: Starts the process to redeem a prize code.
* **♻️ Caption**: Allows you to set or change your default caption for uploads.
* **Support 🗣️**: Lets you send a message directly to the bot owner.
* **⚙️ Profile**: Shows your user info and file count.

### Bot Commands

While most actions are handled by buttons, several slash commands are available for direct access.

#### For All Users
* `/start`: Starts the bot and shows the main menu. Can also be used with a link to get a file/post.
* `/getfile`: Same as the "Get File by ID" button.
* `/redeem`: Same as the "Redeem Code" button.

#### For Admins Only
* `/batch`: Starts the process to create a shareable link for a range of messages.
* `/createcode`: Starts the process of creating a new redeem code.
* `/createpool`: Starts the process of creating a new code pool for giveaways.
* `/listadmins`: Shows a list of all current bot admins.
* `/panel`: Shows the admin panel with management buttons.

#### For the Bot Owner Only
* `/addadmin <user_id>`: Promotes a user to an admin.
* `/removeadmin <user_id>`: Removes an admin's privileges.
* `/addforcesub <channel_id>`: Add a channel to the force subscription list.
* `/removeforcesub <channel_id>`: Remove a channel from the force subscription list.
* `/listforcesub`: List all force subscription channels.
* `/set_delete_timer`: Set the auto-delete timer for sent files/messages.
* `/check_delete_timer`: Check the current auto-delete timer setting.

---

## ⚙️ Setup and Deployment

You can run this bot on a cloud platform (like Heroku, Render, Railway) or on your own server.

### Prerequisites

* **Telegram Bot Token**: Get this from `@BotFather` on Telegram.
* **Telegram Admin User IDs**: Your numerical Telegram user ID. You can get it from `@userinfobot`. The first ID in the list will be the Bot Owner.
* **Telegram Storage Channel/Group ID**: The ID of a private channel or group where the bot is an admin. This is where all files and posts will be stored.
* **MongoDB Atlas Account**: The free M0 tier is sufficient. Create one at [cloud.mongodb.com](https://cloud.mongodb.com/).
* **MongoDB Connection URI**: The connection string for your database.

### Method 1: Cloud Deployment (Heroku Example)

1.  **Fork the Repository:** Fork this project to your own GitHub account.
2.  **Prepare your Project:**
    * Ensure your `requirements.txt` file is present.
    * Ensure your `Procfile` is present with the line: `worker: python up.V1.py`
3.  **Set Up MongoDB:**
    * On MongoDB Atlas, create a new cluster and a **Database User** with a secure password.
    * In the **Network Access** tab, add `0.0.0.0/0` to your IP access list to allow connections from anywhere.
    * Get your **Connection URI** and replace `<password>` with your database user's password.
4.  **Deploy to Heroku:**
    * Create a new app on Heroku and connect it to your forked GitHub repository.
    * Go to the app's `Settings` -> `Config Vars` and add the following environment variables:

| Key                | Value                                                                   |
| :----------------- | :---------------------------------------------------------------------- |
| `MONGODB_URI`      | Your full MongoDB connection string from Step 3.                        |
| `BOT_TOKEN`        | Your Telegram bot token.                                                |
| `ADMIN_IDS`        | A comma-separated list of admin User IDs. **The first ID is the Owner.** |
| `STORAGE_GROUP_ID` | The ID of your private Telegram storage channel/group.                  |

5.  **Activate the Bot:** In your Heroku app's "Resources" tab, ensure the `worker` dyno is switched ON.
6.  **Set Bot Commands:** In `@BotFather`, use the `/setcommands` command to add the list from the "Bot Commands" section above for easy access in the Telegram UI.

---

## 🤝 Contributing

Contributions, issues, and feature requests are welcome!

1.  Fork the Project
2.  Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3.  Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4.  Push to the Branch (`git push origin feature/AmazingFeature`)
5.  Open a Pull Request

## 🙏 Credits and Acknowledgements

* **Original Bot Concept**: [MasterShayan](https://github.com/MasterShayan)
* **Major Upgrades & Refactoring**: This version was developed with significant architectural upgrades by [@XEX10DERV66](https://github.com/thetechsavage26).

## 📄 License

This project is licensed under the **Attribution-NonCommercial-NoDerivatives 4.0 International (CC BY-NC-ND 4.0)**.

You are free to:
* **Share** — copy and redistribute the material in any medium or format.

Under the following terms:
* **Attribution** — You must give appropriate credit.
* **NonCommercial** — You may not use the material for commercial purposes.
* **NoDerivatives** — If you remix, transform, or build upon the material, you may not distribute the modified material.

For more details, see the [full license](https://creativecommons.org/licenses/by-nc-nd/4.0/).
