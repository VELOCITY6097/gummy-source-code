import discord
from discord.ext import commands
from datetime import datetime
from utils import get_db

class Events(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def get_log_channel(self, guild):
        """Fetches the log channel ID from the database config."""
        db = get_db()
        config = db.guild_configs.find_one({"_id": guild.id})
        if config and "log_channel" in config:
            return guild.get_channel(config["log_channel"])
        return None

    @commands.Cog.listener()
    async def on_message_delete(self, message):
        if message.author.bot or not message.guild: return
        
        log_channel = await self.get_log_channel(message.guild)
        if not log_channel: return

        embed = discord.Embed(title="🗑️ Message Deleted", color=discord.Color.red(), timestamp=datetime.now())
        embed.set_author(name=message.author.name, icon_url=message.author.avatar.url if message.author.avatar else None)
        embed.add_field(name="Channel", value=message.channel.mention, inline=True)
        embed.add_field(name="Content", value=message.content or "[Image/File]", inline=False)
        
        await log_channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_message_edit(self, before, after):
        if before.author.bot or not before.guild: return
        if before.content == after.content: return
        
        log_channel = await self.get_log_channel(before.guild)
        if not log_channel: return

        embed = discord.Embed(title="✏️ Message Edited", color=discord.Color.orange(), timestamp=datetime.now())
        embed.add_field(name="Channel", value=before.channel.mention, inline=True)
        embed.add_field(name="Before", value=before.content[:1024] or "[Empty]", inline=False)
        embed.add_field(name="After", value=after.content[:1024] or "[Empty]", inline=False)
        
        await log_channel.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Events(bot))