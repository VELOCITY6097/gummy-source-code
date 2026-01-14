import discord
from discord.ext import commands
import os
import time
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

# Load env from parent directory
env_path = Path(__file__).parent.parent.parent / '.env'
load_dotenv(dotenv_path=env_path)
OWNER_ID = int(os.getenv("OWNER_ID", 0))

class Diagnostics(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def is_owner_check(self, user_id):
        return user_id == OWNER_ID

    def get_uptime_str(self):
        """Calculates the time delta since bot start."""
        if hasattr(self.bot, 'start_time'):
            delta = datetime.now() - self.bot.start_time
            days = delta.days
            hours, remainder = divmod(delta.seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            return f"{days}d {hours}h {minutes}m {seconds}s"
        return "Unknown"

    # --- SHARED LOGIC ---

    async def send_uptime_embed(self, sender_func, is_ephemeral=False):
        latency = round(self.bot.latency * 1000)
        embed = discord.Embed(
            title="⏱️ System Uptime",
            description=f"**Running for:** `{self.get_uptime_str()}`",
            color=discord.Color.green()
        )
        embed.add_field(name="📶 Ping", value=f"`{latency}ms`", inline=True)
        embed.set_footer(text="Gumit Systems")
        
        if is_ephemeral:
            await sender_func(embed=embed, ephemeral=True)
        else:
            await sender_func(embed=embed)

    async def send_system_embed(self, sender_func, is_ephemeral=False):
        embed = discord.Embed(
            title="🩺 System Health Check",
            color=discord.Color.blurple(),
            timestamp=datetime.now()
        )

        # Module Scan - UPDATED FOR 'modules' FOLDER
        target_folders = ['cogs', 'dont_touch', 'premium']
        found_files = []
        
        for subfolder in target_folders:
            dir_path = os.path.join('./modules', subfolder)
            if os.path.exists(dir_path):
                for filename in os.listdir(dir_path):
                    if filename.endswith('.py') and not filename.startswith('__'):
                        # Correct import path format: modules.subfolder.filename
                        path = f"modules.{subfolder}.{filename[:-3]}"
                        found_files.append(path)
        
        loaded_extensions = list(self.bot.extensions.keys())
        cog_report = ""
        healthy_count = 0
        
        for path in found_files:
            if path in loaded_extensions:
                cog_report += f"✅ `{path}`\n"
                healthy_count += 1
            else:
                cog_report += f"🔴 `{path}` **(FAILED)**\n"

        embed.add_field(name=f"🧩 Modules ({healthy_count}/{len(found_files)})", value=cog_report or "No modules found.", inline=False)
        embed.add_field(name="⏱️ Uptime", value=f"`{self.get_uptime_str()}`", inline=True)
        embed.add_field(name="📶 Latency", value=f"`{round(self.bot.latency * 1000)}ms`", inline=True)
        embed.add_field(name="🏰 Guilds", value=str(len(self.bot.guilds)), inline=True)
        embed.add_field(name="👥 Users", value=str(len(self.bot.users)), inline=True)

        if is_ephemeral:
            await sender_func(embed=embed, ephemeral=True)
        else:
            await sender_func(embed=embed)

    # --- HYBRID COMMANDS (Slash support) ---

    @commands.hybrid_command(name="uptime", description="Check system uptime (Owner Only).")
    async def uptime_cmd(self, ctx):
        if not self.is_owner_check(ctx.author.id):
            msg = "❌ **Access Denied:** Owner Only."
            return await ctx.send(msg, ephemeral=True) if ctx.interaction else await ctx.send(msg)

        if ctx.interaction:
            await ctx.defer(ephemeral=True)
            await self.send_uptime_embed(ctx.send, is_ephemeral=True)
        else:
            try:
                await ctx.message.delete()
                await self.send_uptime_embed(ctx.author.send, is_ephemeral=False)
            except discord.Forbidden:
                await ctx.send("❌ Enable DMs to see private stats.", delete_after=5)

    @commands.hybrid_command(name="system", description="Run diagnostics (Owner Only).")
    async def system_cmd(self, ctx):
        if not self.is_owner_check(ctx.author.id):
            msg = "❌ **Access Denied:** Owner Only."
            return await ctx.send(msg, ephemeral=True) if ctx.interaction else await ctx.send(msg)

        if ctx.interaction:
            await ctx.defer(ephemeral=True)
            await self.send_system_embed(ctx.send, is_ephemeral=True)
        else:
            try:
                await ctx.message.delete()
                await self.send_system_embed(ctx.author.send, is_ephemeral=False)
            except discord.Forbidden:
                await ctx.send("❌ Enable DMs to see private diagnostics.", delete_after=5)

    # --- PREFIX OVERRIDE LISTENER (Forces ^ support) ---

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot: return
        
        # Strict Owner Check before processing
        if message.author.id != OWNER_ID: return

        content = message.content.lower().strip()

        if content == "^uptime":
            try:
                await message.delete()
                await self.send_uptime_embed(message.author.send, is_ephemeral=False)
            except discord.Forbidden:
                pass 
        
        elif content == "^system":
            try:
                await message.delete()
                await self.send_system_embed(message.author.send, is_ephemeral=False)
            except discord.Forbidden:
                pass

async def setup(bot):
    await bot.add_cog(Diagnostics(bot))