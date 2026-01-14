import os
from dotenv import load_dotenv
from pymongo import MongoClient
import discord
from discord.ext import commands

# Load environment variables from .env file
load_dotenv()

# --- CONFIGURATION ---
# We use 'int()' because environment variables are always strings
OWNER_ID = int(os.getenv("OWNER_ID", 0))
SUPPORT_SERVER_ID = int(os.getenv("SUPPORT_SERVER_ID", 0))
PREMIUM_ROLE_ID = int(os.getenv("PREMIUM_ROLE_ID", 0))
MONGO_URI = os.getenv("MONGO_URI")

# --- DATABASE CONNECTION ---
def get_db():
    """Returns the MongoDB database object."""
    if not MONGO_URI:
        print("❌ Error: MONGO_URI is missing in .env file")
        return None
        
    client = MongoClient(MONGO_URI)
    return client["gumit_bot"]

# --- CHECKS ---
def check_premium_status(user_id):
    if user_id == OWNER_ID:
        return True
    
    db = get_db()
    # MongoDB: Check if document exists with _id equal to user_id
    result = db.premium_users.find_one({"_id": user_id})
    return result is not None

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