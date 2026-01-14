import os
import logging
from dotenv import load_dotenv
from pymongo import MongoClient
import discord
from discord.ext import commands
import certifi  # <--- Added certifi import

# Load environment variables
load_dotenv()

# --- LOGGING SETUP ---
logger = logging.getLogger("Utils")

# --- CONFIGURATION ---
OWNER_ID = int(os.getenv("OWNER_ID", 0))
SUPPORT_SERVER_ID = int(os.getenv("SUPPORT_SERVER_ID", 0))
PREMIUM_ROLE_ID = int(os.getenv("PREMIUM_ROLE_ID", 0))
MONGO_URI = os.getenv("MONGO_URI")

# --- GLOBAL DATABASE VARIABLES ---
# We store the client here so we don't reconnect every time
_mongo_client = None
_premium_cache = set()

def get_db():
    """
    Returns the MongoDB database object using a singleton connection.
    This prevents 'Max Connection' errors.
    """
    global _mongo_client
    
    if not MONGO_URI:
        logger.critical("❌ MONGO_URI is missing in .env file")
        return None

    if _mongo_client is None:
        try:
            # Added certifi for SSL certificate verification & TLS options
            _mongo_client = MongoClient(
                MONGO_URI, 
                tls=True, 
                tlsCAFile=certifi.where()
            )
            
            # Verify connection works immediately
            _mongo_client.admin.command('ping')
            logger.info("📦 Connected to MongoDB successfully.")
        except Exception as e:
            logger.error(f"❌ Failed to connect to MongoDB: {e}")
            return None
            
    return _mongo_client["gumit_bot"]

# --- CACHE MANAGEMENT ---
def load_premium_cache():
    """Loads all premium user IDs into memory on startup."""
    global _premium_cache
    db = get_db()
    if db is None: return

    try:
        # Fetch only the _id field for all premium users
        cursor = db.premium_users.find({}, {"_id": 1})
        _premium_cache = {doc["_id"] for doc in cursor}
        logger.info(f"💎 Loaded {len(_premium_cache)} premium users into cache.")
    except Exception as e:
        logger.error(f"Failed to load premium cache: {e}")

def add_premium_cache(user_id):
    """Updates cache when a user buys/redeems premium."""
    _premium_cache.add(user_id)

def remove_premium_cache(user_id):
    """Updates cache when premium expires."""
    if user_id in _premium_cache:
        _premium_cache.remove(user_id)

# --- CHECKS ---
def check_premium_status(user_id):
    """Checks cache first (instant), falls back to DB if needed."""
    if user_id == OWNER_ID:
        return True
    
    # 1. Fast Cache Check
    if user_id in _premium_cache:
        return True
    
    # 2. Safety Fallback (Optional: In case cache isn't loaded yet)
    # Usually strictly relying on cache is better for speed, 
    # but we can do a DB check just in case.
    db = get_db()
    if db and db.premium_users.find_one({"_id": user_id}):
        add_premium_cache(user_id)
        return True
        
    return False

class PremiumCog(commands.Cog):
    """
    Any Cog that inherits from this class will automatically 
    require the user to be a Premium member to use ANY command inside it.
    """
    async def cog_check(self, ctx):
        if check_premium_status(ctx.author.id):
            return True
        else:
            embed = discord.Embed(
                title="🔒 Premium Only", 
                description="This feature is locked for **Gumit Gold** members.", 
                color=discord.Color.gold()
            )
            await ctx.send(embed=embed, ephemeral=True)
            return False
