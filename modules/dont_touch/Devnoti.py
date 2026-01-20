import discord
from discord.ext import commands
import os
import traceback
import sys
from datetime import datetime
from dotenv import load_dotenv
from pathlib import Path

# --- CONFIGURATION ---
# Load environment variables to find the Owner ID
env_path = Path(__file__).parent.parent.parent / '.env'
load_dotenv(dotenv_path=env_path)

OWNER_ID = int(os.getenv("OWNER_ID", 0))

# Path to check for modules
COGS_DIR = "./modules/cogs" 
DONT_TOUCH_DIR = "./modules/dont_touch"

class DevNotifications(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.startup_checked = False

    async def send_dev_alert(self, title, description, color=discord.Color.red()):
        """Helper to DM the owner."""
        if not OWNER_ID:
            print("[DevNoti] ❌ OWNER_ID not found in .env, cannot send DM.")
            return

        try:
            owner = await self.bot.fetch_user(OWNER_ID)
            embed = discord.Embed(
                title=title,
                description=description,
                color=color,
                timestamp=datetime.now()
            )
            embed.set_footer(text=" Developer System Notification")
            await owner.send(embed=embed)
        except Exception as e:
            print(f"[DevNoti] ❌ Failed to DM Owner: {e}")

    # ─── 1. STARTUP INTEGRITY CHECK ─────────────────────────
    @commands.Cog.listener()
    async def on_ready(self):
        if self.startup_checked:
            return
        
        print("[DevNoti] 🔍 Running startup integrity check...")
        
        # Get list of all .py files in your module folders
        physical_files = []
        for directory in [COGS_DIR, DONT_TOUCH_DIR]:
            if os.path.exists(directory):
                for filename in os.listdir(directory):
                    if filename.endswith(".py") and not filename.startswith("__"):
                        # Convert path to python module format (e.g., modules.cogs.status_page)
                        clean_dir = directory.replace("./", "").replace("/", ".")
                        module_name = f"{clean_dir}.{filename[:-3]}"
                        physical_files.append(module_name)

        # Compare with what is actually loaded in the bot
        loaded_extensions = list(self.bot.extensions.keys())
        
        failed_modules = []
        for file in physical_files:
            if file not in loaded_extensions:
                # Exclude this file itself if it loaded (just in case)
                if "devnoti" not in file:
                    failed_modules.append(file)

        if failed_modules:
            # Alert the owner!
            desc = "**The following modules failed to load on startup:**\n```diff\n"
            for fail in failed_modules:
                desc += f"- {fail}\n"
            desc += "```\n*Check your console for syntax errors.*"
            
            await self.send_dev_alert("⚠️ Startup Integrity Failure", desc, discord.Color.orange())
            print(f"[DevNoti] ⚠️ Found {len(failed_modules)} failed modules.")
        else:
            print("[DevNoti] ✅ All modules loaded successfully.")
        
        self.startup_checked = True

    # ─── 2. RUNTIME ERROR REPORTER ──────────────────────────
    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        # Ignore expected errors (user inputs, cooldowns, etc)
        ignored = (commands.CommandNotFound, commands.MissingRequiredArgument, 
                   commands.BadArgument, commands.CheckFailure, commands.CommandOnCooldown)
        
        if isinstance(error, ignored):
            return

        # If it's a real crash (InvokeError), extract the traceback
        if isinstance(error, commands.CommandInvokeError):
            error = error.original

        # Format the error traceback
        tb_lines = traceback.format_exception(type(error), error, error.__traceback__)
        tb_text = "".join(tb_lines)
        
        # Truncate if too long for Discord
        if len(tb_text) > 1000:
            tb_text = tb_text[-1000:]

        # Send Alert
        desc = (
            f"**Command:** `{ctx.command}`\n"
            f"**User:** `{ctx.author}` ({ctx.author.id})\n"
            f"**Channel:** `{ctx.channel}` in `{ctx.guild}`\n\n"
            f"**Traceback:**\n```python\n{tb_text}\n```"
        )
        
        await self.send_dev_alert("🚨 Runtime Command Error", desc)
        
        # Also notify user vaguely that something broke
        try:
            await ctx.send("❌ **Internal Error:** An automated report has been sent to the developer.", delete_after=10)
        except:
            pass

    # ─── DEBUG COMMAND ──────────────────────────────────────
    @commands.command()
    @commands.is_owner()
    async def testfail(self, ctx):
        """Forces an error to test the notification system."""
        await ctx.send("💥 **Causing a deliberate error...**")
        # This will raise a ZeroDivisionError, triggering on_command_error
        x = 1 / 0 

async def setup(bot):
    await bot.add_cog(DevNotifications(bot))