import discord
from discord.ext import commands
from discord import ui
import asyncio
from utils import get_db

class SetupSession:
    """Helper class to manage the setup state."""
    def __init__(self, ctx):
        self.ctx = ctx
        self.step = 1
        self.config = {}
        self.message = None # The bot's main embed message
        self.view = None
        self.finished = False

class Configuration(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # --- HELPER: HYBRID INPUT WAITER ---
    async def wait_for_input(self, session, embed, view):
        """
        Waits for EITHER a button click (via view) OR a chat message.
        """
        # 1. Send or Edit the bot's interface message
        if session.message:
            await session.message.edit(embed=embed, view=view)
        else:
            session.message = await session.ctx.send(embed=embed, view=view)
        
        session.view = view

        # 2. Define the check for chat messages
        def msg_check(m):
            return m.author.id == session.ctx.author.id and m.channel.id == session.ctx.channel.id

        # 3. Run Listeners in Parallel
        # We create a task for the View (buttons) and a task for Messages (chat)
        # We wait for the FIRST one to complete.
        
        view_task = asyncio.create_task(view.wait())
        msg_task = asyncio.create_task(self.bot.wait_for('message', check=msg_check))

        done, pending = await asyncio.wait(
            [view_task, msg_task], 
            return_when=asyncio.FIRST_COMPLETED
        )

        result = None
        
        # 4. Handle the Winner
        if view_task in done:
            # Button was clicked!
            msg_task.cancel() # Stop listening for messages
            result = "button"
            
        elif msg_task in done:
            # Message was sent!
            message = msg_task.result()
            result = message
            
            # Auto-Delete user's message as requested
            try:
                await message.delete()
            except:
                pass
            
            # Stop the view (disable buttons temporarily)
            view.stop()

        return result

    # --- STEP LOGIC ---

    async def get_or_create_channel(self, guild, name):
        existing = discord.utils.get(guild.text_channels, name=name)
        if existing: return existing, False
        
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }
        return await guild.create_text_channel(name, overwrites=overwrites), True

    # --- MAIN COMMAND ---

    @commands.hybrid_command(name="setup", description="Interactive Server Setup Wizard.")
    @commands.has_permissions(administrator=True)
    async def setup(self, ctx):
        session = SetupSession(ctx)
        
        # --- STEP 1: LOGGING ---
        while True:
            embed = discord.Embed(
                title="🛡️ Step 1: Logging Channel",
                description="Where should I log deleted messages and events?\n\n**To Answer:**\n📝 **Type** a channel name (e.g. `#logs`)\n👇 **OR Click** a button below.",
                color=discord.Color.blue()
            )
            
            # Create View for Step 1
            view = ui.View(timeout=None)
            
            # Button Logic needs to be inline or methods attached to a custom View class.
            # For simplicity in this hybrid loop, we use a custom class per step or dynamic addition.
            # Let's use dynamic addition for cleaner code here.
            
            selection = None

            # Button 1: Create New
            async def create_callback(interaction):
                await interaction.response.defer()
                c, created = await self.get_or_create_channel(ctx.guild, "server-logs")
                session.config["log_channel"] = c.id
                view.stop()
            b1 = ui.Button(label="Auto-Create '#server-logs'", style=discord.ButtonStyle.primary, emoji="✨")
            b1.callback = create_callback
            view.add_item(b1)

            # Button 2: Skip
            async def skip_callback(interaction):
                await interaction.response.defer()
                session.config["log_channel"] = None
                view.stop()
            b2 = ui.Button(label="Skip Logging", style=discord.ButtonStyle.secondary)
            b2.callback = skip_callback
            view.add_item(b2)

            # WAIT
            result = await self.wait_for_input(session, embed, view)

            # PROCESS INPUT
            if result == "button":
                break # Config already set in callback
            else:
                # User typed something
                if result.channel_mentions:
                    session.config["log_channel"] = result.channel_mentions[0].id
                    break
                else:
                    # Try finding by name or ID
                    try:
                        cid = int(result.content)
                        session.config["log_channel"] = cid
                        break
                    except:
                        # Invalid input, loop repeats
                        temp = await ctx.send("❌ Invalid channel. Please mention a channel or click a button.", delete_after=3)

        # --- STEP 2: TRANSCRIPTS ---
        while True:
            log_status = "Enabled" if session.config.get("log_channel") else "Disabled"
            embed = discord.Embed(
                title="📂 Step 2: Ticket Transcripts",
                description=f"Where should closed ticket files be saved?\nLogs Status: **{log_status}**\n\n**To Answer:**\n📝 **Type** a channel name\n👇 **OR Click** a button.",
                color=discord.Color.gold()
            )
            
            view = ui.View(timeout=None)

            # Option: Use Logs
            if session.config.get("log_channel"):
                async def same_callback(interaction):
                    await interaction.response.defer()
                    session.config["transcript_channel"] = session.config["log_channel"]
                    session.config["transcripts_enabled"] = True
                    view.stop()
                b_same = ui.Button(label="Use Log Channel", style=discord.ButtonStyle.success, emoji="🔄")
                b_same.callback = same_callback
                view.add_item(b_same)

            # Option: Create
            async def create_t_callback(interaction):
                await interaction.response.defer()
                c, created = await self.get_or_create_channel(ctx.guild, "transcripts")
                session.config["transcript_channel"] = c.id
                session.config["transcripts_enabled"] = True
                view.stop()
            b_create = ui.Button(label="Auto-Create '#transcripts'", style=discord.ButtonStyle.primary, emoji="✨")
            b_create.callback = create_t_callback
            view.add_item(b_create)

            # Option: Disable
            async def disable_callback(interaction):
                await interaction.response.defer()
                session.config["transcripts_enabled"] = False
                view.stop()
            b_off = ui.Button(label="Disable Transcripts", style=discord.ButtonStyle.danger)
            b_off.callback = disable_callback
            view.add_item(b_off)

            result = await self.wait_for_input(session, embed, view)

            if result == "button":
                break
            else:
                if result.channel_mentions:
                    session.config["transcript_channel"] = result.channel_mentions[0].id
                    session.config["transcripts_enabled"] = True
                    break
                else:
                     temp = await ctx.send("❌ Invalid input. Mention a channel.", delete_after=3)

        # --- STEP 3: ROLES ---
        while True:
            embed = discord.Embed(
                title="👮 Step 3: Mod Roles",
                description="Which roles can use Kick/Ban/Warn commands?\n(Admins always have access)\n\n**To Answer:**\n📝 **Type** role mentions (e.g. `@Mod @Staff`)\n👇 **OR Click** 'Admins Only'.",
                color=discord.Color.purple()
            )

            view = ui.View(timeout=None)
            
            async def admin_callback(interaction):
                await interaction.response.defer()
                session.config["mod_roles"] = []
                view.stop()
            b_admin = ui.Button(label="Admins Only", style=discord.ButtonStyle.secondary, emoji="🛡️")
            b_admin.callback = admin_callback
            view.add_item(b_admin)

            result = await self.wait_for_input(session, embed, view)

            if result == "button":
                break
            else:
                # Check for role mentions
                if result.role_mentions:
                    session.config["mod_roles"] = [r.id for r in result.role_mentions]
                    break
                else:
                    temp = await ctx.send("❌ Please mention at least one role (e.g. @Moderator).", delete_after=3)

        # --- FINISH ---
        # Save to DB
        db = get_db()
        db.guild_configs.update_one({"_id": ctx.guild.id}, {"$set": session.config}, upsert=True)

        final_embed = discord.Embed(title="✅ Setup Complete!", color=discord.Color.green())
        
        # Formatting output
        log_c = f"<#{session.config['log_channel']}>" if session.config.get('log_channel') else "❌ Disabled"
        
        if session.config.get('transcripts_enabled'):
            trans_c = f"<#{session.config['transcript_channel']}>"
        else:
            trans_c = "❌ Disabled"
            
        roles_c = f"{len(session.config.get('mod_roles', []))} Roles" if session.config.get('mod_roles') else "👑 Admins Only"

        final_embed.add_field(name="📜 Logging", value=log_c, inline=True)
        final_embed.add_field(name="📂 Transcripts", value=trans_c, inline=True)
        final_embed.add_field(name="🛡️ Access", value=roles_c, inline=True)
        final_embed.set_footer(text="Settings saved to Database.")

        if session.message:
            await session.message.edit(embed=final_embed, view=None)
        else:
            await ctx.send(embed=final_embed)

async def setup(bot):
    await bot.add_cog(Configuration(bot))