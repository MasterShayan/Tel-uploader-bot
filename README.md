# 🚀 Advanced File Management & Giveaway Bot

[![Python](https://img.shields.io/badge/Python-3.11+-blue?style=for-the-badge&logo=python)](https://www.python.org/)
[![MongoDB](https://img.shields.io/badge/MongoDB-4.7cfc4-green?style=for-the-badge&logo=mongodb)](https://www.mongodb.com/)
[![Telegram](https://img.shields.io/badge/Telegram-2CA5E0?style=for-the-badge&logo=telegram)](https://telegram.org/)

This is an advanced, feature-rich Telegram bot built with Python and `pyTelegramBotAPI`. It provides robust file management, a unique redeem code/giveaway system, and dynamic multi-admin controls, all powered by a persistent MongoDB database backend for permanent data storage.

This project has been significantly upgraded from its original version to be a scalable and professional application suitable for cloud deployment.

## ✨ Key Features

* **Persistent Database:** Uses MongoDB Atlas to ensure no data (users, files, codes) is ever lost on server restarts.
* **Global File System:** Every uploaded file receives a unique, global ID that any user can use to retrieve the file.
* **Anonymous File Delivery:** All files delivered by the bot (via links, "Get File by ID", or redemptions) are sent as fresh copies, completely removing the "Forwarded from" tag to protect the privacy of the source channel and users.
* **Redeem Code System:**
    * Admins can create codes for prizes (files or text).
    * Supports both single-use and limited-use codes (e.g., for the first 10 users).
    * Admins receive real-time notifications when a code is redeemed.
* **Dynamic Multi-Admin System:**
    * Supports multiple administrators.
    * A designated "Bot Owner" can add or remove other admins directly via bot commands.
* **Full-Featured Admin Panel:** Admins can view bot stats, ban/unban users, and broadcast messages to all users.

## ⚙️ Deployment Guide

To deploy your own instance of this bot, you will need a few prerequisites. This guide uses a cloud platform like [Heroku](https://www.heroku.com/) as an example.

### Prerequisites

1.  A **Telegram Bot Token** from `@BotFather`.
2.  The **Telegram User IDs** for all your initial admins.
3.  The ID of a private **Telegram Group** where the bot is an admin (this is used for file storage).
4.  A **MongoDB Atlas Account** ([cloud.mongodb.com](https://cloud.mongodb.com/)). The free M0 tier is sufficient.
5.  Your **MongoDB Connection URI** from your Atlas cluster.

### Step-by-Step Setup

1.  **Fork & Clone:** Fork this repository to your own GitHub account.
2.  **Set Up MongoDB:**
    * On MongoDB Atlas, create a free (M0) cluster.
    * Create a **Database User** with a secure password.
    * In **Network Access**, add `0.0.0.0/0` to "Allow Access From Anywhere".
    * Get your **Connection URI** and replace `<password>` with your database user's password.
3.  **Create `requirements.txt`:** Create this file in your repository with the following content:
    ```
    pyTelegramBotAPI
    pymongo[srv]
    certifi
    ```
4.  **Create `Procfile`:** Create a file named `Procfile` (no extension) with this line:
    ```
    worker: python up.V1.py
    ```
5.  **Deploy:**
    * Create a new app on a platform like Heroku and connect it to your GitHub repository.
    * In the app's settings, add the following **Config Vars** (Environment Variables):

| Key | Value |
| :--- | :--- |
| `MONGODB_URI` | Your full MongoDB connection string from Step 2. |
| `BOT_TOKEN` | Your Telegram bot token. |
| `ADMIN_IDS` | A comma-separated list of admin User IDs. The **first ID** is the Bot Owner. |
| `STORAGE_GROUP_ID` | The ID of your private Telegram group. |

6.  **Set Bot Commands:** In `@BotFather`, use `/setcommands` and provide the list from the section below to make the commands easily accessible to users.
7.  **Deploy & Run:** Deploy the branch from your Heroku dashboard. Go to the "Resources" tab and ensure the `worker` dyno is switched ON.

## 🤖 Bot Commands

### For All Users
* `/start` - Starts the bot and shows the main menu.
* `/getfile` - Asks for a Global File ID to retrieve a file.
* `/redeem` - Asks for a code to redeem a prize.

### For Admins Only
* `/panel` - Shows the admin panel with more options.
* `/createcode` - Starts the process of creating a new redeem code.
* `/listadmins` - Shows a list of all current bot admins.

### For the Bot Owner Only
* `/addadmin <user_id>` - Promotes a user to an admin.
* `/removeadmin <user_id>` - Removes an admin's privileges.


## 🙏 Credits and Acknowledgements

* **Original Bot Concept:** [MasterShayan](https://github.com/MasterShayan)
* **Major Upgrades & Refactoring:** This version was developed with significant architectural upgrades by [@XEX10DERV66](https://github.com/thetechsavage26).

## 📄 License

This project is licensed under the [Attribution-NonCommercial-NoDerivatives 4.0 International License](https://creativecommons.org/licenses/by-nc-nd/4.0/).
