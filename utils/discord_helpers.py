import asyncio
from datetime import timedelta

import discord
from colorama import Fore, Style
from discord.ext import commands


def make_is_authorized(config, logger, translate):
    """Create the standard authorization check."""
    def is_authorized():
        async def predicate(ctx):
            owner_id = config.get("owner_id")
            whitelist = config.get("whitelist", [])

            if owner_id and isinstance(owner_id, str) and owner_id.isdigit():
                owner_id = int(owner_id)

            if ctx.author.id == owner_id or ctx.author.id in whitelist:
                return True

            print(f"{Fore.RED}[UNAUTHORIZED] {Fore.WHITE}{ctx.author.display_name} (ID: {ctx.author.id}) attempted to use {ctx.command.name} in {ctx.guild.name}{Style.RESET_ALL}")
            logger.warning(translate("unauthorized", user=ctx.author, user_id=ctx.author.id, command=ctx.command.name, guild=ctx.guild.name, guild_id=ctx.guild.id))

            try:
                await ctx.message.delete()
            except (discord.HTTPException, discord.NotFound):
                pass

            try:
                embed = discord.Embed(
                    description=translate("unauthorized_message"),
                    color=discord.Color.red(),
                )
                await ctx.send(embed=embed, delete_after=5)
            except discord.HTTPException:
                pass

            return False

        return commands.check(predicate)

    return is_authorized


def make_is_owner(config, translate):
    """Create the owner-only authorization check."""
    def is_owner():
        async def predicate(ctx):
            owner_id = config.get("owner_id")
            if owner_id and isinstance(owner_id, str) and owner_id.isdigit():
                owner_id = int(owner_id)
            if ctx.author.id == owner_id:
                return True
            try:
                await ctx.message.delete()
            except (discord.HTTPException, discord.NotFound):
                pass
            embed = discord.Embed(
                description=translate("owner_only_message"),
                color=discord.Color.red(),
            )
            try:
                await ctx.send(embed=embed, delete_after=5)
            except discord.HTTPException:
                pass
            return False

        return commands.check(predicate)

    return is_owner


async def send_dm(ctx, content=None, embed=None):
    """Delete the command, send a short channel response, and DM the author."""
    try:
        await ctx.message.delete()
    except (discord.HTTPException, discord.NotFound):
        pass

    try:
        if embed:
            await ctx.send(embed=embed, delete_after=3)
        else:
            await ctx.send(content, delete_after=3)
    except discord.HTTPException:
        pass

    try:
        if embed:
            await ctx.author.send(embed=embed)
        else:
            await ctx.author.send(content)
    except discord.Forbidden:
        pass


async def rate_limited_action(coro_fn):
    """Call coro_fn(), retrying once after a Discord 429 delay."""
    try:
        await coro_fn()
        return True
    except discord.HTTPException as exc:
        if exc.status == 429:
            await asyncio.sleep(getattr(exc, "retry_after", 1.0))
            try:
                await coro_fn()
                return True
            except (discord.HTTPException, discord.Forbidden):
                return False
        return False
    except discord.Forbidden:
        return False


def parse_duration(duration):
    """Parse a duration string like 10m, 1h, 30s, or 1d into a timedelta."""
    time_units = {"s": 1, "m": 60, "h": 3600, "d": 86400}
    try:
        unit = duration[-1]
        amount = int(duration[:-1])
        if unit not in time_units or amount <= 0:
            return None
        return timedelta(seconds=amount * time_units[unit])
    except (ValueError, IndexError):
        return None
