# Advanced Discord Nuke Bot
* Python 3.10+
* py-cord 2.6.0+
***
# Features

## Bot Commands
 - [x] Delete Channels
 - [x] Delete All Channels
 - [x] Ban All Members
 - [x] Kick All Members
 - [x] Mute All Members
 - [x] Delete All Roles
 - [x] Create Channels
 - [x] Spam Messages
 - [x] Channel Nuking
 - [x] Give all admin
 - [x] Give self admin
 - [x] DM Users (Individual & Mass DM)
 - [x] Nickname Management (Individual & Mass)
 - [x] Server Customization (Rename, Icon, Banner, Description)
 - [x] Role Management (Spam create & Strip roles)
 - [x] Users in Voice channels control (Move All, Scatter)
 - [x] Webhook Management (Nuke All Webhooks)
 - [x] Emoji Management (Nuke All Emojis)
 - [x] Channel Shuffle (Random Reorder)
 - [x] Ghost Ping / Mention Spam

## Soon

- [x] Multi Lang support
- [ ] Control/Nuke from console
- [ ] Webpage interface
- [ ] Clone/Backup server
- [ ] Proxies

***
# Commands
**[View all commands and usage →](COMMANDS.md)**

For a complete list of all available commands with detailed descriptions and usage examples, see **[COMMANDS.md](COMMANDS.md)**

***
# Installation:
## Windows (Easy Method)
**Using Batch Files:**
1. Clone the repository:
```console
git clone https://github.com/Daniel-191/nuke-bot
cd nuke-bot
```
2. Run the installer:
   - Double-click **`install.bat`** to install dependencies
   - OR double-click **`start.bat`** for automatic install + run

3. Configure `config.json` with your bot token and user ID
4. Run **`run.bat`** to start the bot

## Windows / Linux (Manual Method)
```console
git clone https://github.com/Daniel-191/nuke-bot
cd nuke-bot
python -m pip install -r requirements.txt
```

## Android (Termux):
```console
apt update && apt upgrade
pkg install python git
git clone https://github.com/Daniel-191/nuke-bot
cd nuke-bot
python -m pip install -r requirements.txt
```

***
# Configuration
Edit `config.json` and configure your bot settings:
```json
{
  "token": "BOT_TOKEN",
  "prefix": ".!",
  "owner_id": "YOUR_USER_ID_HERE",
  "whitelist": [],
  "language": "en"
}
```

## Configuration Options:
- **`token`** (required): Your Discord bot token
- **`prefix`** (optional, default: `.!`): Command prefix - Change this to customize your command prefix
- **`owner_id`** (required): Your Discord user ID - The bot owner who has full access to all commands
- **`whitelist`** (optional, default: `[]`): Array of user IDs who are authorized to use the bot
  - Example: `"whitelist": [123456789012345678, 987654321098765432]`
  - Only the owner and whitelisted users can use bot commands
  - Leave empty `[]` to only allow the owner
- **`language`** (optional, default: `"en"`): Bot language for messages and responses
  - Available languages:
    - `"en"` - English
    - `"es"` - Spanish (Español)
    - `"fr"` - French (Français)
    - `"de"` - German (Deutsch)
    - `"pt"` - Portuguese (Português)
    - `"it"` - Italian (Italiana)
    - `"ru"` - Russian (Русский)
    - `"pl"` - Polish (Polski)
    - `"nl"` - Dutch (Nederlands)
    - `"uk"` - Ukrainian (Українська)
    - `"sv"` - Swedish (Svenska)
    - `"el"` - Greek (Ελληνικά)
  - The bot will use the specified language for all messages, embeds, and responses
  - If language file is not found, it will fallback to English

## 🔐 Security & Authorization
**IMPORTANT:** All bot commands are restricted to authorized users only!
- Only the **bot owner** (specified in `owner_id`) can use commands by default
- Additional users can be whitelisted by adding their Discord user IDs to the `whitelist` array
- Unauthorized users will receive an error message if they try to use any command
- Get your Discord user ID: Enable Developer Mode in Discord settings, then right-click your username and select "Copy ID"

## Getting a Bot Token
1. Go to https://discord.com/developers/applications
2. Create a new application
3. Go to the "Bot" section and create a bot
4. Copy the token and replace `BOT_TOKEN` in `config.json`
5. Enable these intents in Bot settings:
   - Message Content Intent
   - Server Members Intent
6. Invite bot with Administrator permissions

***
# Running

## Windows:
- **Easy:** Double-click `run.bat`
- **Manual:** `python main.py`

## Linux/Mac:
```console
python3 main.py
```

**[Subsequent launches]**
```console
cd nuke-bot

# Windows: run.bat
# Linux/Mac: python3 main.py
```

***
> [!WARNING]  
> ⚠️ This bot contains highly destructive commands. Use responsibly and only in servers where you have explicit permission. The developers are not responsible for any misuse.
