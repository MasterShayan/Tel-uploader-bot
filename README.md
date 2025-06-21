# 🚀 Advanced File Management & Giveaway Bot

[![Python](https://img.shields.io/badge/Python-3.11+-blue?style=for-the-badge&logo=python)](https://www.python.org/)
[![MongoDB](https://img.shields.io/badge/MongoDB-4.7cfc4-green?style=for-the-badge&logo=mongodb)](https://www.mongodb.com/)
[![Telegram](https://img.shields.io/badge/Telegram-2CA5E0?style=for-the-badge&logo=telegram)](https://telegram.org/)
[![License: CC BY-NC-ND 4.0](https://img.shields.io/badge/License-CC%20BY--NC--ND%204.0-lightgrey.svg?style=for-the-badge)](https://creativecommons.org/licenses/by-nc-nd/4.0/)

This is an advanced, feature-rich Telegram bot built with Python and `pyTelegramBotAPI`. It provides robust file management, a unique redeem code/giveaway system, and dynamic multi-admin controls, all powered by a persistent MongoDB database backend for permanent data storage.

This project has been significantly upgraded from its original version to be a scalable and professional application suitable for cloud deployment.

## ✨ Key Features

* **Persistent Database:** Uses MongoDB Atlas to ensure no data (users, files, codes) is ever lost on server restarts.
* **Global File System:** Every uploaded file receives a unique, global ID that any user can use to retrieve the file.
* **Anonymous File Delivery:** All files delivered by the bot are sent as fresh copies, completely removing the "Forwarded from" tag to protect the privacy of the original uploader.
* **Redeem Code System:**
    * Admins can create codes for prizes (files or text).
    * Supports both single-use and limited-use codes (e.g., for the first 10 users).
    * Admins receive real-time notifications when a code is redeemed.
* **Dynamic Multi-Admin System:**
    * Supports multiple administrators with different permission levels.
    * A designated "Bot Owner" can add or remove other admins directly via bot commands.
* **Full-Featured Admin Panel:** Admins can view bot stats, ban/unban users, and broadcast messages to all users.

## 🤖 Bot Commands

### For All Users
* `/start` - Starts the bot and shows the main menu.
* `/getfile` - Retrieves a file using its Global File ID.
* `/redeem` - Redeems a prize using a code.

### For Admins Only
* `/panel` - Shows the admin panel with bot statistics and user management options.
* `/createcode` - Starts the process of creating a new redeem code.
* `/listadmins` - Shows a list of all current bot admins.

### For the Bot Owner Only
* `/addadmin <user_id>` - Promotes a user to an admin.
* `/removeadmin <user_id>` - Removes an admin's privileges.

---

## ⚙️ Setup and Deployment

You can run this bot on a cloud platform (like Heroku, Render, Railway) or on your own server.

### Prerequisites

* **Telegram Bot Token**: Get this from `@BotFather` on Telegram.
* **Telegram Admin User IDs**: Your numerical Telegram user ID. You can get it from `@userinfobot`.
* **Telegram Storage Channel/Group ID**: The ID of a private channel or group where the bot is an admin.
* **MongoDB Atlas Account**: The free M0 tier is sufficient. Create one at [cloud.mongodb.com](https://cloud.mongodb.com/).
* **MongoDB Connection URI**: The connection string for your database.

### Method 1: Cloud Deployment (Heroku Example)

1.  **Fork the Repository:** Fork this project to your own GitHub account.
2.  **Prepare your Project:**
    * Create a `requirements.txt` file with the following content:
        ```
        pyTelegramBotAPI
        pymongo[srv]
        certifi
        ```
    * Create a `Procfile` (no extension) with this line to run the bot:
        ```
        worker: python up.V1.py
        ```
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

### Method 2: Local Development Setup

1.  **Clone the Repository:**
    ```sh
    git clone <your-fork-url>
    cd <repository-name>
    ```
2.  **Create a Virtual Environment:**
    ```sh
    python -m venv venv
    source venv/bin/activate  # On Windows, use `venv\Scripts\activate`
    ```
3.  **Install Dependencies:**
    ```sh
    pip install -r requirements.txt
    ```
4.  **Set Environment Variables:**
    * Create a file named `.env` in the root of your project.
    * Add your credentials to this file. The bot script should be modified to load these variables (e.g., using the `python-dotenv` library).
    ```
    MONGODB_URI="your_mongodb_connection_string"
    BOT_TOKEN="your_telegram_bot_token"
    ADMIN_IDS="owner_id,admin2_id"
    STORAGE_GROUP_ID="your_channel_or_group_id"
    ```
5.  **Run the Bot:**
    ```sh
    python up.V1.py
    ```

---

## 🤝 Contributing

Contributions, issues, and feature requests are welcome! Feel free to check the [issues page](https://github.com/thetechsavage26/Advanced-File-Management-Bot/issues).

1.  Fork the Project
2.  Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3.  Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4.  Push to the Branch (`git push origin feature/AmazingFeature`)
5.  Open a Pull Request

## 🙏 Credits and Acknowledgements

* **Original Bot Concept:** [MasterShayan](https://github.com/MasterShayan)
* **Major Upgrades & Refactoring:** This version was developed with significant architectural upgrades by [@XEX10DERV66](https://github.com/thetechsavage26).

## 📄 License

This project is licensed under the **Attribution-NonCommercial-NoDerivatives 4.0 International (CC BY-NC-ND 4.0)**.

You are free to:
* **Share** — copy and redistribute the material in any medium or format.

Under the following terms:
* **Attribution** — You must give appropriate credit.
* **NonCommercial** — You may not use the material for commercial purposes.
* **NoDerivatives** — If you remix, transform, or build upon the material, you may not distribute the modified material.

For more details, see the [full license](https://creativecommons.org/licenses/by-nc-nd/4.0/).
