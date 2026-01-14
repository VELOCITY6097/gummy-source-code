import discord
from discord.ext import commands
from discord import ui
import asyncio
import os
from dotenv import load_dotenv
from pathlib import Path
from utils import get_db

# Load configuration directly from environment variables
env_path = Path(__file__).parent.parent.parent / '.env'
load_dotenv(dotenv_path=env_path)

OWNER_ID = int(os.getenv("OWNER_ID", 0))
SUPPORT_SERVER_ID = int(os.getenv("SUPPORT_SERVER_ID", 0))

# Your Specific Animated Maintenance Images
MAINTENANCE_IMG = "https://cdn.dribbble.com/userupload/23395972/file/original-ff14fcab6789bf4f22e0f260ee71a603.gif"
COMPLETION_IMG = "https://i.giphy.com/kLOkqcrdC5mrCE7k7G.webp"

class BroadcastUtils:
    """Helper to handle safe global broadcasting."""
    @staticmethod
    async def global_broadcast(bot, embed, interaction):
        status_msg = await interaction.followup.send(f"📡 **Broadcasting to {len(bot.guilds)} servers...**\n*This process is throttled to prevent rate limits.*")
        
        success_count = 0
        fail_count = 0
        
        for guild in bot.guilds:
            # 1. Find best channel
            target_channel = guild.system_channel
            if not target_channel:
                for c in guild.text_channels:
                    if c.permissions_for(guild.me).send_messages and c.permissions_for(guild.me).embed_links:
                        if c.name in ["announcements", "news", "updates", "general", "chat"]:
                            target_channel = c
                            break
                if not target_channel:
                    for c in guild.text_channels:
                        if c.permissions_for(guild.me).send_messages:
                            target_channel = c
                            break
            
            # 2. Send if channel found
            if target_channel:
                try:
                    await target_channel.send(embed=embed)
                    success_count += 1
                    # 🛡️ RATE LIMIT PROTECTION: Sleep 2.5s between servers
                    await asyncio.sleep(2.5) 
                except:
                    fail_count += 1
            else:
                fail_count += 1
                
        await interaction.followup.send(f"✅ **Broadcast Complete.**\nSent: {success_count}\nFailed: {fail_count}", ephemeral=True)

class MaintenanceModal(ui.Modal, title="📢 Start Maintenance"):
    duration = ui.TextInput(
        label="Estimated Duration", 
        placeholder="e.g., 2 hours", 
        default="2 hours", 
        required=True
    )
    
    update_reason = ui.TextInput(
        label="Update Details / Reason", 
        style=discord.TextStyle.paragraph, 
        placeholder="Briefly describe the update...", 
        required=False
    )
    
    image_url = ui.TextInput(
        label="Embed Image URL", 
        placeholder="https://...", 
        default=MAINTENANCE_IMG, 
        required=False
    )

    def __init__(self, bot):
        super().__init__()
        self.bot = bot

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        # --- CRITICAL FIX: STOP STATUS LOOP ---
        # 1. Save state to DB
        db = get_db()
        db.bot_settings.update_one(
            {"_id": "maintenance_mode"}, 
            {"$set": {"active": True}}, 
            upsert=True
        )
        self.bot.maintenance_mode = True

        # 2. Stop the randomizer so it doesn't overwrite DND
        status_cog = self.bot.get_cog("Status")
        if status_cog and status_cog.status_loop.is_running():
            status_cog.status_loop.cancel()
            print("🛑 Maintenance started: Status Randomizer paused.")
        # --------------------------------------

        reason_text = self.update_reason.value if self.update_reason.value.strip() else "System upgrades and performance stability improvements."
        duration_text = self.duration.value
        img = self.image_url.value if self.image_url.value.strip() else MAINTENANCE_IMG

        # Your Custom Embed Style
        embed = discord.Embed(
            title="🚧 SYSTEM MAINTENANCE IN PROGRESS 🚧",
            description=(
                "# ⚠️ SERVICE ANNOUNCEMENT\n"
                "### The bot is currently undergoing critical maintenance.\n\n"
                "**🛑 Status:** `🔴 SYSTEM OFFLINE / UNRESPONSIVE`\n"
                f"**⏳ Estimated Down Time:** `{duration_text}`\n\n"
                "**📋 Update Log:**\n"
                f"```fix\n{reason_text}\n```"
            ),
            color=discord.Color.from_rgb(255, 69, 58) 
        )
        embed.set_image(url=img)
        embed.set_footer(text="Thank you for your patience.")
        embed.set_thumbnail(url=interaction.client.user.avatar.url if interaction.client.user.avatar else None)

        await self.bot.change_presence(status=discord.Status.dnd, activity=discord.Activity(type=discord.ActivityType.watching, name="System Updates"))
        
        await BroadcastUtils.global_broadcast(self.bot, embed, interaction)

class EndMaintenanceModal(ui.Modal, title="✅ End Maintenance"):
    message = ui.TextInput(
        label="Completion Message", 
        style=discord.TextStyle.paragraph, 
        default="All systems are operational. Thank you for your patience.", 
        required=True
    )
    
    image_url = ui.TextInput(
        label="Embed Image URL", 
        placeholder="https://...", 
        default=COMPLETION_IMG,
        required=False
    )

    def __init__(self, bot):
        super().__init__()
        self.bot = bot

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        # --- CRITICAL FIX: RESTART STATUS LOOP ---
        # 1. Update DB
        db = get_db()
        db.bot_settings.update_one(
            {"_id": "maintenance_mode"}, 
            {"$set": {"active": False}}, 
            upsert=True
        )
        self.bot.maintenance_mode = False

        # 2. Restart the randomizer
        status_cog = self.bot.get_cog("Status")
        if status_cog and not status_cog.status_loop.is_running():
            status_cog.status_loop.start()
            print("🟢 Maintenance ended: Status Randomizer restarted.")
        # -----------------------------------------

        img = self.image_url.value if self.image_url.value.strip() else COMPLETION_IMG

        # Your Custom Embed Style
        embed = discord.Embed(
            title="✅ MAINTENANCE COMPLETE",
            description=(
                "# 🟢 SYSTEMS ONLINE\n"
                "### Maintenance has concluded successfully.\n\n"
                f"{self.message.value}\n\n"
                "**✨ Status:** `🟢 FULLY OPERATIONAL`"
            ),
            color=discord.Color.green()
        )
        embed.set_image(url=img)
        embed.set_footer(text="Gumit is back online!")
        embed.set_thumbnail(url=interaction.client.user.avatar.url if interaction.client.user.avatar else None)

        await self.bot.change_presence(status=discord.Status.online, activity=discord.Activity(type=discord.ActivityType.listening, name="/help"))
        
        await BroadcastUtils.global_broadcast(self.bot, embed, interaction)

class MaintenanceView(ui.View):
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot

    @ui.button(label="START Maintenance", style=discord.ButtonStyle.danger, emoji="🚧")
    async def start_m(self, interaction: discord.Interaction, button: ui.Button):
        if interaction.user.id != OWNER_ID:
            return await interaction.response.send_message("❌ Unauthorized.", ephemeral=True)
        await interaction.response.send_modal(MaintenanceModal(self.bot))

    @ui.button(label="END Maintenance", style=discord.ButtonStyle.success, emoji="✅")
    async def end_m(self, interaction: discord.Interaction, button: ui.Button):
        if interaction.user.id != OWNER_ID:
            return await interaction.response.send_message("❌ Unauthorized.", ephemeral=True)
        await interaction.response.send_modal(EndMaintenanceModal(self.bot))

class Maintenance(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.bot.maintenance_mode = False

    async def cog_load(self):
        # Restore state on bot restart
        try:
            db = get_db()
            data = db.bot_settings.find_one({"_id": "maintenance_mode"})
            if data and data.get("active"):
                self.bot.maintenance_mode = True
                print("⚠️  Maintenance Mode Active on Startup")
                await self.bot.change_presence(status=discord.Status.dnd, activity=discord.Activity(type=discord.ActivityType.watching, name="System Updates"))
        except: pass

    def is_authorized(self, ctx):
        if ctx.guild.id != SUPPORT_SERVER_ID: return False
        if ctx.author.id != OWNER_ID: return False
        return True

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot: return
        
        if message.content.startswith("^maintain"):
            ctx = await self.bot.get_context(message)
            if not self.is_authorized(ctx): return 

            embed = discord.Embed(
                title="🔧 Maintenance Control Center",
                description="**Restricted Access:** Owner Only.\nSelect an action below.",
                color=discord.Color.dark_theme()
            )
            await ctx.send(embed=embed, view=MaintenanceView(self.bot))

async def setup(bot):
    await bot.add_cog(Maintenance(bot))