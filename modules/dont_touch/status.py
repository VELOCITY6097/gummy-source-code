import discord
from discord.ext import commands, tasks
from discord import ui
import os
import random
import asyncio
from dotenv import load_dotenv
from pathlib import Path
from utils import get_db

# Load env variables
env_path = Path(__file__).parent.parent.parent / '.env'
load_dotenv(dotenv_path=env_path)

OWNER_ID = int(os.getenv("OWNER_ID", 0))
SUPPORT_SERVER_ID = int(os.getenv("SUPPORT_SERVER_ID", 0))

DEFAULT_ACTIVITIES = [
    (discord.ActivityType.watching, "over the server"),
    (discord.ActivityType.listening, "/help"),
    (discord.ActivityType.playing, "with sticky messages"),
    (discord.ActivityType.competing, "best bot award"),
    (discord.ActivityType.watching, "users behave"),
]

# --- MODALS ---

class ActivityTextModal(ui.Modal, title="Set Activity Details"):
    text = ui.TextInput(label="Activity Name", placeholder="e.g., Minecraft", required=True)

    def __init__(self, bot, activity_type, mode="manual", cog=None):
        super().__init__()
        self.bot = bot
        self.activity_type = activity_type
        self.mode = mode
        self.cog = cog

    async def on_submit(self, interaction: discord.Interaction):
        if self.mode == "manual":
            # Stop randomizer if manual set
            if self.cog and self.cog.status_loop.is_running():
                self.cog.status_loop.cancel()

            act = discord.Activity(type=self.activity_type, name=self.text.value)
            await self.bot.change_presence(activity=act)
            await interaction.response.send_message(f"✅ **Activity Set:** {self.activity_type.name.title()} {self.text.value}", ephemeral=True)
        
        elif self.mode == "add_custom":
            self.cog.add_custom_activity(self.activity_type, self.text.value)
            await interaction.response.send_message(f"✅ **Added to Pool:** {self.activity_type.name.title()} {self.text.value}", ephemeral=True)

class RandomizerIntervalModal(ui.Modal, title="Loop Settings"):
    seconds = ui.TextInput(label="Interval (Seconds)", placeholder="e.g. 600 for 10 mins", default="300", required=True)

    def __init__(self, cog):
        super().__init__()
        self.cog = cog

    async def on_submit(self, interaction: discord.Interaction):
        try:
            val = int(self.seconds.value)
            if val < 10: raise ValueError
            self.cog.status_loop.change_interval(seconds=val)
            if self.cog.status_loop.is_running():
                self.cog.status_loop.restart()
            else:
                self.cog.status_loop.start()
            
            await interaction.response.send_message(f"✅ **Randomizer Updated:** Interval set to {val} seconds.", ephemeral=True)
        except ValueError:
            await interaction.response.send_message("❌ Invalid number. Minimum 10 seconds.", ephemeral=True)

# --- VIEWS ---

class MainStatusView(ui.View):
    def __init__(self, bot, cog):
        super().__init__(timeout=None)
        self.bot = bot
        self.cog = cog

    async def update_dashboard(self, interaction):
        status = self.bot.guilds[0].me.status if self.bot.guilds else discord.Status.online
        activity = self.bot.guilds[0].me.activity
        
        act_text = "None"
        if activity:
            act_text = f"{activity.type.name.title()} {activity.name}"

        loop_status = "🔴 Stopped"
        if self.cog.status_loop.is_running():
            mode = "Custom Pool" if self.cog.randomizer_mode == "custom" else "Default Pool"
            loop_status = f"🟢 Running ({mode})"

        embed = discord.Embed(title="🎛️ Status Dashboard", color=discord.Color.blurple())
        embed.add_field(name="Current Status", value=f"`{status.name.upper()}`", inline=True)
        embed.add_field(name="Current Activity", value=f"`{act_text}`", inline=True)
        embed.add_field(name="Randomizer", value=f"`{loop_status}`", inline=False)
        
        if self.cog.custom_pool:
            pool_text = ""
            for item in self.cog.custom_pool:
                try:
                    t_name = discord.ActivityType(item['type']).name.title()
                    line = f"• **{t_name}**: {item['name']}\n"
                    if len(pool_text) + len(line) > 1000:
                        pool_text += f"...and {len(self.cog.custom_pool) - pool_text.count('•')} more"
                        break
                    pool_text += line
                except: continue
            embed.add_field(name=f"Custom Pool ({len(self.cog.custom_pool)})", value=pool_text or "*Error reading pool*", inline=False)
        else:
            embed.add_field(name="Custom Pool", value="*Pool is empty*", inline=False)
        
        await interaction.response.edit_message(embed=embed, view=self)

    @ui.button(label="Refresh Info", style=discord.ButtonStyle.secondary, emoji="🔄", row=0)
    async def refresh(self, interaction: discord.Interaction, button: ui.Button):
        await self.update_dashboard(interaction)

    @ui.button(label="Change Status", style=discord.ButtonStyle.primary, emoji="🟢", row=0)
    async def status_menu(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.edit_message(content="**Select a Status Mode:**", view=StatusSelectView(self.bot, self.cog))

    @ui.button(label="Set Activity", style=discord.ButtonStyle.success, emoji="🎮", row=0)
    async def activity_menu(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.edit_message(content="**Select an Activity Type:**", view=ActivitySelectView(self.bot, self.cog))

    @ui.button(label="Randomizer Settings", style=discord.ButtonStyle.secondary, emoji="🎲", row=0)
    async def random_menu(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.edit_message(content="**Activity Loop Settings:**", view=RandomizerSelectView(self.bot, self.cog))

class StatusSelectView(ui.View):
    def __init__(self, bot, cog):
        super().__init__(timeout=None)
        self.bot = bot
        self.cog = cog
        self.selected = None

    @ui.select(placeholder="Choose Status...", options=[
        discord.SelectOption(label="Online", emoji="🟢", value="online"),
        discord.SelectOption(label="Idle", emoji="🌙", value="idle"),
        discord.SelectOption(label="Do Not Disturb", emoji="🔴", value="dnd"),
        discord.SelectOption(label="Invisible", emoji="👻", value="invisible"),
    ])
    async def select_cb(self, interaction: discord.Interaction, select: ui.Select):
        self.selected = select.values[0]
        await interaction.response.defer()

    @ui.button(label="Confirm", style=discord.ButtonStyle.success)
    async def confirm(self, interaction: discord.Interaction, button: ui.Button):
        if not self.selected: return await interaction.response.send_message("❌ Select an option first.", ephemeral=True)
        
        status = getattr(discord.Status, self.selected)
        await self.bot.change_presence(status=status)
        
        view = MainStatusView(self.bot, self.cog)
        await view.update_dashboard(interaction)

    @ui.button(label="Back", style=discord.ButtonStyle.secondary)
    async def back(self, interaction: discord.Interaction, button: ui.Button):
        view = MainStatusView(self.bot, self.cog)
        await view.update_dashboard(interaction)

class ActivitySelectView(ui.View):
    def __init__(self, bot, cog, mode="manual"):
        super().__init__(timeout=None)
        self.bot = bot
        self.cog = cog
        self.mode = mode 
        self.selected_type = None

    @ui.select(placeholder="Choose Type...", options=[
        discord.SelectOption(label="Playing", emoji="🎮", value="playing"),
        discord.SelectOption(label="Watching", emoji="📺", value="watching"),
        discord.SelectOption(label="Listening", emoji="🎧", value="listening"),
        discord.SelectOption(label="Competing", emoji="🏆", value="competing"),
        discord.SelectOption(label="Clear Presence", emoji="❌", value="clear"),
    ])
    async def select_cb(self, interaction: discord.Interaction, select: ui.Select):
        self.selected_type = select.values[0]
        await interaction.response.defer()

    @ui.button(label="Next", style=discord.ButtonStyle.success)
    async def confirm(self, interaction: discord.Interaction, button: ui.Button):
        if not self.selected_type: return await interaction.response.send_message("❌ Select an option first.", ephemeral=True)
        
        if self.selected_type == "clear":
            await self.bot.change_presence(activity=None)
            view = MainStatusView(self.bot, self.cog)
            return await view.update_dashboard(interaction)

        act_type = getattr(discord.ActivityType, self.selected_type)
        await interaction.response.send_modal(ActivityTextModal(self.bot, act_type, self.mode, self.cog))
        
        view = MainStatusView(self.bot, self.cog)
        await interaction.message.edit(embed=interaction.message.embeds[0], view=view)

    @ui.button(label="Back", style=discord.ButtonStyle.secondary)
    async def back(self, interaction: discord.Interaction, button: ui.Button):
        view = MainStatusView(self.bot, self.cog)
        if self.mode == "add_custom":
             await interaction.response.edit_message(content="**Manage Custom Pool**", view=CustomPoolManagerView(self.bot, self.cog))
        else:
             await view.update_dashboard(interaction)

class RandomizerSelectView(ui.View):
    def __init__(self, bot, cog):
        super().__init__(timeout=None)
        self.bot = bot
        self.cog = cog
        self.action = None

    @ui.select(placeholder="Configuration...", options=[
        discord.SelectOption(label="Start Default Loop", emoji="▶️", value="start_default", description="Uses built-in messages"),
        discord.SelectOption(label="Start Custom Loop", emoji="🚀", value="start_custom", description="Uses your saved list"),
        discord.SelectOption(label="Manage Custom Pool", emoji="📝", value="manage", description="Add/Remove custom activities"),
        discord.SelectOption(label="Stop Loop", emoji="⏹️", value="stop", description="Stops changing status"),
        discord.SelectOption(label="Set Interval", emoji="⏱️", value="interval", description="Change loop speed"),
    ])
    async def select_cb(self, interaction: discord.Interaction, select: ui.Select):
        self.action = select.values[0]
        await interaction.response.defer()

    @ui.button(label="Confirm", style=discord.ButtonStyle.success)
    async def confirm(self, interaction: discord.Interaction, button: ui.Button):
        if not self.action: return await interaction.response.send_message("❌ Select an option first.", ephemeral=True)
        
        if self.action == "stop":
            self.cog.status_loop.cancel()
            view = MainStatusView(self.bot, self.cog)
            await view.update_dashboard(interaction)
        
        elif self.action == "start_default":
            self.cog.randomizer_mode = "default"
            if not self.cog.status_loop.is_running(): self.cog.status_loop.start()
            view = MainStatusView(self.bot, self.cog)
            await view.update_dashboard(interaction)

        elif self.action == "start_custom":
            if not self.cog.custom_pool:
                return await interaction.followup.send("❌ **Custom Pool is Empty!** Add activities first using 'Manage Custom Pool'.", ephemeral=True)
            self.cog.randomizer_mode = "custom"
            if not self.cog.status_loop.is_running(): self.cog.status_loop.start()
            view = MainStatusView(self.bot, self.cog)
            await view.update_dashboard(interaction)

        elif self.action == "manage":
            await interaction.response.edit_message(content="**Manage Custom Pool**", view=CustomPoolManagerView(self.bot, self.cog))

        elif self.action == "interval":
            await interaction.response.send_modal(RandomizerIntervalModal(self.cog))
            view = MainStatusView(self.bot, self.cog)
            await interaction.message.edit(view=view)

    @ui.button(label="Back", style=discord.ButtonStyle.secondary)
    async def back(self, interaction: discord.Interaction, button: ui.Button):
        view = MainStatusView(self.bot, self.cog)
        await view.update_dashboard(interaction)

class CustomPoolManagerView(ui.View):
    def __init__(self, bot, cog):
        super().__init__(timeout=None)
        self.bot = bot
        self.cog = cog

    @ui.button(label="Add New Activity", style=discord.ButtonStyle.success, emoji="➕")
    async def add_btn(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.edit_message(content="**Select Type for New Entry:**", view=ActivitySelectView(self.bot, self.cog, mode="add_custom"))

    @ui.button(label="Remove Activity", style=discord.ButtonStyle.danger, emoji="➖")
    async def remove_btn(self, interaction: discord.Interaction, button: ui.Button):
        if not self.cog.custom_pool:
            return await interaction.response.send_message("❌ Pool is empty.", ephemeral=True)
        
        options = []
        for i, item in enumerate(self.cog.custom_pool[:25]):
            t_name = discord.ActivityType(item['type']).name
            options.append(discord.SelectOption(label=f"{t_name}: {item['name']}"[:100], value=str(i)))
        
        view = RemoveActivityView(self.bot, self.cog, options)
        await interaction.response.edit_message(content="**Select to Delete:**", view=view)

    @ui.button(label="Back to Randomizer", style=discord.ButtonStyle.secondary)
    async def back(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.edit_message(content="**Activity Loop Settings:**", view=RandomizerSelectView(self.bot, self.cog))

class RemoveActivityView(ui.View):
    def __init__(self, bot, cog, options):
        super().__init__(timeout=None)
        self.bot = bot
        self.cog = cog
        self.add_item(RemoveDropdown(options))

    @ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def back(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.edit_message(content="**Manage Custom Pool**", view=CustomPoolManagerView(self.bot, self.cog))

class RemoveDropdown(ui.Select):
    def __init__(self, options):
        super().__init__(placeholder="Select item to remove...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        index = int(self.values[0])
        removed = self.view.cog.remove_custom_activity(index)
        await interaction.response.send_message(f"🗑️ Removed: **{removed['name']}**", ephemeral=True)
        await interaction.message.edit(content="**Manage Custom Pool**", view=CustomPoolManagerView(self.view.bot, self.view.cog))

# --- COG ---

class Status(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.custom_pool = []
        self.randomizer_mode = "default" 
        self.load_pool()

    def load_pool(self):
        db = get_db()
        doc = db.bot_settings.find_one({"_id": "status_randomizer"})
        if doc and "activities" in doc:
            self.custom_pool = doc["activities"]

    def add_custom_activity(self, activity_type, name):
        entry = {"type": int(activity_type), "name": name}
        self.custom_pool.append(entry)
        db = get_db()
        db.bot_settings.update_one(
            {"_id": "status_randomizer"},
            {"$push": {"activities": entry}},
            upsert=True
        )

    def remove_custom_activity(self, index):
        if 0 <= index < len(self.custom_pool):
            removed = self.custom_pool.pop(index)
            db = get_db()
            db.bot_settings.update_one(
                {"_id": "status_randomizer"},
                {"$set": {"activities": self.custom_pool}},
                upsert=True
            )
            return removed
        return None

    def is_authorized(self, ctx):
        if not ctx.guild: return False
        if ctx.guild.id != SUPPORT_SERVER_ID: return False
        if ctx.author.id != OWNER_ID: return False
        return True

    @tasks.loop(seconds=300) 
    async def status_loop(self):
        # 1. Check Maintenance Mode
        if getattr(self.bot, 'maintenance_mode', False):
            return 

        # 2. Select Pool
        pool = DEFAULT_ACTIVITIES
        if self.randomizer_mode == "custom":
            if not self.custom_pool:
                # Custom pool empty, falling back
                pool = DEFAULT_ACTIVITIES
            else:
                try:
                    pool = [(discord.ActivityType(x['type']), x['name']) for x in self.custom_pool]
                except Exception as e:
                    pool = DEFAULT_ACTIVITIES

        # 3. Apply Activity
        try:
            if not pool: return
            type_enum, name = random.choice(pool)
            act = discord.Activity(type=type_enum, name=name)
            await self.bot.change_presence(activity=act)
            # removed print logging to avoid console spam
        except Exception as e:
            print(f"❌ Status Loop Error: {e}")

    @status_loop.error
    async def status_loop_error(self, error):
        print(f"❌ CRITICAL STATUS LOOP ERROR: {error}")

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot: return
        if message.content.startswith("^status"):
            ctx = await self.bot.get_context(message)
            if not self.is_authorized(ctx): return

            # CHECK FOR MAINTENANCE MODE
            if getattr(self.bot, 'maintenance_mode', False):
                return await ctx.send("🔒 **Maintenance Mode is Active.** Status controls are disabled to prevent interference.", delete_after=5)

            # Generate initial embed info
            status = self.bot.guilds[0].me.status if self.bot.guilds else discord.Status.online
            activity = self.bot.guilds[0].me.activity
            act_text = f"{activity.type.name.title()} {activity.name}" if activity else "None"
            
            loop_status = "🔴 Stopped"
            if self.status_loop.is_running():
                mode = "Custom" if self.randomizer_mode == "custom" else "Default"
                loop_status = f"🟢 Running ({mode})"

            embed = discord.Embed(title="🎛️ Status Dashboard", color=discord.Color.blurple())
            embed.add_field(name="Current Status", value=f"`{status.name.upper()}`", inline=True)
            embed.add_field(name="Current Activity", value=f"`{act_text}`", inline=True)
            embed.add_field(name="Randomizer", value=f"`{loop_status}`", inline=False)
            
            if self.custom_pool:
                pool_items = [f"• **{discord.ActivityType(x['type']).name.title()}**: {x['name']}" for x in self.custom_pool[:5]]
                if len(self.custom_pool) > 5: pool_items.append(f"...and {len(self.custom_pool)-5} more")
                embed.add_field(name=f"Custom Pool ({len(self.custom_pool)})", value="\n".join(pool_items), inline=False)
            else:
                embed.add_field(name="Custom Pool", value="*Pool is empty*", inline=False)
            
            await ctx.send(embed=embed, view=MainStatusView(self.bot, self))

async def setup(bot):
    await bot.add_cog(Status(bot))