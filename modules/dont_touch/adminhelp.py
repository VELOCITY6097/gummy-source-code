import discord
from discord.ext import commands
import os
from dotenv import load_dotenv
from pathlib import Path

# Load configuration
env_path = Path(__file__).parent.parent.parent / '.env'
load_dotenv(dotenv_path=env_path)

OWNER_ID = int(os.getenv("OWNER_ID", 0))
SUPPORT_SERVER_ID = int(os.getenv("SUPPORT_SERVER_ID", 0))

class AdminHelp(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def is_authorized(self, ctx):
        # 1. Check Server
        if not ctx.guild or ctx.guild.id != SUPPORT_SERVER_ID: 
            return False
        # 2. Check Owner
        if ctx.author.id != OWNER_ID: 
            return False
        return True

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot: return
        
        # Listen strictly for ^help
        if message.content.strip().lower() == "^help":
            ctx = await self.bot.get_context(message)
            
            # Silent Skip if not authorized
            if not self.is_authorized(ctx): 
                return

            embed = discord.Embed(
                title="🛡️ Gumit Owner Control Panel",
                description="**Confidential:** List of administrative overrides and controls.\n*These commands only work in the Support Server.*",
                color=discord.Color.gold()
            )
            embed.set_thumbnail(url=self.bot.user.avatar.url if self.bot.user.avatar else None)
            
            # Section 1: System Control (^)
            embed.add_field(
                name="🔧 System Internals (Prefix: `^`)",
                value=(
                    "**`^maintain`**\n"
                    "Opens the Maintenance Dashboard. Use this to lock the bot to DND and broadcast updates to all servers.\n\n"
                    "**`^status`**\n"
                    "Opens the Status Manager. Configure rich presence, set custom activities, or start the auto-randomizer loop.\n\n"
                    "**`^system`**\n"
                    "Runs a deep health check. Scans all module files vs loaded extensions to find crashed cogs.\n\n"
                    "**`^uptime`**\n"
                    "Displays current session uptime and API latency."
                ),
                inline=False
            )
            
            # Section 2: Billing & Users (!)
            embed.add_field(
                name="💸 Billing & Management (Standard Prefix)",
                value=(
                    "**`/genkey`** (or `!genkey`)\n"
                    "Generate a one-time Premium License Key to DM to a buyer.\n\n"
                    "**`/deactivate_key [key]`**\n"
                    "Delete/Ban a specific license key preventing its future use.\n\n"
                    "**`/revoke_premium [user]`**\n"
                    "Forcefully remove Premium status from a user ID."
                ),
                inline=False
            )
            
            embed.set_footer(text=f"Logged in as Owner • Server ID: {SUPPORT_SERVER_ID}")
            
            await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(AdminHelp(bot))