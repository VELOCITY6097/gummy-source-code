import discord
from discord.ext import commands
import asyncio
from datetime import datetime
import os
from dotenv import load_dotenv
from utils import get_db

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
        # Enable ANSI colors in Windows CMD
        if os.name == 'nt':
            os.system("")

        self.load_cache()
        
        # --- NEW FOLDER STRUCTURE LOADER (BEAUTIFIED) ---
        target_folders = ['cogs', 'dont_touch', 'premium']
        
        # Stats tracking
        stats = {folder: {'success': 0, 'total': 0} for folder in target_folders}
        failed_cogs = []

        # ANSI Colors for Console
        CYAN = "\033[96m"
        GREEN = "\033[92m"
        RED = "\033[91m"
        YELLOW = "\033[93m"
        GREY = "\033[90m"
        RESET = "\033[0m"
        BOLD = "\033[1m"

        # Fixed Header Alignment (Removed Emojis to ensure straight lines)
        print(f"\n{CYAN}╔══════════════════════════════════════════════════════╗")
        print(f"║          GUMIT BOT MODULE LOADER INITIATED           ║")
        print(f"╚══════════════════════════════════════════════════════╝{RESET}")

        for subfolder in target_folders:
            # UPDATED: Point to 'modules' instead of 'cogs'
            dir_path = os.path.join('./modules', subfolder)
            
            if os.path.exists(dir_path):
                # Sort files for cleaner output
                files = sorted([f for f in os.listdir(dir_path) if f.endswith('.py') and not f.startswith('__')])
                stats[subfolder]['total'] = len(files)
                
                if not files:
                    print(f"{GREY}   📂 {subfolder:<12} (Empty){RESET}")
                    continue

                print(f"{YELLOW}   📂 {subfolder.upper()}{RESET}")

                for filename in files:
                    try:
                        # UPDATED: Import from 'modules' package
                        ext_path = f'modules.{subfolder}.{filename[:-3]}'
                        await self.load_extension(ext_path)
                        stats[subfolder]['success'] += 1
                        print(f"     {GREEN}✅ {filename:<20} {RESET}")
                    except Exception as e:
                        failed_cogs.append((f"{subfolder}/{filename}", str(e)))
                        print(f"     {RED}❌ {filename:<20} -> {e}{RESET}")
            else:
                print(f"{GREY}   ⚠️  Directory './modules/{subfolder}' does not exist.{RESET}")

        # Summary Generation
        print(f"\n{CYAN}══════════════════════ 📊 SUMMARY ══════════════════════{RESET}")
        
        for folder, data in stats.items():
            s = data['success']
            t = data['total']
            
            # Determine status color
            if s == t and t > 0:
                status_icon = f"{GREEN}✔{RESET}"
                status_color = GREEN
            elif s < t:
                status_icon = f"{RED}✖{RESET}"
                status_color = RED
            else:
                status_icon = f"{GREY}-{RESET}"
                status_color = GREY
            
            print(f"   {status_icon} {status_color}{folder:<12}: {s}/{t} Modules Loaded{RESET}")

        print(f"{CYAN}════════════════════════════════════════════════════════{RESET}")

        # Final Status
        if failed_cogs:
            print(f"\n{RED}🚨 FAILED MODULES DETECTED:{RESET}")
            for name, err in failed_cogs:
                print(f"   {RED}❌ {BOLD}{name}{RESET}: {err}")
            print(f"\n{YELLOW}⚠️  Bot started with errors.{RESET}")
        else:
            print(f"\n{GREEN}🚀 ALL SYSTEMS OPERATIONAL. READY TO LAUNCH.{RESET}")
        
        print(f"{CYAN}════════════════════════════════════════════════════════{RESET}\n")

        await self.tree.sync()
        print(f"{GREEN}🌳 Command Tree Synced{RESET}")

    def load_cache(self):
        db = get_db()
        if db is None: return

        # Load Sticky Data
        for doc in db.sticky_messages.find():
            self.sticky_cache[doc["_id"]] = doc
            self.sticky_locks[doc["_id"]] = asyncio.Lock()
            
        for doc in db.guild_configs.find():
            self.prefix_cache[doc["_id"]] = doc["prefix"]

        for doc in db.welcome_configs.find():
            self.welcome_cache[doc["_id"]] = doc["channel_id"]

        # Sticky Roles
        for doc in db.sticky_roles_config.find():
            if doc.get("enabled"):
                self.sticky_roles_enabled.add(doc["_id"])
            
        print("📦 MongoDB Data Loaded")

bot = GumitBot()

@bot.event
async def on_ready():
    print(f'✅ {bot.user} is Online!')
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.listening, name="/help"))

if __name__ == "__main__":
    if not TOKEN: print("❌ Error: DISCORD_TOKEN is missing")
    else: bot.run(TOKEN)