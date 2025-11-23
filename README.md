# Advanced Discord Nuke Bot
* Python 3.9+
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
 - [x] Server Customization (Rename & Icon)
 - [x] Role Spam (Mass Create Roles)

# Soon

- [ ] Control/Nuke from console
- [ ] Webpage interface
- [ ] Clone/Backup server
- [ ] Proxies
- [ ] Rate limit bypass

***
# Commands
**Note:** The default command prefix is `.!` but can be customized in `config.json`

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

## Destructive Commands
- `.!nuke` - Delete the current channel and recreate it in the same position with the same permissions (clears all messages)
- `.!nuke-all` - Delete ALL channels, categories, voice channels, and roles (except god role and bot roles)
- `.!death` - Ultimate destruction: Ban all members, delete all channels, and delete all roles
- `.!brainfuck <channel_name> <message>` - Delete all channels then infinitely create new channels and spam messages in them
- `.!spam <count> <message>` - Spam a message in all text channels (use 0 for infinite spam mode)

## Admin Commands
- `.!god` - Create and assign yourself an administrator role named "." with full permissions
- `.!god-all` - Give everyone in the server the god administrator role
- `.!delchannel <#channel>` - Delete a specific channel by mention or ID

## Server Management Commands
- `.!rename-server <new_name>` - Rename the server to a new name
- `.!server-icon <image_url>` - Change the server icon using an image URL

## Nickname Commands
- `.!nick <@user> <nickname>` - Change a specific user's nickname
- `.!nick-all <nickname>` - Set everyone's nickname to the same thing (skips bots and higher roles)

## Role Commands
- `.!role-spam <role_name> <count>` - Mass create roles with a specific name (max 250 at once)

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
  "prefix": ".!"
}
```
- `token`: Your Discord bot token (required)
- `prefix`: Command prefix (default: `.!`) - Change this to customize your command prefix

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
