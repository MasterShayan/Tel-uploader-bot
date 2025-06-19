# 🚀 Telegram Uploader Bot - (MongoDB Edition)

> **Note:** This is a heavily modified fork of the original [Tel-uploader-bot by MasterShayan](https://github.com/MasterShayan/Tel-uploader-bot). This version has been significantly upgraded to use a professional and persistent database backend instead of temporary JSON files.

This version introduces several key improvements:
- **MongoDB Integration:** All user data and file information is stored in a permanent MongoDB Atlas database, preventing data loss on server restarts.
- **Environment Variables:** Configuration (like bot tokens and IDs) is handled securely through environment variables, not hardcoded in the script.
- **Deployment-Ready:** Includes the necessary files (`Procfile`, `requirements.txt`) and instructions for deploying on cloud platforms like Heroku.

## ✨ Key Features

  * **Persistent Storage:** Thanks to MongoDB, the bot remembers all users and files permanently.
  * **Easy Upload:** Simply send your files to the bot to upload.
  * **Multi-Media Support:** Upload photos, videos, documents, and audio files.
  * **Direct Telegram Links:** Get a unique, shareable link that forwards the file to other users within Telegram.
  * **File Management:** Set a custom caption for your files and delete them by ID.
  * **Admin Panel:** Includes features for bot statistics, user management (ban/unban), and broadcasting messages.

## ⚙️ Deployment Guide

To deploy your own instance of this bot, you will need a few prerequisites and to follow these steps. This guide uses [Heroku](https://www.heroku.com/) as an example platform.

### Prerequisites

1.  A **Telegram Bot Token** from `@BotFather`.
2.  Your personal **Telegram User ID** (from `@userinfobot`).
3.  The ID of a private **Telegram Group** where the bot is an admin (for file storage).
4.  A **MongoDB Atlas Account** ([cloud.mongodb.com](https://cloud.mongodb.com/)). You can use the free M0 tier.
5.  Your **MongoDB Connection URI** from your Atlas cluster.

### Step-by-Step Setup

1.  **Fork and Clone the Repository**
    - Fork this repository to your own GitHub account.
    - Clone it to your local machine.

2.  **Set Up MongoDB Atlas**
    - Create a free (M0) cluster on MongoDB Atlas.
    - In your cluster settings, go to **Database Access** and create a database user with a secure password.
    - Go to **Network Access** and add an entry for `0.0.0.0/0` (Allow Access From Anywhere). This is necessary for cloud platforms like Heroku to connect.
    - Go to **Database**, click "Connect" on your cluster, select "Connect your application", and copy your **Connection URI**. Be sure to replace `<password>` with the actual password you just created.

3.  **Create `requirements.txt`**
    - Create a file named `requirements.txt` in your project's root directory.
    - Add the following lines to it:
      ```
      pyTelegramBotAPI
      pymongo[srv]
      certifi
      ```

4.  **Create `Procfile`**
    - Create a file named `Procfile` (with a capital 'P' and no extension).
    - Add the following line to it. This tells Heroku how to run the bot.
      ```
      worker: python up.V1.py
      ```

5.  **Deploy to Heroku**
    - Create a new app on Heroku.
    - In the "Deploy" tab of your Heroku app, connect it to your GitHub fork.
    * In the "Settings" tab, go to "Config Vars" and add the following variables:

| Key | Value |
| :--- | :--- |
| `MONGODB_URI` | Your full MongoDB connection string from Step 2. |
| `BOT_TOKEN` | Your Telegram bot token. |
| `ADMIN_USER_ID` | Your personal Telegram user ID. |
| `STORAGE_GROUP_ID` | The ID of your private Telegram group. |
| `ADMIN_PASSWORD` | Any password (this feature is not fully implemented). |

    - Go back to the "Deploy" tab and click **"Deploy Branch"**.
    - Finally, go to the **"Resources"** tab and make sure the `worker` dyno is switched ON.

## 🙏 Credits and Acknowledgements

* **Original Concept & Base Code:** [MasterShayan](https://github.com/MasterShayan)
* **MongoDB Integration & Deployment Refactoring:** [@XEX10DERV66](https://github.com/thetechsavage26)

## 📄 License

This project is licensed under the [Attribution-NonCommercial-NoDerivatives 4.0 International License](https://creativecommons.org/licenses/by-nc-nd/4.0/).
