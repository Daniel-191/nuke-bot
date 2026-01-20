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
# Installation

## Windows

### Easy Method: (Windows)
1. Clone the repository:
```console
git clone https://github.com/Daniel-191/nuke-bot
cd nuke-bot
```
2. Run the installer:
   - Double-click **`install.bat`** to install dependencies

3. Configure `config.json` with your bot token and user ID
4. Run **`run.bat`** to start the bot

### Manual Method: (Windows)
```console
git clone https://github.com/Daniel-191/nuke-bot
cd nuke-bot
pip install -r requirements.txt
python main.py
```

## Linux / Mac

```console
git clone https://github.com/Daniel-191/nuke-bot
cd nuke-bot
pip install -r requirements.txt
python3 main.py
```

## Android (Termux)

```console
apt update && apt upgrade
pkg install python git
git clone https://github.com/Daniel-191/nuke-bot
cd nuke-bot
pip install -r requirements.txt
python3 main.py
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

***
> [!WARNING]  
> ⚠️ This bot contains highly destructive commands. Use responsibly and only in servers where you have explicit permission. The developers are not responsible for any misuse.
