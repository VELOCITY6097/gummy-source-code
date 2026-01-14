import discord
from discord.ext import commands, tasks
import asyncio
from datetime import datetime
import re
from utils import get_db

class General(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.check_temp_roles.start()

    # --- EVENTS ---
    @commands.Cog.listener()
    async def on_message_delete(self, message):
        if message.author.bot: return
        self.bot.snipe_cache[message.channel.id] = (message.content, message.author, datetime.now())

    @commands.Cog.listener()
    async def on_member_join(self, member):
        cid = self.bot.welcome_cache.get(member.guild.id)
        if cid:
            channel = member.guild.get_channel(cid)
            if channel:
                await channel.send(f"Welcome {member.mention} to {member.guild.name}!")

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot: return
        if message.author.id in self.bot.afk_cache:
            del self.bot.afk_cache[message.author.id]
            await message.channel.send(f"👋 Welcome back {message.author.mention}, I removed your AFK.", delete_after=5)
        for mention in message.mentions:
            if mention.id in self.bot.afk_cache:
                await message.channel.send(f"💤 **{mention.name}** is AFK: {self.bot.afk_cache[mention.id]}")

    # --- COMMANDS ---

    @commands.hybrid_command(name="setwelcome", description="Set welcome channel.")
    @commands.has_permissions(administrator=True)
    async def setwelcome(self, ctx, channel: discord.TextChannel):
        db = get_db()
        db.welcome_configs.update_one(
            {"_id": ctx.guild.id},
            {"$set": {"channel_id": channel.id}},
            upsert=True
        )
        self.bot.welcome_cache[ctx.guild.id] = channel.id
        await ctx.send(f"✅ Welcomes set to {channel.mention}")

    @commands.hybrid_command(name="setprefix", description="Change server prefix.")
    @commands.has_permissions(administrator=True)
    async def setprefix(self, ctx, new_prefix: str):
        db = get_db()
        db.guild_configs.update_one(
            {"_id": ctx.guild.id},
            {"$set": {"prefix": new_prefix}},
            upsert=True
        )
        self.bot.prefix_cache[ctx.guild.id] = new_prefix
        await ctx.send(f"✅ Prefix changed to `{new_prefix}`")

    @commands.hybrid_command(name="snipe", description="Recover last deleted message.")
    async def snipe(self, ctx):
        data = self.bot.snipe_cache.get(ctx.channel.id)
        if not data: return await ctx.send("❌ Nothing to snipe.")
        content, author, time = data
        embed = discord.Embed(description=content, color=discord.Color.red(), timestamp=time)
        embed.set_author(name=author.name, icon_url=author.avatar.url if author.avatar else None)
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="afk", description="Set AFK status.")
    async def afk(self, ctx, *, reason: str = "AFK"):
        self.bot.afk_cache[ctx.author.id] = reason
        await ctx.send(f"💤 Set AFK: {reason}")

    @commands.hybrid_command(name="temprole", description="Give role temporarily.")
    @commands.has_permissions(manage_roles=True)
    async def temprole(self, ctx, member: discord.Member, role: discord.Role, duration: str):
        amount = int(re.findall(r'\d+', duration)[0])
        unit = re.findall(r'[a-zA-Z]+', duration)[0].lower()
        seconds = amount * (60 if unit == 'm' else 3600 if unit == 'h' else 86400)
        
        await member.add_roles(role)
        expiry = datetime.now().timestamp() + seconds
        
        db = get_db()
        db.temp_roles.insert_one({
            "guild_id": ctx.guild.id,
            "user_id": member.id,
            "role_id": role.id,
            "expiry": expiry
        })
        await ctx.send(f"✅ Gave {role.name} for {duration}")

    # --- TASKS ---
    @tasks.loop(seconds=60)
    async def check_temp_roles(self):
        db = get_db()
        now = datetime.now().timestamp()
        
        # Find expired roles
        expired_cursor = db.temp_roles.find({"expiry": {"$lte": now}})
        
        for doc in expired_cursor:
            try:
                guild = self.bot.get_guild(doc["guild_id"])
                if guild:
                    await guild.get_member(doc["user_id"]).remove_roles(guild.get_role(doc["role_id"]))
            except: pass
            
            # Delete processed
            db.temp_roles.delete_one({"_id": doc["_id"]})

async def setup(bot):
    await bot.add_cog(General(bot))