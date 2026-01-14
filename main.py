import discord
from discord.ext import commands
import asyncio
from datetime import datetime
import os
import logging
import sys
from dotenv import load_dotenv
from utils import get_db, load_premium_cache  # <--- Imported load_premium_cache

# --- LOGGING CONFIGURATION ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.FileHandler("bot.log", encoding='utf-8', mode='a'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("Main")

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
DEFAULT_PREFIX = "!"

async def get_prefix(bot, message):
    if not message.guild:
        return DEFAULT_PREFIX
    return bot.prefix_cache.get(message.guild.id, DEFAULT_PREFIX)

class GumitBot(commands.AutoShardedBot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True 
        super().__init__(command_prefix=get_prefix, intents=intents, help_command=None)
        
        # --- CACHES ---
        self.sticky_cache = {}        
        self.last_sticky_ids = {}     
        self.sticky_locks = {}
        self.sticky_cooldowns = {}         
        self.prefix_cache = {} 
        self.welcome_cache = {}
        self.snipe_cache = {} 
        self.afk_cache = {} 
        self.sticky_roles_enabled = set()
        self.start_time = datetime.now()

    async def setup_hook(self):
        self.load_cache()
        
        # --- MODULE LOADER ---
        target_folders = ['cogs', 'dont_touch', 'premium']
        
        logger.info("--- STARTING MODULE LOAD ---")
        
        for subfolder in target_folders:
            # Use safe path joining
            dir_path = os.path.join('./modules', subfolder)
            
            if not os.path.exists(dir_path):
                logger.warning(f"Directory {dir_path} missing.")
                continue

            # List .py files
            files = [f for f in os.listdir(dir_path) if f.endswith('.py') and not f.startswith('__')]
            
            for filename in files:
                try:
                    # e.g. modules.cogs.general
                    ext_path = f'modules.{subfolder}.{filename[:-3]}'
                    await self.load_extension(ext_path)
                    logger.info(f"✅ Loaded: {filename}")
                except Exception as e:
                    logger.error(f"❌ Failed to load {filename}: {e}")

        logger.info("--- SYSTEM READY ---")
        await self.tree.sync()

    def load_cache(self):
        """Loads all persistent data from MongoDB into memory."""
        db = get_db()
        if db is None: return

        # 1. Load Premium Users (NEW: Performance Fix)
        load_premium_cache()

        # 2. Load Sticky Messages (Restored)
        for doc in db.sticky_messages.find():
            self.sticky_cache[doc["_id"]] = doc
            self.sticky_locks[doc["_id"]] = asyncio.Lock()

        # 3. Load Prefixes
        for doc in db.guild_configs.find():
            self.prefix_cache[doc["_id"]] = doc.get("prefix", DEFAULT_PREFIX)

        # 4. Load Welcome Channels
        for doc in db.welcome_configs.find():
            self.welcome_cache[doc["_id"]] = doc["channel_id"]

        # 5. Load Sticky Roles (Restored)
        for doc in db.sticky_roles_config.find():
            if doc.get("enabled"):
                self.sticky_roles_enabled.add(doc["_id"])

        logger.info("📦 MongoDB Data & Caches Loaded")

bot = GumitBot()

@bot.event
async def on_ready():
    logger.info(f'🚀 Logged in as {bot.user} (ID: {bot.user.id})')
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.listening, name="/help"))

if __name__ == "__main__":
    if not TOKEN: 
        logger.critical("DISCORD_TOKEN is missing from .env")
    else: 
        bot.run(TOKEN, log_handler=None)
