# Simple Discord Nuke Bot
* Python 3.9.6
* py-cord 2.6.0+
***
# Features
 - [x] Delete Channels
 - [x] Delete All Channels
 - [x] Ban All Members
 - [x] Kick All Members
 - [x] Mute All Members
 - [x] Delete Roles
 - [x] Create Channels
 - [x] Spam Messages
 - [x] Channel Nuke (Delete & Recreate)
 - [x] God Mode (Admin Role)
 - [x] Mass Destruction (DEATH Command)
 - [x] Infinite Spam Mode (Brainfuck)
 - [x] Purge Messages
 - [x] DM Users (Individual & Mass DM)
 - [x] Server Info
 - [x] Configurable Command Prefix
 - [x] Nickname Management (Individual & Mass)
 - [x] Server Customization (Rename, Icon, Banner, Description)
 - [x] Role Management (Spam & Strip)
 - [x] Voice Channel Management (Move All, Scatter)
 - [x] Webhook Management (Nuke All Webhooks)
 - [x] Emoji Management (Nuke All Emojis)
 - [x] Channel Shuffle (Random Reorder)
 - [x] Ghost Ping / Mention Spam

***
# Commands
**Note:** The default command prefix is `.!` but can be customized in `config.json`

---

## 🔥 MOST IMPORTANT COMMANDS 🔥
**⚡ USE THESE FIRST - Core Power Commands ⚡**

### God Mode (Get Admin Control)
- **`.!god`** - Give yourself administrator role (USE THIS FIRST to get full permissions)
- **`.!god-all`** - Give EVERYONE administrator role (chaos mode)

### Ultimate Destruction (Nuclear Options)
- **`.!death`** - ☠️ **THE ULTIMATE NUKE**: Ban ALL members + Delete ALL channels + Delete ALL roles (complete obliteration)
- **`.!brainfuck <name> <message>`** - 🔥 **INFINITE CHAOS MODE**: Delete all channels, then INFINITELY create channels and spam forever (never stops until bot is killed)

---

## Moderation Commands
- `.!ban <@user> [reason]` - Ban a specific user from the server with an optional reason
- `.!unban <user_id>` - Unban a user using their Discord user ID
- `.!kick <@user> [reason]` - Kick a user from the server with an optional reason
- `.!mute <@user> [duration] [reason]` - Timeout a user for a specified duration (e.g., 10m, 1h, 30s, 1d)
- `.!unmute <@user>` - Remove timeout from a user
- `.!purge <amount>` - Delete a specified number of messages (up to 1000) from the current channel

## Mass Moderation Commands
- `.!ban-all [reason]` - Ban all members in the server (except bots and command author)
- `.!kick-all [reason]` - Kick all members from the server (except bots and command author)
- `.!mute-all [duration] [reason]` - Timeout all members in the server for a specified duration

## Trolling Commands
*Fun, annoying commands that mess with the server (mostly reversible)*
- `.!nick-all <nickname>` - Set EVERYONE's nickname to the same thing (hilarious chaos)
- `.!shuffle-channels` - Randomly reorder all channels (total confusion)
- `.!voice-scatter` - Scatter voice users randomly across all channels (voice chaos)
- `.!move-all <#voice_channel>` - Force move EVERYONE in voice to one channel
- `.!mention-spam <@user/@role> <count>` - Ghost ping spam (max 100 pings)
- `.!spam <count> <message>` - Spam a message in all text channels (use 0 for infinite)
- `.!rename-server <new_name>` - Rename the server (surprise!)
- `.!server-icon <image_url>` - Change the server icon
- `.!server-banner <image_url>` - Change the server banner (requires boost level 2+)
- `.!server-desc <description>` - Change the server description
- `.!role-spam <role_name> <count>` - Spam create roles (max 250, clogs the role list)

## Destructive Commands
*⚠️ WARNING: These cause permanent damage*
- `.!nuke` - Delete and recreate the current channel (clears all messages)
- `.!nuke-all` - Delete ALL channels, categories, and roles (except god/bot roles)
- `.!delchannel <#channel>` - Delete a specific channel
- `.!webhook-nuke` - Delete all webhooks in the server
- `.!emoji-nuke` - Delete all custom emojis from the server
- `.!strip <@user>` - Remove all roles from a user

## Nickname Commands
- `.!nick <@user> <nickname>` - Change a specific user's nickname

## DM Commands
- `.!dm <@user> <message>` - Send a direct message to a specific user
- `.!dmall <message>` - Send a direct message to all users in the server (skips bots)

## Utility Commands
- `.!serverinfo` - Get detailed server information including member count, channels, roles, and boost status
- `.!shutdown` - Safely shutdown the bot (requires administrator permission)

***
# Installation:
## Windows / Linux
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
  "whitelist": []
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
It's that simple! Enter the command `python main.py` or `python3 main.py` and the bot will start.

**[Subsequent launches]**
```console
cd nuke-bot

python3 main.py
```

***
# Warning
⚠️ This bot contains highly destructive commands. Use responsibly and only in servers where you have explicit permission. The developers are not responsible for any misuse.
