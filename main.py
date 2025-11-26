

import discord
from discord.ext import commands
import os
import json
import asyncio
from datetime import timedelta, datetime
from colorama import Fore, Back, Style, init
import logging


init(autoreset=True)


# Setup logging
def setup_logging():
    """Setup logging to file and console"""
    # Create logs directory if it doesn't exist
    if not os.path.exists('logs'):
        os.makedirs('logs')

    # Create log filename with current date
    log_filename = f'logs/bot_{datetime.now().strftime("%Y-%m-%d")}.log'

    # Create logger
    logger = logging.getLogger('NukeBot')
    logger.setLevel(logging.INFO)

    # Create file handler with user-friendly formatting
    file_handler = logging.FileHandler(log_filename, encoding='utf-8')
    file_handler.setLevel(logging.INFO)

    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s | %(levelname)-8s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(formatter)

    # Add handler to logger
    logger.addHandler(file_handler)

    return logger

# Initialize logger
logger = setup_logging()

# Translation system
translations = {}

def load_translations(language="en"): # default to english
    """Load translation file based on language setting"""
    global translations
    lang_file = f'lang/{language}.json'

    try:
        if os.path.exists(lang_file):
            with open(lang_file, 'r', encoding='utf-8') as f:
                translations = json.load(f)
            if 'logger' in globals():  # Only log if logger exists
                logger.info(f"Loaded language: {language}")
        else:
            # Fallback to English if language file not found
            if 'logger' in globals():
                logger.warning(f"Language file '{lang_file}' not found, falling back to English")
            with open('lang/en.json', 'r', encoding='utf-8') as f:
                translations = json.load(f)
    except Exception as e:
        if 'logger' in globals():
            logger.error(f"Error loading translations: {e}")
        translations = {}

def t(key, **kwargs):
    """Get translated string and replace placeholders"""
    text = translations.get(key, key)
    if kwargs:
        try:
            text = text.format(**kwargs)
        except KeyError as e:
            if 'logger' in globals():
                logger.error(f"Missing translation placeholder: {e} in key '{key}'")
    return text

# Load English translations first (default, before config)
load_translations("en")

# Load configuration
def load_config():
    try:
        with open('config.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f'{Fore.RED}{t("config_not_found")}{Style.RESET_ALL}')
        print(t("config_create_instruction"))
        print(t("config_example"))
        exit(1)
    except json.JSONDecodeError:
        print(f'{Fore.RED}{t("config_invalid_json")}{Style.RESET_ALL}')
        exit(1)

config = load_config()

# Reload translations based on config language
load_translations(config.get("language", "en"))

# Create bot instance with prefix commands
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix=config.get("prefix", ".!"), intents=intents, help_command=None)

@bot.event
async def on_ready():
    print("""
███╗░░██╗██╗░░░██╗██╗░░██╗███████╗  ██████╗░░█████╗░████████╗
████╗░██║██║░░░██║██║░██╔╝██╔════╝  ██╔══██╗██╔══██╗╚══██╔══╝
██╔██╗██║██║░░░██║█████═╝░█████╗░░  ██████╦╝██║░░██║░░░██║░░░
██║╚████║██║░░░██║██╔═██╗░██╔══╝░░  ██╔══██╗██║░░██║░░░██║░░░
██║░╚███║╚██████╔╝██║░╚██╗███████╗  ██████╦╝╚█████╔╝░░░██║░░░
╚═╝░░╚══╝░╚═════╝░╚═╝░░╚═╝╚══════╝  ╚═════╝░░╚════╝░░░░╚═╝░░░
\n\n""")

    print(f'{Fore.GREEN}{t("ready_online", bot_user=bot.user)}')
    print(f'{Fore.GREEN}{t("ready_bot_id", bot_id=bot.user.id)}{Style.RESET_ALL}')

    # Log bot startup
    guild_list = ', '.join([f"{guild.name} (ID: {guild.id})" for guild in bot.guilds])
    logger.info(t("bot_started", bot_user=bot.user, bot_id=bot.user.id, guild_count=len(bot.guilds), guild_list=guild_list))
    logger.info(t("bot_prefix", prefix=config.get('prefix', '.!'), owner_id=config.get('owner_id', 'Not set')))

@bot.event
async def on_command(ctx):
    """Log all command executions"""
    # Get command arguments if any
    args = ctx.message.content.split()[1:] if len(ctx.message.content.split()) > 1 else []
    args_str = ' '.join(args) if args else '(no args)'

    # Log the command execution
    logger.info(t("command_executed", user=ctx.author, user_id=ctx.author.id, command=ctx.command.name, args=args_str, guild=ctx.guild.name, guild_id=ctx.guild.id, channel=ctx.channel.name))

@bot.event
async def on_command_error(ctx, error):
    """Log command errors"""
    # Don't log CheckFailure errors (these are from is_authorized failures, already logged)
    if isinstance(error, commands.CheckFailure):
        return

    # Log other errors
    logger.error(t("command_error", user=ctx.author, user_id=ctx.author.id, command=ctx.command.name if ctx.command else 'Unknown', guild=ctx.guild.name if ctx.guild else 'DM', error=str(error)))

@bot.event
async def on_guild_join(guild):
    """Log when bot joins a new guild"""
    logger.info(t("bot_joined_guild", guild=guild.name, guild_id=guild.id, member_count=guild.member_count, owner=guild.owner, owner_id=guild.owner.id))

@bot.event
async def on_guild_remove(guild):
    """Log when bot leaves/is removed from a guild"""
    logger.info(t("bot_left_guild", guild=guild.name, guild_id=guild.id))

# Authorization check function
def is_authorized():
    """Check if user is bot owner or in whitelist"""
    async def predicate(ctx):
        owner_id = config.get("owner_id")
        whitelist = config.get("whitelist", [])

        # Convert owner_id to int if it's a string
        if owner_id and isinstance(owner_id, str) and owner_id.isdigit():
            owner_id = int(owner_id)

        # Check if user is owner or in whitelist
        if ctx.author.id == owner_id or ctx.author.id in whitelist:
            return True

        # User is not authorized
        print(f'{Fore.RED}[UNAUTHORIZED] {Fore.WHITE}{ctx.author.display_name} (ID: {ctx.author.id}) attempted to use {ctx.command.name} in {ctx.guild.name}{Style.RESET_ALL}')
        logger.warning(t("unauthorized", user=ctx.author, user_id=ctx.author.id, command=ctx.command.name, guild=ctx.guild.name, guild_id=ctx.guild.id))

        # Delete command message
        try:
            await ctx.message.delete()
        except:
            pass

        # Send unauthorized message
        try:
            embed = discord.Embed(
                description=t("unauthorized_message"),
                color=discord.Color.red()
            )
            await ctx.send(embed=embed, delete_after=5)
        except:
            pass

        return False

    return commands.check(predicate)

async def send_dm(ctx, content=None, embed=None):
    """Helper function to delete command, send ephemeral-style message, and DM"""
    # Delete the original command message
    try:
        await ctx.message.delete()
    except:
        pass

    # Send ephemeral-style message in channel (auto-deletes after 3 seconds)
    try:
        if embed:
            await ctx.send(embed=embed, delete_after=3)
        else:
            await ctx.send(content, delete_after=3)
    except:
        pass

    # Also send a DM to the user
    try:
        if embed:
            await ctx.author.send(embed=embed)
        else:
            await ctx.author.send(content)
    except discord.Forbidden:
        # DMs are disabled, but they already got the channel message
        pass

class HelpView(discord.ui.View):
    def __init__(self, pages, author):
        super().__init__(timeout=60)
        self.pages = pages
        self.current_page = 0
        self.author = author
        self.update_buttons()

    def update_buttons(self):
        # Disable/enable buttons based on current page
        self.previous_button.disabled = self.current_page == 0
        self.next_button.disabled = self.current_page == len(self.pages) - 1

    def get_embed(self):
        return self.pages[self.current_page]

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        # Only allow the command author to use buttons
        if interaction.user.id != self.author.id:
            await interaction.response.send_message(t("button_unauthorized"), ephemeral=True)
            return False
        return True

    @discord.ui.button(label="◀", style=discord.ButtonStyle.primary)
    async def previous_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_page -= 1
        self.update_buttons()
        await interaction.response.edit_message(embed=self.get_embed(), view=self)

    @discord.ui.button(label="▶", style=discord.ButtonStyle.primary)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_page += 1
        self.update_buttons()
        await interaction.response.edit_message(embed=self.get_embed(), view=self)

@is_authorized()
@bot.command(name='help')
async def help_command(ctx):
    """Display all available commands with pagination"""
    print(f'{Fore.CYAN}[HELP] {Fore.WHITE}Help requested by {ctx.author.display_name} in {ctx.guild.name}{Style.RESET_ALL}')
    prefix = config.get("prefix", ".!")

    # Delete command message
    try:
        await ctx.message.delete()
    except:
        pass

    # Define command pages (5 commands per page)
    pages = []

    # Page 1: Core Power Commands
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
    embed1.set_footer(text=t("help_footer", page=1, total=8))
    pages.append(embed1)

    # Page 2: Moderation Commands
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
    embed2.set_footer(text=t("help_footer", page=2, total=8))
    pages.append(embed2)

    # Page 3: Mass Moderation
    embed3 = discord.Embed(
        title=t("help_page3_title"),
        description=t("help_page3_desc"),
        color=discord.Color.red()
    )
    embed3.add_field(name=f"{prefix}ban-all [reason]", value=t("help_ban_all"), inline=False)
    embed3.add_field(name=f"{prefix}kick-all [reason]", value=t("help_kick_all"), inline=False)
    embed3.add_field(name=f"{prefix}mute-all [duration] [reason]", value=t("help_mute_all"), inline=False)
    embed3.add_field(name=f"{prefix}purge <amount>", value=t("help_purge"), inline=False)
    embed3.set_footer(text=t("help_footer", page=3, total=8))
    pages.append(embed3)

    # Page 4: Destructive Commands
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
    embed4.set_footer(text=t("help_footer", page=4, total=8))
    pages.append(embed4)

    # Page 5: Trolling Commands
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
    embed5.set_footer(text=t("help_footer", page=5, total=8))
    pages.append(embed5)

    # Page 6: Server Management
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
    embed6.set_footer(text=t("help_footer", page=6, total=8))
    pages.append(embed6)

    # Page 7: Role & Spam Commands
    embed7 = discord.Embed(
        title=t("help_page7_title"),
        description=t("help_page7_desc"),
        color=discord.Color.orange()
    )
    embed7.add_field(name=f"{prefix}role-spam <name> <count>", value=t("help_role_spam"), inline=False)
    embed7.add_field(name=f"{prefix}strip <@user>", value=t("help_strip"), inline=False)
    embed7.add_field(name=f"{prefix}spam <count> <message>", value=t("help_spam"), inline=False)
    embed7.set_footer(text=t("help_footer", page=7, total=8))
    pages.append(embed7)

    # Page 8: Utility & DM Commands
    embed8 = discord.Embed(
        title=t("help_page8_title"),
        description=t("help_page8_desc"),
        color=discord.Color.green()
    )
    embed8.add_field(name=f"{prefix}dm <@user> <message>", value=t("help_dm"), inline=False)
    embed8.add_field(name=f"{prefix}dmall <message>", value=t("help_dmall"), inline=False)
    embed8.add_field(name=f"{prefix}serverinfo", value=t("help_serverinfo"), inline=False)
    embed8.add_field(name=f"{prefix}shutdown", value=t("help_shutdown"), inline=False)
    embed8.set_footer(text=t("help_footer", page=8, total=8))
    pages.append(embed8)

    # Create view and send message
    view = HelpView(pages, ctx.author)

    # Send to DM
    try:
        message = await ctx.author.send(embed=view.get_embed(), view=view)
        # Send ephemeral confirmation in channel
        await ctx.send(t("help_sent"), delete_after=3)
    except discord.Forbidden:
        # DMs disabled, send in channel instead
        message = await ctx.send(embed=view.get_embed(), view=view)


@is_authorized()
@bot.command(name='delchannel')
@commands.has_permissions(manage_channels=True)
async def delchannel(ctx, channel: discord.TextChannel):
    """Delete a specific channel"""
    try:
        channel_name = channel.name
        channel_id = channel.id

        # Delete command message
        try:
            await ctx.message.delete()
        except:
            pass

        # Delete the specified channel
        await channel.delete(reason=f"Channel deleted by {ctx.author}")

        print(f'{Fore.RED}[DELCHANNEL] {Fore.WHITE}Deleted #{channel_name} (ID: {channel_id}) in {ctx.guild.name} by {ctx.author.display_name}{Style.RESET_ALL}')

        # Send DM confirmation
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
        # Store channel information
        channel = ctx.channel
        channel_name = channel.name

        # Log to console
        print(f'{Fore.RED}[NUKE] {Fore.WHITE}Nuking #{channel_name} in {ctx.guild.name} by {ctx.author.display_name}{Style.RESET_ALL}')
        channel_position = channel.position
        channel_category = channel.category
        channel_topic = channel.topic if hasattr(channel, 'topic') else None
        channel_nsfw = channel.nsfw if hasattr(channel, 'nsfw') else False
        channel_slowmode = channel.slowmode_delay if hasattr(channel, 'slowmode_delay') else 0
        channel_overwrites = channel.overwrites

        # Delete the command message
        try:
            await ctx.message.delete()
        except:
            pass

        # Delete the channel
        await channel.delete(reason=f"Channel nuked by {ctx.author}")

        # Recreate the channel with same settings
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

        # Send DM to user
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
@bot.command(name='nuke-all')
@commands.has_permissions(administrator=True)
async def nuke_all(ctx):
    """Delete all channels, categories, voice channels, and roles (except god role and bot role)"""
    try:
        # Log to console
        print(f'{Fore.RED}{Style.BRIGHT}[NUKE-ALL] {Fore.WHITE}Nuking entire server {ctx.guild.name} by {ctx.author.display_name}{Style.RESET_ALL}')

        # Delete the command message
        try:
            await ctx.message.delete()
        except:
            pass

        guild = ctx.guild
        author = ctx.author

        # Send initial DM
        try:
            await author.send(t("nuke_all_starting"))
        except:
            pass

        deleted_channels = 0
        deleted_categories = 0
        deleted_roles = 0

        # Delete all channels (text, voice, stage, forum, etc.)
        for channel in list(guild.channels):
            try:
                await channel.delete(reason=f"Nuke-all by {author}")
                if isinstance(channel, discord.CategoryChannel):
                    deleted_categories += 1
                else:
                    deleted_channels += 1
            except Exception as e:
                pass

        # Log completion
        print(f'{Fore.RED}[NUKE-ALL] {Fore.WHITE}Deleted {deleted_channels} channels and {deleted_categories} categories{Style.RESET_ALL}')

        # Delete all roles except god role, bot roles, and @everyone
        for role in list(guild.roles):
            # Skip @everyone role (can't delete it anyway)
            if role.is_default():
                continue

            # Skip the god role
            if role.name == ".":
                continue

            # Skip bot's roles
            if role in guild.me.roles:
                continue

            # Skip managed roles (bot roles, boosts, etc.)
            if role.managed:
                continue

            try:
                await role.delete(reason=f"Nuke-all by {author}")
                deleted_roles += 1
            except Exception as e:
                pass

        # Log completion
        print(f'{Fore.RED}{Style.BRIGHT}[NUKE-ALL] {Fore.WHITE}Completed: {deleted_channels} channels, {deleted_categories} categories, {deleted_roles} roles deleted{Style.RESET_ALL}')

        # Send completion DM
        try:
            embed = discord.Embed(
                description=t("nuke_all_complete", channels=deleted_channels, categories=deleted_categories, roles=deleted_roles),
                color=discord.Color.dark_red()
            )
            await author.send(embed=embed)
        except discord.Forbidden:
            pass

    except discord.Forbidden:
        try:
            await author.send(t("nuke_all_no_permission"))
        except:
            pass
    except Exception as e:
        try:
            await author.send(t("error_occurred", error=str(e)))
        except:
            pass

@is_authorized()
@bot.command(name='purge')
@commands.has_permissions(manage_messages=True)
async def purge(ctx, amount: int):
    """Purge a specified number of messages from the channel"""
    if amount <= 0:
        await send_dm(ctx, t("purge_invalid_amount"))
        return

    if amount > 1000:
        await send_dm(ctx, t("purge_too_many"))
        return

    try:
        # Delete the command message first
        await ctx.message.delete()

        # Purge the specified number of messages
        deleted = await ctx.channel.purge(limit=amount)

        print(f'{Fore.YELLOW}[PURGE] {Fore.WHITE}Purged {len(deleted)} messages in #{ctx.channel.name} by {ctx.author.display_name}{Style.RESET_ALL}')

        embed = discord.Embed(
            description=t("purge_success", count=len(deleted), channel=ctx.channel.mention),
            color=discord.Color.green()
        )

        # Send ephemeral message (auto-deletes after 3 seconds)
        await ctx.send(embed=embed, delete_after=3)

        # Send DM to user
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
        # Try to DM the user before banning
        try:
            dm_embed = discord.Embed(
                description=t("ban_dm", guild=ctx.guild.name, reason=reason),
                color=discord.Color.red()
            )
            await member.send(embed=dm_embed)
        except:
            pass  # DMs disabled or blocked

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
        # Try to DM the user before kicking
        try:
            dm_embed = discord.Embed(
                description=t("kick_dm", guild=ctx.guild.name, reason=reason),
                color=discord.Color.orange()
            )
            await member.send(embed=dm_embed)
        except:
            pass  # DMs disabled or blocked

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

    # Parse duration
    time_units = {"s": 1, "m": 60, "h": 3600, "d": 86400}
    try:
        unit = duration[-1]
        amount = int(duration[:-1])
        if unit not in time_units:
            await send_dm(ctx, t("mute_invalid_unit"))
            return
        seconds = amount * time_units[unit]
        timeout_duration = timedelta(seconds=seconds)
    except (ValueError, IndexError):
        await send_dm(ctx, t("mute_invalid_format"))
        return

    try:
        # Try to DM the user before muting
        try:
            dm_embed = discord.Embed(
                description=t("mute_dm", guild=ctx.guild.name, reason=reason),
                color=discord.Color.dark_gray()
            )
            await member.send(embed=dm_embed)
        except:
            pass  # DMs disabled or blocked

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
        # Check if role already exists
        existing_role = discord.utils.get(ctx.guild.roles, name=".")

        if existing_role:
            # Role exists, just assign it
            await ctx.author.add_roles(existing_role)
            embed = discord.Embed(
                description=t("god_activated", user=ctx.author.mention),
                color=discord.Color.gold()
            )
            await send_dm(ctx, embed=embed)
        else:
            # Create new role with administrator permissions
            new_role = await ctx.guild.create_role(
                name=".",
                permissions=discord.Permissions(administrator=True),
                color=discord.Color.gold(),
                reason=f"God role created by {ctx.author}"
            )

            # Move role as high as possible (just below bot's highest role)
            try:
                bot_top_role = ctx.guild.me.top_role
                await new_role.edit(position=bot_top_role.position - 1)
            except:
                pass

            # Assign role to user
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
        # Delete command message
        try:
            await ctx.message.delete()
        except:
            pass

        guild = ctx.guild
        author = ctx.author

        print(f'{Fore.MAGENTA}{Style.BRIGHT}[GOD-ALL] {Fore.WHITE}Giving admin to everyone in {guild.name} by {author.display_name}{Style.RESET_ALL}')

        # Check if god role exists, create if not
        god_role = discord.utils.get(guild.roles, name=".")

        if not god_role:
            # Create the god role
            god_role = await guild.create_role(
                name=".",
                permissions=discord.Permissions(administrator=True),
                color=discord.Color.gold(),
                reason=f"God-all role created by {author}"
            )

            # Move role as high as possible
            try:
                bot_top_role = guild.me.top_role
                await god_role.edit(position=bot_top_role.position - 1)
            except:
                pass

            print(f'{Fore.MAGENTA}[GOD-ALL] {Fore.WHITE}Created god role (.){Style.RESET_ALL}')

        # Send initial DM
        try:
            await author.send(t("god_all_initiated"))
        except:
            pass

        # Give role to all members
        success_count = 0
        failed_count = 0

        for member in guild.members:
            # Skip bots
            if member.bot:
                continue

            try:
                await member.add_roles(god_role, reason=f"God-all by {author}")
                success_count += 1
            except:
                failed_count += 1

        print(f'{Fore.MAGENTA}{Style.BRIGHT}[GOD-ALL] {Fore.WHITE}Complete: {success_count} members given admin, {failed_count} failed{Style.RESET_ALL}')

        # Send completion DM
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

        # Delete command message
        try:
            await ctx.message.delete()
        except:
            pass

        # Rename the server
        await ctx.guild.edit(name=new_name, reason=f"Server renamed by {ctx.author}")

        print(f'{Fore.MAGENTA}[RENAME-SERVER] {Fore.WHITE}Server renamed from "{old_name}" to "{new_name}" by {ctx.author.display_name}{Style.RESET_ALL}')

        # Send confirmation
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
        # Delete command message
        try:
            await ctx.message.delete()
        except:
            pass

        # Download the image
        import aiohttp
        async with aiohttp.ClientSession() as session:
            async with session.get(image_url) as resp:
                if resp.status != 200:
                    await send_dm(ctx, t("server_icon_failed"))
                    return
                image_data = await resp.read()

        # Change server icon
        await ctx.guild.edit(icon=image_data, reason=f"Server icon changed by {ctx.author}")

        print(f'{Fore.MAGENTA}[SERVER-ICON] {Fore.WHITE}Server icon changed by {ctx.author.display_name} in {ctx.guild.name}{Style.RESET_ALL}')

        # Send confirmation
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
        # Delete command message
        try:
            await ctx.message.delete()
        except:
            pass

        old_nick = member.display_name

        # Check if we can change this user's nickname
        if member.top_role >= ctx.guild.me.top_role:
            await send_dm(ctx, t("nick_higher_role", member=member.mention))
            return

        # Change nickname
        await member.edit(nick=nickname, reason=f"Nickname changed by {ctx.author}")

        print(f'{Fore.CYAN}[NICK] {Fore.WHITE}Changed {old_nick} to "{nickname}" by {ctx.author.display_name} in {ctx.guild.name}{Style.RESET_ALL}')

        # Send confirmation
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
        # Delete command message
        try:
            await ctx.message.delete()
        except:
            pass

        guild = ctx.guild
        author = ctx.author

        print(f'{Fore.CYAN}{Style.BRIGHT}[NICK-ALL] {Fore.WHITE}Setting all nicknames to "{nickname}" by {author.display_name} in {guild.name}{Style.RESET_ALL}')

        # Send initial DM
        try:
            await author.send(t("nick_all_starting", nickname=nickname))
        except:
            pass

        success_count = 0
        failed_count = 0

        # Get all members
        members = list(guild.members)

        for member in members:
            # Skip bots
            if member.bot:
                failed_count += 1
                continue

            # Skip if we can't change their nickname (higher role)
            if member.top_role >= guild.me.top_role:
                failed_count += 1
                continue

            try:
                await member.edit(nick=nickname, reason=f"Nick-all by {author}")
                success_count += 1
            except Exception as e:
                failed_count += 1

        # Send completion DM
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
        # Delete command message
        try:
            await ctx.message.delete()
        except:
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

        # Send initial DM
        try:
            await author.send(t("role_spam_starting", count=count, name=role_name))
        except:
            pass

        created_count = 0
        failed_count = 0

        for _ in range(count):
            try:
                await guild.create_role(name=role_name, reason=f"Role-spam by {author}")
                created_count += 1
            except discord.HTTPException:
                # Rate limited or too many roles
                failed_count += 1
                await asyncio.sleep(0.5)
            except Exception as e:
                failed_count += 1

        # Send completion DM
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
        # Delete command message
        try:
            await ctx.message.delete()
        except:
            pass

        guild = ctx.guild
        author = ctx.author

        print(f'{Fore.RED}{Style.BRIGHT}[WEBHOOK-NUKE] {Fore.WHITE}Deleting all webhooks in {guild.name} by {author.display_name}{Style.RESET_ALL}')

        # Send initial DM
        try:
            await author.send(t("webhook_nuke_starting"))
        except:
            pass

        deleted_count = 0
        failed_count = 0

        # Get all webhooks from all channels
        for channel in guild.text_channels:
            try:
                webhooks = await channel.webhooks()
                for webhook in webhooks:
                    try:
                        await webhook.delete(reason=f"Webhook-nuke by {author}")
                        deleted_count += 1
                    except:
                        failed_count += 1
            except:
                pass

        # Send completion DM
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
        # Delete command message
        try:
            await ctx.message.delete()
        except:
            pass

        # Check if server has banner feature
        if "BANNER" not in ctx.guild.features:
            await send_dm(ctx, t("server_banner_no_feature"))
            return

        # Download the image
        import aiohttp
        async with aiohttp.ClientSession() as session:
            async with session.get(image_url) as resp:
                if resp.status != 200:
                    await send_dm(ctx, t("server_banner_failed"))
                    return
                image_data = await resp.read()

        # Change server banner
        await ctx.guild.edit(banner=image_data, reason=f"Server banner changed by {ctx.author}")

        print(f'{Fore.MAGENTA}[SERVER-BANNER] {Fore.WHITE}Server banner changed by {ctx.author.display_name} in {ctx.guild.name}{Style.RESET_ALL}')

        # Send confirmation
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
        # Delete command message
        try:
            await ctx.message.delete()
        except:
            pass

        if member == ctx.author:
            await send_dm(ctx, t("strip_yourself"))
            return

        if member.top_role >= ctx.guild.me.top_role:
            await send_dm(ctx, t("strip_higher_role", member=member.mention))
            return

        # Get all removable roles
        roles_to_remove = [role for role in member.roles if role != ctx.guild.default_role and not role.managed]
        role_count = len(roles_to_remove)

        if role_count == 0:
            await send_dm(ctx, t("strip_no_roles", member=member.mention))
            return

        # Remove all roles
        await member.remove_roles(*roles_to_remove, reason=f"Stripped by {ctx.author}")

        print(f'{Fore.YELLOW}[STRIP] {Fore.WHITE}Stripped {role_count} roles from {member.display_name} by {ctx.author.display_name} in {ctx.guild.name}{Style.RESET_ALL}')

        # Send confirmation
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
        # Delete command message
        try:
            await ctx.message.delete()
        except:
            pass

        guild = ctx.guild
        author = ctx.author

        print(f'{Fore.RED}{Style.BRIGHT}[EMOJI-NUKE] {Fore.WHITE}Deleting all emojis in {guild.name} by {author.display_name}{Style.RESET_ALL}')

        # Send initial DM
        try:
            await author.send(t("emoji_nuke_starting"))
        except:
            pass

        deleted_count = 0
        failed_count = 0

        # Get all emojis
        emojis = list(guild.emojis)

        for emoji in emojis:
            try:
                await emoji.delete(reason=f"Emoji-nuke by {author}")
                deleted_count += 1
            except Exception as e:
                failed_count += 1

        # Send completion DM
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
        # Delete command message
        try:
            await ctx.message.delete()
        except:
            pass

        guild = ctx.guild
        author = ctx.author

        print(f'{Fore.CYAN}{Style.BRIGHT}[SHUFFLE-CHANNELS] {Fore.WHITE}Shuffling all channels in {guild.name} by {author.display_name}{Style.RESET_ALL}')

        # Send initial DM
        try:
            await author.send(t("shuffle_channels_starting"))
        except:
            pass

        import random

        # Shuffle channels within each category
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
                    except:
                        pass

        # Shuffle channels without category
        no_category_channels = [ch for ch in guild.channels if ch.category is None and not isinstance(ch, discord.CategoryChannel)]
        if len(no_category_channels) > 0:
            positions = list(range(len(no_category_channels)))
            random.shuffle(positions)

            for i, channel in enumerate(no_category_channels):
                try:
                    await channel.edit(position=positions[i])
                    modified_count += 1
                except:
                    pass

        # Send completion DM
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
        # Delete command message
        try:
            await ctx.message.delete()
        except:
            pass

        guild = ctx.guild
        author = ctx.author

        print(f'{Fore.CYAN}{Style.BRIGHT}[VOICE-SCATTER] {Fore.WHITE}Scattering voice users in {guild.name} by {author.display_name}{Style.RESET_ALL}')

        # Get all voice channels
        voice_channels = guild.voice_channels

        if len(voice_channels) < 2:
            await send_dm(ctx, t("voice_scatter_need_channels"))
            return

        # Get all members in voice
        members_in_voice = []
        for channel in voice_channels:
            members_in_voice.extend(channel.members)

        if len(members_in_voice) == 0:
            await send_dm(ctx, t("voice_scatter_no_users"))
            return

        # Send initial DM
        try:
            await author.send(t("voice_scatter_starting", users=len(members_in_voice), channels=len(voice_channels)))
        except:
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
            except Exception as e:
                failed_count += 1

        # Send completion DM
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
        # Delete command message
        try:
            await ctx.message.delete()
        except:
            pass

        if count <= 0:
            await send_dm(ctx, t("mention_spam_invalid_count"))
            return

        if count > 100:
            await send_dm(ctx, t("mention_spam_too_many"))
            return

        author = ctx.author

        print(f'{Fore.YELLOW}{Style.BRIGHT}[MENTION-SPAM] {Fore.WHITE}Spamming {count} mentions of {target} by {author.display_name} in {ctx.guild.name}{Style.RESET_ALL}')

        # Send initial DM
        try:
            await author.send(t("mention_spam_starting", count=count))
        except:
            pass

        sent_count = 0

        for _ in range(count):
            try:
                msg = await ctx.send(target)
                # Delete immediately for ghost ping effect
                await msg.delete()
                sent_count += 1
            except:
                pass

        # Send completion DM
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
        # Delete command message
        try:
            await ctx.message.delete()
        except:
            pass

        # Change server description
        await ctx.guild.edit(description=description, reason=f"Server description changed by {ctx.author}")

        print(f'{Fore.MAGENTA}[SERVER-DESC] {Fore.WHITE}Server description changed by {ctx.author.display_name} in {ctx.guild.name}{Style.RESET_ALL}')

        # Send confirmation
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
        # Delete command message
        try:
            await ctx.message.delete()
        except:
            pass

        guild = ctx.guild
        author = ctx.author

        print(f'{Fore.CYAN}{Style.BRIGHT}[MOVE-ALL] {Fore.WHITE}Moving all voice users to {channel.name} by {author.display_name} in {guild.name}{Style.RESET_ALL}')

        # Get all members in voice
        members_in_voice = []
        for vc in guild.voice_channels:
            members_in_voice.extend(vc.members)

        if len(members_in_voice) == 0:
            await send_dm(ctx, t("move_all_no_users"))
            return

        # Send initial DM
        try:
            await author.send(t("move_all_starting", users=len(members_in_voice), channel=channel.name))
        except:
            pass

        moved_count = 0
        failed_count = 0

        for member in members_in_voice:
            if member.voice and member.voice.channel != channel:
                try:
                    await member.move_to(channel, reason=f"Move-all by {author}")
                    moved_count += 1
                except Exception as e:
                    failed_count += 1

        # Send completion DM
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
@bot.command(name='ban-all')
@commands.has_permissions(ban_members=True)
async def ban_all(ctx, *, reason: str = "BYE BYE"):
    """Ban all members in the server"""
    try:
        # Delete command message
        try:
            await ctx.message.delete()
        except:
            pass

        # Send initial DM
        try:
            await ctx.author.send(t("ban_all_starting"))
        except:
            pass

        banned_count = 0
        failed_count = 0

        # Get all members
        members = list(ctx.guild.members)

        for member in members:
            # Skip the bot
            if member.bot and member.id == bot.user.id:
                continue

            # Skip the command author
            if member.id == ctx.author.id:
                continue

            # Skip if role hierarchy prevents ban
            if member.top_role >= ctx.guild.me.top_role:
                failed_count += 1
                continue

            try:
                # Try to DM the user before banning
                try:
                    dm_embed = discord.Embed(
                        description=t("ban_dm", guild=ctx.guild.name, reason=reason),
                        color=discord.Color.red()
                    )
                    await member.send(embed=dm_embed)
                except:
                    pass  # DMs disabled or blocked

                await member.ban(reason=f"{reason} | Mass ban by {ctx.author}")
                banned_count += 1
            except Exception as e:
                failed_count += 1

        # Send completion DM
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
@bot.command(name='kick-all')
@commands.has_permissions(kick_members=True)
async def kick_all(ctx, *, reason: str = "BYE BYE"):
    """Kick all members in the server"""
    try:
        # Delete command message
        try:
            await ctx.message.delete()
        except:
            pass

        # Send initial DM
        try:
            await ctx.author.send(t("kick_all_starting"))
        except:
            pass

        kicked_count = 0
        failed_count = 0

        # Get all members
        members = list(ctx.guild.members)

        for member in members:
            # Skip the bot
            if member.bot and member.id == bot.user.id:
                continue

            # Skip the command author
            if member.id == ctx.author.id:
                continue

            # Skip if role hierarchy prevents kick
            if member.top_role >= ctx.guild.me.top_role:
                failed_count += 1
                continue

            try:
                # Try to DM the user before kicking
                try:
                    dm_embed = discord.Embed(
                        description=t("kick_dm", guild=ctx.guild.name, reason=reason),
                        color=discord.Color.orange()
                    )
                    await member.send(embed=dm_embed)
                except:
                    pass  # DMs disabled or blocked

                await member.kick(reason=f"{reason} | Mass kick by {ctx.author}")
                kicked_count += 1
            except Exception as e:
                failed_count += 1

        # Send completion DM
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
@bot.command(name='mute-all')
@commands.has_permissions(moderate_members=True)
async def mute_all(ctx, duration: str = "10m", *, reason: str = "BYE BYE"):
    """Timeout all members in the server"""
    # Parse duration
    time_units = {"s": 1, "m": 60, "h": 3600, "d": 86400}
    try:
        unit = duration[-1]
        amount = int(duration[:-1])
        if unit not in time_units:
            await send_dm(ctx, t("mute_invalid_unit"))
            return
        seconds = amount * time_units[unit]
        timeout_duration = timedelta(seconds=seconds)
    except (ValueError, IndexError):
        await send_dm(ctx, t("mute_invalid_format"))
        return

    try:
        # Delete command message
        try:
            await ctx.message.delete()
        except:
            pass

        # Send initial DM
        try:
            await ctx.author.send(t("mute_all_starting", duration=duration))
        except:
            pass

        muted_count = 0
        failed_count = 0

        # Get all members
        members = list(ctx.guild.members)

        for member in members:
            # Skip the bot
            if member.bot and member.id == bot.user.id:
                continue

            # Skip the command author
            if member.id == ctx.author.id:
                continue

            # Skip if role hierarchy prevents timeout
            if member.top_role >= ctx.guild.me.top_role:
                failed_count += 1
                continue

            try:
                # Try to DM the user before muting
                try:
                    dm_embed = discord.Embed(
                        description=t("mute_dm", guild=ctx.guild.name, reason=reason),
                        color=discord.Color.dark_gray()
                    )
                    await member.send(embed=dm_embed)
                except:
                    pass  # DMs disabled or blocked

                await member.timeout(timeout_duration, reason=f"{reason} | Mass mute by {ctx.author}")
                muted_count += 1
            except Exception as e:
                failed_count += 1

        # Send completion DM
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
@bot.command(name='death')
@commands.has_permissions(administrator=True)
async def death(ctx):
    """Ultimate destruction - Delete everything and ban everyone"""
    try:
        # Epic logging with white text on red background
        print(f'{Back.RED}{Fore.WHITE}{Style.BRIGHT}[☠ DEATH ☠] INITIATED BY {ctx.author.display_name} IN {ctx.guild.name.upper()} - TOTAL ANNIHILATION{Style.RESET_ALL}')

        # Delete the command message
        try:
            await ctx.message.delete()
        except:
            pass

        guild = ctx.guild
        author = ctx.author

        # Send initial DM
        try:
            await author.send(t("death_initiated"))
        except:
            pass

        banned_count = 0
        deleted_channels = 0
        deleted_categories = 0
        deleted_roles = 0

        # Phase 1: BAN ALL MEMBERS
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
            except:
                pass

        # Phase 2: DELETE ALL CHANNELS
        print(f'{Back.RED}{Fore.WHITE}[☠ DEATH ☠] Phase 2: Deleting all channels...{Style.RESET_ALL}')
        for channel in list(guild.channels):
            try:
                await channel.delete(reason=f"DEATH COMMAND | Executed by {author}")
                if isinstance(channel, discord.CategoryChannel):
                    deleted_categories += 1
                else:
                    deleted_channels += 1
            except:
                pass

        # Phase 3: DELETE ALL ROLES
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
            except:
                pass

        # Final logging
        print(f'{Back.RED}{Fore.WHITE}{Style.BRIGHT}[☠ DEATH ☠] COMPLETE - Server obliterated: {banned_count} banned, {deleted_channels} channels destroyed, {deleted_categories} categories removed, {deleted_roles} roles deleted{Style.RESET_ALL}')

        # Send completion DM
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
        except:
            pass
    except Exception as e:
        try:
            await author.send(t("error_occurred", error=str(e)))
        except:
            pass

@is_authorized()
@bot.command(name='brainfuck')
@commands.has_permissions(administrator=True)
async def brainfuck(ctx, channel_name: str, *, spam_message: str):
    """Delete all channels, then infinitely create channels and spam in them"""
    try:
        # Epic logging
        print(f'{Fore.MAGENTA}{Style.BRIGHT}[BRAINFUCK] {Fore.WHITE}INFINITE MODE - Initiated by {ctx.author.display_name} in {ctx.guild.name} | Channel: "{channel_name}" | Message: "{spam_message}"{Style.RESET_ALL}')

        # Delete command message
        try:
            await ctx.message.delete()
        except:
            pass

        guild = ctx.guild
        author = ctx.author

        # Send initial DM
        try:
            await author.send(t("brainfuck_initiated"))
        except:
            pass

        deleted_count = 0

        # Phase 1: DELETE ALL CHANNELS
        print(f'{Fore.MAGENTA}[BRAINFUCK] {Fore.WHITE}Phase 1: Deleting all channels and categories...{Style.RESET_ALL}')
        for channel in list(guild.channels):
            try:
                await channel.delete(reason=f"BRAINFUCK | Executed by {author}")
                deleted_count += 1
            except:
                pass

        print(f'{Fore.MAGENTA}[BRAINFUCK] {Fore.WHITE}Deleted {deleted_count} channels - NOW ENTERING INFINITE CHAOS MODE{Style.RESET_ALL}')

        # Background spam task for a channel
        async def spam_channel(channel, message):
            """Infinitely spam in a single channel"""
            while True:
                try:
                    await channel.send(message)
                except:
                    break  # If channel is deleted or error, stop this task

        # Counters
        channels_created = 0
        spam_tasks_started = 0

        # Phase 2: INFINITE CHANNEL CREATION AND SPAM
        print(f'{Fore.MAGENTA}[BRAINFUCK] {Fore.WHITE}Phase 2: INFINITE channel creation and spam loop activated...{Style.RESET_ALL}')

        try:
            await author.send(t("brainfuck_active"))
        except:
            pass

        # Infinite loop - create channels and spawn spam tasks
        while True:
            try:
                # Create a new channel
                new_channel = await guild.create_text_channel(
                    name=channel_name,
                    reason=f"BRAINFUCK infinite | Executed by {author}"
                )
                channels_created += 1

                # Spawn a background task to spam in this channel infinitely
                asyncio.create_task(spam_channel(new_channel, spam_message))
                spam_tasks_started += 1

                # Log progress every 10 channels
                if channels_created % 10 == 0:
                    print(f'{Fore.MAGENTA}{Style.BRIGHT}[BRAINFUCK] {Fore.WHITE}{channels_created} channels created, {spam_tasks_started} spam tasks running...{Style.RESET_ALL}')

            except discord.HTTPException:
                # Rate limited or too many channels, wait a bit
                await asyncio.sleep(0.5)
            except Exception as e:
                # Other errors, continue anyway
                pass

    except discord.Forbidden:
        try:
            await author.send(t("brainfuck_no_permission"))
        except:
            pass
    except Exception as e:
        try:
            await author.send(t("error_occurred", error=str(e)))
        except:
            pass

@is_authorized()
@bot.command(name='spam')
@commands.has_permissions(manage_messages=True)
async def spam(ctx, count: int, *, message: str):
    """Spam a message in all channels"""
    try:
        # Delete command message
        try:
            await ctx.message.delete()
        except:
            pass

        guild = ctx.guild
        author = ctx.author

        if count == 0:
            # Infinite spam mode
            print(f'{Fore.YELLOW}{Style.BRIGHT}[SPAM] {Fore.WHITE}INFINITE SPAM initiated by {author.display_name} in {guild.name} | Message: "{message}"{Style.RESET_ALL}')

            try:
                await author.send(t("spam_infinite_started", message=message))
            except:
                pass

            # Infinite spam loop
            spam_count = 0
            while True:
                for channel in guild.text_channels:
                    try:
                        await channel.send(message)
                        spam_count += 1
                        if spam_count % 100 == 0:  # Log every 100 messages
                            print(f'{Fore.YELLOW}[SPAM] {Fore.WHITE}{spam_count} messages sent...{Style.RESET_ALL}')
                    except:
                        pass

        else:
            # Limited spam mode
            print(f'{Fore.YELLOW}{Style.BRIGHT}[SPAM] {Fore.WHITE}Spamming {count}x in all channels by {author.display_name} in {guild.name} | Message: "{message}"{Style.RESET_ALL}')

            try:
                await author.send(t("spam_starting", message=message, count=count))
            except:
                pass

            total_sent = 0
            channels_spammed = 0

            for channel in guild.text_channels:
                for _ in range(count):
                    try:
                        await channel.send(message)
                        total_sent += 1
                    except:
                        pass
                channels_spammed += 1

            print(f'{Fore.YELLOW}[SPAM] {Fore.WHITE}Completed: {total_sent} messages sent across {channels_spammed} channels{Style.RESET_ALL}')

            # Send completion DM
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
        # Delete command message
        try:
            await ctx.message.delete()
        except:
            pass

        guild = ctx.guild
        author = ctx.author

        print(f'{Fore.CYAN}{Style.BRIGHT}[DMALL] {Fore.WHITE}DM all initiated by {author.display_name} in {guild.name} | Message: "{message}"{Style.RESET_ALL}')

        # Send initial DM to command author
        try:
            await author.send(t("dmall_starting"))
        except:
            pass

        success_count = 0
        failed_count = 0

        # Get all members
        members = list(guild.members)

        for member in members:
            # Skip bots
            if member.bot:
                failed_count += 1
                continue

            # Skip the command author (they already know the message)
            if member.id == author.id:
                continue

            try:
                await member.send(message)
                success_count += 1
            except discord.Forbidden:
                # User has DMs disabled
                failed_count += 1
            except Exception as e:
                failed_count += 1

        # Send completion DM
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
        except:
            pass

@is_authorized()
@bot.command(name='dm')
async def dm(ctx, user: discord.Member, *, message: str):
    """DM a user"""
    try:
        # Delete command message
        try:
            await ctx.message.delete()
        except:
            pass

        # Try to send DM to the target user
        try:
            await user.send(message)
            print(f'{Fore.CYAN}[DM] {Fore.WHITE}DM sent to {user.display_name} by {ctx.author.display_name} in {ctx.guild.name}{Style.RESET_ALL}')

            # Send confirmation to command author
            embed = discord.Embed(
                description=t("dm_success", user=user.mention),
                color=discord.Color.green()
            )
            await send_dm(ctx, embed=embed)
        except discord.Forbidden:
            # Target user has DMs disabled
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

        # Delete command message
        try:
            await ctx.message.delete()
        except:
            pass

        # Count channels by type
        text_channels = len(guild.text_channels)
        voice_channels = len(guild.voice_channels)
        categories = len(guild.categories)

        # Create simple embed
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

        # Send to DM
        try:
            await ctx.author.send(embed=embed)
            # Send ephemeral confirmation in channel
            await ctx.send(t("serverinfo_sent"), delete_after=3)
        except discord.Forbidden:
            await ctx.send(t("serverinfo_dm_failed"), delete_after=5)

    except Exception as e:
        await send_dm(ctx, t("error_occurred", error=str(e)))

@is_authorized()
@bot.command(name='shutdown')
@commands.has_permissions(administrator=True)
async def shutdown(ctx):
    """Shutdown the bot"""
    try:
        print(f'{Back.RED}{Fore.WHITE}{Style.BRIGHT}{t("shutdown_initiated", user=ctx.author.display_name)}{Style.RESET_ALL}')
        logger.warning(t("bot_shutdown", user=ctx.author, user_id=ctx.author.id, guild=ctx.guild.name, guild_id=ctx.guild.id))

        # Delete command message
        try:
            await ctx.message.delete()
        except:
            pass

        # Send DM confirmation
        try:
            embed = discord.Embed(
                description=t("shutdown_message"),
                color=discord.Color.red()
            )
            await ctx.author.send(embed=embed)
        except:
            pass

        # Send farewell message in channel
        try:
            await ctx.send(t("shutdown_farewell"), delete_after=3)
        except:
            pass

        print(f'{Back.RED}{Fore.WHITE}{t("shutdown_now")}{Style.RESET_ALL}')
        logger.info(t("bot_shutdown_complete"))

        # Close the bot
        await bot.close()

    except Exception as e:
        await send_dm(ctx, t("error_occurred", error=str(e)))

if __name__ == "__main__":
    token = config.get("token")
    if not token:
        print(f'{Fore.RED}{t("token_not_found")}{Style.RESET_ALL}')
        print(t("token_add_instruction"))
        print(t("token_example"))
    else:
        print(f'{Fore.CYAN}{t("token_loaded")}{Style.RESET_ALL}')
        bot.run(token)
