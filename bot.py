import discord
from discord.ext import commands
import asyncio
import random
import datetime
import json
import aiohttp
import string

# --- CONFIG ---
BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"
WARDEN_ROLE_ID = 123456789012345678 # Replace with your Warden role ID
JAIL_CATEGORY_ID = 123456789012345678 # Optional: Jail category ID

# --- SETUP ---
# Intents are necessary for the bot to receive certain events.
intents = discord.Intents.default()
intents.members = True
intents.messages = True
intents.message_content = True
intents.guilds = True
intents.reactions = True
intents.presences = True

bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

# --- HELPERS ---
def is_warden():
    """Check command context for Warden role."""
    async def predicate(ctx):
        return any(role.id == WARDEN_ROLE_ID for role in ctx.author.roles)
    return commands.check(predicate)

def has_higher_role_hierarchy(bot_member, target_role):
    return bot_member.top_role > target_role

# --- EVENTS ---
@bot.event
async def on_ready():
    print('--------------------')
    print(f'Warden Bot is online: {bot.user.name}')
    print(f'Warden Bot is active in {len(bot.guilds)} server(s).')
    print('--------------------')
    try:
        synced = await bot.tree.sync()
        print(f"Successfully synced {len(synced)} command(s).")
    except Exception as e:
        print(f"Failed to sync commands: {e}")

@bot.event
async def on_guild_join(guild):
    # Announce creator in the system channel.
    system_channel = guild.system_channel
    announcement = "Warden Bot Was Officially Made by Spikeytacos."
    if system_channel and system_channel.permissions_for(guild.me).send_messages:
        try:
            await system_channel.send(announcement)
        except discord.Forbidden:
            pass

    # Create the Warden role on join if it doesn't exist.
    warden_role = discord.utils.get(guild.roles, name="Warden")
    if not warden_role:
        try:
            warden_role = await guild.create_role(name="Warden", permissions=discord.Permissions(8), reason="Initial setup.")
            print(f"Created Warden role in {guild.name}")
        except discord.Forbidden:
            print(f"Failed to create Warden role in {guild.name}.")

# --- TYRANT COG ---
class Tyrant(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.jailed_users = {}

    @commands.command(name="nuke-channel")
    @is_warden()
    async def nuke_channel(self, ctx):
        await ctx.send("Channel deletion in progress.")
        await asyncio.sleep(3)
        await ctx.channel.delete()

    @commands.command(name="nuke-all-channels")
    @is_warden()
    async def nuke_all_channels(self, ctx):
        await ctx.send("Confirm this action by typing `!confirm-nuke` in the next 30 seconds.")
        def check(m):
            return m.author == ctx.author and m.channel == ctx.channel and m.content == "!confirm-nuke"
        try:
            await self.bot.wait_for("message", check=check, timeout=30.0)
            await ctx.send("Deleting all channels.")
            for channel in ctx.guild.channels:
                try:
                    await channel.delete()
                except discord.Forbidden:
                    continue
        except asyncio.TimeoutError:
            await ctx.send("Action cancelled.")

    @commands.command(name="jail")
    @is_warden()
    async def jail(self, ctx, member: discord.Member, *, reason="No reason provided."):
        if member.top_role >= ctx.author.top_role and member.id != ctx.guild.owner_id:
            return await ctx.send("Target has a higher or equal role.")
        
        jail_role = discord.utils.get(ctx.guild.roles, name="Prisoner")
        if not jail_role:
            jail_role = await ctx.guild.create_role(name="Prisoner", reason="Jail role creation.")
            for channel in ctx.guild.channels:
                await channel.set_permissions(jail_role, read_messages=False, send_messages=False)

        jail_category = discord.utils.get(ctx.guild.categories, id=JAIL_CATEGORY_ID)
        jail_channel = discord.utils.get(ctx.guild.text_channels, name="jail")
        if not jail_channel:
            overwrites = {ctx.guild.default_role: discord.PermissionOverwrite(read_messages=False),
                         jail_role: discord.PermissionOverwrite(read_messages=True, send_messages=True)}
            jail_channel = await ctx.guild.create_text_channel("jail", category=jail_category, overwrites=overwrites)

        self.jailed_users[member.id] = [member.roles, member.nick]
        await member.edit(roles=[jail_role], nick=f"Jailed [{member.display_name}]", reason=reason)
        await ctx.send(f"{member.mention} has been jailed. Reason: {reason}")

    @commands.command(name="unjail")
    @is_warden()
    async def unjail(self, ctx, member: discord.Member):
        if member.id not in self.jailed_users:
            return await ctx.send("This user is not jailed.")
        
        old_roles, old_nick = self.jailed_users.pop(member.id)
        await member.edit(roles=old_roles, nick=old_nick, reason="Released from jail.")
        await ctx.send(f"{member.mention} has been released.")

    @commands.command(name="purge")
    @is_warden()
    async def purge(self, ctx, amount: int = 10):
        await ctx.channel.purge(limit=amount + 1)
        await ctx.send(f"Purged {amount} messages.", delete_after=3)

    @commands.command(name="kick")
    @is_warden()
    async def kick(self, ctx, member: discord.Member, *, reason="No reason provided."):
        if member.top_role >= ctx.author.top_role and member.id != ctx.guild.owner_id:
            return await ctx.send("Target has a higher or equal role.")
        await member.kick(reason=reason)
        await ctx.send(f"{member.mention} has been kicked. Reason: {reason}")

    @commands.command(name="ban")
    @is_warden()
    async def ban(self, ctx, member: discord.Member, *, reason="No reason provided."):
        if member.top_role >= ctx.author.top_role and member.id != ctx.guild.owner_id:
            return await ctx.send("Target has a higher or equal role.")
        await member.ban(reason=reason)
        await ctx.send(f"{member.mention} has been banned. Reason: {reason}")

    @commands.command(name="nickname-all")
    @is_warden()
    async def nickname_all(self, ctx, *, nickname="Warden Victim"):
        await ctx.send(f"Changing all nicknames to '{nickname}'...")
        for member in ctx.guild.members:
            if not member.top_role >= ctx.author.top_role:
                try:
                    await member.edit(nick=nickname)
                except discord.Forbidden:
                    continue
        await ctx.send("Nicknames updated.")

    @commands.command(name="slowmode-all")
    @is_warden()
    async def slowmode_all(self, ctx, seconds: int):
        for channel in ctx.guild.text_channels:
            await channel.edit(slowmode_delay=seconds)
        await ctx.send(f"Slowmode set to {seconds} seconds in all channels.")

# --- TRICKSTER COG ---
class Trickster(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.mocking = {}
        self.echoing = {}

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return
        
        if message.author.id in self.mocking and datetime.datetime.now() < self.mocking[message.author.id]:
            await message.channel.send(message.content.upper())

        if message.author.id in self.echoing and datetime.datetime.now() < self.echoing[message.author.id]:
            try:
                await message.author.send(f"You said: {message.content}")
            except discord.Forbidden:
                pass

        await self.bot.process_commands(message)

    @commands.command(name="mock")
    @is_warden()
    async def mock(self, ctx, member: discord.Member, duration: int = 10):
        self.mocking[member.id] = datetime.datetime.now() + datetime.timedelta(minutes=duration)
        await ctx.send(f"{member.mention} is now being mocked for {duration} minutes.")

    @commands.command(name="echo")
    @is_warden()
    async def echo(self, ctx, member: discord.Member, duration: int = 5):
        self.echoing[member.id] = datetime.datetime.now() + datetime.timedelta(minutes=duration)
        await ctx.send(f"{member.mention} is now being echoed for {duration} minutes.")

    @commands.command(name="ghost-ping")
    @is_warden()
    async def ghost_ping(self, ctx, member: discord.Member, times: int = 5):
        for _ in range(times):
            msg = await ctx.send(member.mention)
            await msg.delete()
            await asyncio.sleep(0.5)
        await ctx.message.delete()

    @commands.command(name="spam-emoji")
    @is_warden()
    async def spam_emoji(self, ctx, emoji: str, count: int = 20):
        if not emoji.startswith("<:") and not emoji.startswith("<a:"):
            return await ctx.send("Invalid custom emoji.")
        for _ in range(count):
            await ctx.send(emoji)
            await asyncio.sleep(0.1)

    @commands.command(name="nick-spam")
    @is_warden()
    async def nick_spam(self, ctx, member: discord.Member, nickname: str):
        await ctx.send(f"Changing nickname for {member.mention}...")
        for i in range(10):
            await member.edit(nick=f"{nickname}_{i}")
            await asyncio.sleep(1)
        await member.edit(nick=member.display_name)

# --- ORACLE COG ---
class Oracle(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="whois")
    @is_warden()
    async def whois(self, ctx, member: discord.Member):
        embed = discord.Embed(title=f"Info on {member.name}", color=member.color)
        embed.set_thumbnail(url=member.avatar.url)
        embed.add_field(name="ID", value=member.id)
        embed.add_field(name="Joined Server", value=member.joined_at.strftime("%b %d, %Y"))
        embed.add_field(name="Created Account", value=member.created_at.strftime("%b %d, %Y"))
        embed.add_field(name="Top Role", value=member.top_role.mention)
        embed.add_field(name="Roles", value=" ".join([role.mention for role in member.roles[1:]]))
        await ctx.send(embed=embed)

    @commands.command(name="server-info")
    @is_warden()
    async def server_info(self, ctx):
        guild = ctx.guild
        embed = discord.Embed(title=f"Info on {guild.name}", color=discord.Color.blue())
        embed.set_thumbnail(url=guild.icon.url)
        embed.add_field(name="ID", value=guild.id)
        embed.add_field(name="Owner", value=guild.owner.mention)
        embed.add_field(name="Created On", value=guild.created_at.strftime("%b %d, %Y"))
        embed.add_field(name="Members", value=guild.member_count)
        embed.add_field(name="Channels", value=len(guild.channels))
        embed.add_field(name="Roles", value=len(guild.roles))
        await ctx.send(embed=embed)

    @commands.command(name="message-search")
    @is_warden()
    async def message_search(self, ctx, phrase: str, limit: int = 100):
        await ctx.send(f"Searching for '{phrase}' in the last {limit} messages...")
        found_messages = []
        async for message in ctx.channel.history(limit=limit):
            if phrase.lower() in message.content.lower():
                found_messages.append(f"**{message.author.name}**: {message.content[:50]}...")
        
        if not found_messages:
            return await ctx.send("No messages found.")
        
        await ctx.send("\n".join(found_messages[:10]))

# --- HELP COMMAND ---
class Help(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="help")
    async def help(self, ctx):
        embed = discord.Embed(title="Warden Bot Commands", description="Commands for server control and information.", color=discord.Color.dark_grey())
        embed.add_field(name="Tyrant (Control)", value="`!nuke-channel`, `!nuke-all-channels`, `!jail`, `!unjail`, `!purge`, `!kick`, `!ban`, `!nickname-all`, `!slowmode-all`", inline=False)
        embed.add_field(name="Trickster (Annoyance)", value="`!mock`, `!echo`, `!ghost-ping`, `!spam-emoji`, `!nick-spam`", inline=False)
        embed.add_field(name="Oracle (Info)", value="`!whois`, `!server-info`, `!message-search`", inline=False)
        await ctx.send(embed=embed)

# --- FINAL SETUP ---
async def setup():
    await bot.add_cog(Tyrant(bot))
    await bot.add_cog(Trickster(bot))
    await bot.add_cog(Oracle(bot))
    await bot.add_cog(Help(bot))

@bot.before_invoke
async def before_invoke(ctx):
    if not any(role.id == WARDEN_ROLE_ID for role in ctx.author.roles):
        await ctx.send("You do not have the required role to use this command.")
        raise commands.CheckFailure("Warden role required.")

if __name__ == "__main__":
    asyncio.run(setup())
    bot.run(BOT_TOKEN)
