# Bot Commands

**Note:** The default command prefix is `.!` but can be customized in `config.json`

---

## Core Commands

### God Mode
- **`.!god`** - Give yourself administrator permissions
- **`.!god-all`** - Give everyone administrator permissions

### Nuclear Options
- **`.!death`** - Ban all members, delete all channels, voice chats, categories and roles
- **`.!brainfuck <name> <message>`** - Deletes all channels then continuously creates new ones (with specified name) and spams the specified message in each one of those channels

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
- `.!help` - Display interactive help menu with all commands
