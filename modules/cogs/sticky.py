import discord
from discord.ext import commands
from discord import app_commands, ui
import asyncio
import time
from utils import get_db

# --- MODALS (POPUPS) ---

class StickyEmbedModal(ui.Modal, title="Configure Sticky Embed"):
    # Define Form Fields
    embed_title = ui.TextInput(label="Title", placeholder="e.g., Server Rules", required=False)
    description = ui.TextInput(label="Description (Body)", style=discord.TextStyle.paragraph, placeholder="Type your message here...", required=True)
    color = ui.TextInput(label="Color (Hex or Name)", placeholder="e.g., #FF0000 or red or blue", required=False, max_length=20)
    image_url = ui.TextInput(label="Main Image URL (Bottom)", placeholder="https://example.com/image.png", required=False)
    thumbnail_url = ui.TextInput(label="Thumbnail URL (Top Right)", placeholder="https://example.com/icon.png", required=False)

    def __init__(self, bot, channel):
        super().__init__()
        self.bot = bot
        self.channel = channel

    async def on_submit(self, interaction: discord.Interaction):
        # Save Data
        sticky_data = {
            "type": "embed",
            "title": self.embed_title.value,
            "description": self.description.value,
            "color": self.color.value,
            "image": self.image_url.value,
            "thumbnail": self.thumbnail_url.value
        }
        
        await save_and_stick(self.bot, interaction, self.channel, sticky_data)

class StickyTextModal(ui.Modal, title="Configure Sticky Text"):
    content = ui.TextInput(label="Message Content", style=discord.TextStyle.paragraph, placeholder="Type your sticky message here...", required=True)

    def __init__(self, bot, channel):
        super().__init__()
        self.bot = bot
        self.channel = channel

    async def on_submit(self, interaction: discord.Interaction):
        sticky_data = {
            "type": "text",
            "content": self.content.value
        }
        await save_and_stick(self.bot, interaction, self.channel, sticky_data)

# --- VIEW (BUTTONS) ---

class StickyTypeView(ui.View):
    def __init__(self, bot, channel):
        super().__init__()
        self.bot = bot
        self.channel = channel

    @ui.button(label="Simple Text", style=discord.ButtonStyle.secondary, emoji="📝")
    async def text_btn(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_modal(StickyTextModal(self.bot, self.channel))

    @ui.button(label="Professional Embed", style=discord.ButtonStyle.primary, emoji="🎨")
    async def embed_btn(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_modal(StickyEmbedModal(self.bot, self.channel))

# --- HELPER FUNCTIONS ---

async def save_and_stick(bot, interaction, channel, data):
    db = get_db()
    # Save to MongoDB
    db.sticky_messages.update_one(
        {"_id": channel.id}, 
        {"$set": data}, 
        upsert=True
    )
    
    # Update Cache
    bot.sticky_cache[channel.id] = data
    if channel.id not in bot.sticky_locks: 
        bot.sticky_locks[channel.id] = asyncio.Lock()
    
    # Send Confirmation
    await interaction.response.send_message(f"✅ Sticky message updated in {channel.mention}!", ephemeral=True)
    
    # Trigger first message immediately
    await trigger_sticky(bot, channel.id)

def get_discord_color(color_input):
    if not color_input: return discord.Color.teal()
    
    # Try Hex
    if color_input.startswith("#"):
        try: return discord.Color(int(color_input.strip("#"), 16))
        except: pass
        
    # Try Names
    color_input = color_input.lower()
    colors = {
        "red": discord.Color.red(),
        "blue": discord.Color.blue(),
        "green": discord.Color.green(),
        "gold": discord.Color.gold(),
        "purple": discord.Color.purple(),
        "orange": discord.Color.orange(),
        "black": discord.Color.default()
    }
    return colors.get(color_input, discord.Color.teal())

async def trigger_sticky(bot, channel_id):
    channel = bot.get_channel(channel_id)
    if not channel: return
    
    data = bot.sticky_cache.get(channel_id)
    if not data: return

    # --- RATE LIMIT CHECK ---
    # Don't stick if we sent one in the last 6 seconds
    now = time.time()
    last_sent = bot.sticky_cooldowns.get(channel_id, 0)
    if now - last_sent < 6:
        return 
    
    bot.sticky_cooldowns[channel_id] = now # Update time

    async with bot.sticky_locks[channel_id]:
        try:
            # 1. Delete Old Message
            if channel_id in bot.last_sticky_ids:
                try:
                    old_msg = await channel.fetch_message(bot.last_sticky_ids[channel_id])
                    await old_msg.delete()
                except (discord.NotFound, discord.Forbidden):
                    pass # Message already gone
            
            # 2. Prepare New Message
            if data.get("type") == "embed":
                embed = discord.Embed(
                    title=data.get("title"), 
                    description=data.get("description"), 
                    color=get_discord_color(data.get("color"))
                )
                
                if data.get("image"):
                    embed.set_image(url=data.get("image"))
                if data.get("thumbnail"):
                    embed.set_thumbnail(url=data.get("thumbnail"))
                    
                embed.set_footer(text="📌 Sticky Message")
                new_msg = await channel.send(embed=embed)
            else:
                # Text Mode - Sending as PLAIN TEXT
                content = data.get("content")
                # We add a small bold header so it still looks distinct, 
                # but it is NOT an embed object.
                msg_content = f"__**📌 GuM It Message:**__\n{content}"
                new_msg = await channel.send(msg_content)

            # 3. Save ID
            bot.last_sticky_ids[channel_id] = new_msg.id
            
        except discord.Forbidden:
            # Bot lost permissions, remove from cache to stop errors
            print(f"❌ Lost permissions in {channel_id}, disabling sticky.")
            del bot.sticky_cache[channel_id]
            db = get_db()
            db.sticky_messages.delete_one({"_id": channel_id})

# --- COG CLASS ---

class Sticky(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot: return
        
        # Check if this channel has a sticky
        if message.channel.id in self.bot.sticky_cache:
            # Trigger Logic
            await trigger_sticky(self.bot, message.channel.id)

    @app_commands.command(name="stick", description="Set up a sticky message (Text or Embed).")
    @app_commands.describe(channel="Target channel (default: current)")
    @commands.has_permissions(manage_messages=True)
    async def stick(self, interaction: discord.Interaction, channel: discord.TextChannel = None):
        target_channel = channel or interaction.channel
        
        embed = discord.Embed(
            title="📌 Sticky Configuration",
            description=f"Setting up sticky message for {target_channel.mention}.\nChoose a style below:",
            color=discord.Color.blue()
        )
        await interaction.response.send_message(embed=embed, view=StickyTypeView(self.bot, target_channel), ephemeral=True)

    @app_commands.command(name="unstick", description="Stop the sticky message in a channel.")
    @commands.has_permissions(manage_messages=True)
    async def unstick(self, interaction: discord.Interaction, channel: discord.TextChannel = None):
        target_channel = channel or interaction.channel
        
        db = get_db()
        db.sticky_messages.delete_one({"_id": target_channel.id})
        
        if target_channel.id in self.bot.sticky_cache: 
            del self.bot.sticky_cache[target_channel.id]
            
        await interaction.response.send_message(f"🗑️ Sticky message removed from {target_channel.mention}.", ephemeral=True)

async def setup(bot):
    await bot.add_cog(Sticky(bot))