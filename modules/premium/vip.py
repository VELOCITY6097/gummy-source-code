import discord
from discord.ext import commands
import os
import time
import asyncio
from utils import PremiumCog, check_premium_status
import google.generativeai as genai

# Initialize Gemini
GEMINI_KEY = os.getenv("GEMINI_API_KEY")
if GEMINI_KEY:
    genai.configure(api_key=GEMINI_KEY)

# List of models to attempt connecting to
PRIORITY_MODELS = [
    "gemini-2.5-flash",
    "gemini-2.5-pro",
    "gemini-2.0-flash",
    "gemini-2.0-flash-001",
    "gemini-2.0-pro-exp-02-05",
    "gemini-exp-1206"
]

class VIP(PremiumCog):
    def __init__(self, bot):
        self.bot = bot
        self.chat_sessions = {}     
        self.chat_expire = {}       
        self.active_model_name = None 

    async def get_working_model(self):
        """Finds the first working model by actually testing generation."""
        if self.active_model_name:
            return genai.GenerativeModel(self.active_model_name)
            
        for model_name in PRIORITY_MODELS:
            try:
                model = genai.GenerativeModel(model_name)
                await model.generate_content_async("Test")
                self.active_model_name = model_name
                print(f"✅ Gemini connected using model: {model_name}")
                return model
            except Exception as e:
                continue
        
        print("❌ All priority models failed. Defaulting to gemini-2.5-flash.")
        return genai.GenerativeModel("gemini-2.5-flash")

    async def get_user_session(self, user_id):
        """Retrieves chat session."""
        now = time.time()
        
        # 2-Hour Timeout Logic
        TIMEOUT_SECONDS = 7200 # 2 Hours

        if user_id in self.chat_expire:
            if self.chat_expire[user_id] < now:
                # Expired: Clear memory
                if user_id in self.chat_sessions:
                    del self.chat_sessions[user_id]
                del self.chat_expire[user_id]

        if user_id not in self.chat_sessions:
            model = await self.get_working_model()
            self.chat_sessions[user_id] = model.start_chat(history=[])
            self.chat_expire[user_id] = now + TIMEOUT_SECONDS
        
        # Extend session
        self.chat_expire[user_id] = now + TIMEOUT_SECONDS
        return self.chat_sessions[user_id]

    async def _generate_response(self, user_id, query, send_method):
        """
        Shared logic to generate and send AI responses.
        send_method: A callable (e.g., ctx.send, interaction.followup.send)
        """
        try:
            chat = await self.get_user_session(user_id)
            
            response = await chat.send_message_async(query)
            answer = response.text.strip()

            if not answer:
                await send_method("⚠️ AI returned an empty response.")
                return

            # Split logic (Text Limit 2000)
            parts = [answer[i:i+1900] for i in range(0, len(answer), 1900)]

            for part in parts:
                await send_method(part)

        except Exception as e:
            err = str(e).lower()
            msg = f"⚠️ **AI Error:** `{e}`"

            if "404" in err or "not found" in err:
                self.active_model_name = None # Reset model
                if user_id in self.chat_sessions: del self.chat_sessions[user_id]
                msg = "⚠️ **Model Updated:** Please try again."
            elif "429" in err:
                msg = "🔥 **High Traffic:** AI is cooling down."
            elif "safety" in err or "blocked" in err:
                msg = "⚠️ **Safety:** Message blocked."

            await send_method(msg)

    async def create_thread_safely(self, message_or_ctx, name):
        """Helper to create threads safe for both TextChannels and existing Threads."""
        try:
            if isinstance(message_or_ctx.channel, discord.Thread):
                return message_or_ctx.channel
            return await message_or_ctx.create_thread(name=name, auto_archive_duration=60)
        except Exception as e:
            print(f"Thread Error: {e}")
            return message_or_ctx.channel 

    @commands.Cog.listener()
    async def on_message(self, message):
        """Listens for mentions/replies and creates threads."""
        if message.author.bot or not GEMINI_KEY:
            return

        is_mentioned = self.bot.user in message.mentions
        is_reply = (message.reference and message.reference.resolved and 
                    message.reference.resolved.author.id == self.bot.user.id)

        if is_mentioned or is_reply:
            if not check_premium_status(message.author.id):
                return 

            query = message.content.replace(f"<@{self.bot.user.id}>", "").strip()
            query = query.replace(f"<@!{self.bot.user.id}>", "").strip()

            if not query: return

            # Thread Logic for public mentions
            if isinstance(message.channel, discord.Thread):
                async with message.channel.typing():
                    await self._generate_response(message.author.id, query, message.channel.send)
            else:
                thread_name = f"AI Chat - {message.author.display_name}"[:20]
                thread = await self.create_thread_safely(message, thread_name)
                async with thread.typing():
                    await self._generate_response(message.author.id, query, thread.send)

    @commands.hybrid_command(name="ai_chat", description="Chat with Gumit AI (Private).")
    @commands.cooldown(1, 4, commands.BucketType.user)
    async def ai_chat(self, ctx, *, query: str):
        if not GEMINI_KEY:
            return await ctx.send("❌ Missing `GEMINI_API_KEY` in your .env", ephemeral=True)

        # Ephemeral Handling
        sender = ctx.send
        if ctx.interaction:
            # If slash command, defer ephemerally
            await ctx.defer(ephemeral=True)
            sender = ctx.interaction.followup.send
        else:
            # If prefix command, show typing (messages can't be ephemeral)
            await ctx.channel.typing()

        await self._generate_response(ctx.author.id, query, sender)

    @ai_chat.error
    async def ai_chat_error(self, ctx, error):
        if isinstance(error, commands.CommandOnCooldown):
            msg = f"⏳ **Cooldown:** Wait {error.retry_after:.1f}s."
            if ctx.interaction:
                await ctx.interaction.response.send_message(msg, ephemeral=True)
            else:
                await ctx.send(msg, delete_after=5)
        else:
            print(f"Error in ai_chat: {error}")

    @commands.hybrid_command(name="reset_ai", description="Clear your AI chat history.")
    async def reset_ai(self, ctx):
        if ctx.author.id in self.chat_sessions:
            del self.chat_sessions[ctx.author.id]
            if ctx.author.id in self.chat_expire:
                del self.chat_expire[ctx.author.id]
            return await ctx.send("🧠 **Memory cleared.**", ephemeral=True)
        return await ctx.send("❌ No active session.", ephemeral=True)

    @commands.hybrid_command(name="gold", description="Premium check (Gumit VIP).")
    async def gold(self, ctx):
        await ctx.send(f"💎 {ctx.author.mention}, you are a confirmed Premium Member.")

    @commands.hybrid_command(name="embed_pro", description="Create a clean & professional embed.")
    async def embed_pro(self, ctx, title: str, *, content: str):
        embed = discord.Embed(
            title=title,
            description=content,
            color=discord.Color.purple()
        )
        embed.set_author(name=ctx.author.display_name, icon_url=ctx.author.avatar.url if ctx.author.avatar else None)
        embed.set_thumbnail(url=ctx.guild.icon.url if ctx.guild.icon else None)
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(VIP(bot))