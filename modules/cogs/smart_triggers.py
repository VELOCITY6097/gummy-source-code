import discord
from discord.ext import commands
from discord import app_commands, ui
import time
from utils import get_db, check_premium_status

# --- UI CLASSES ---

class TriggerModal(ui.Modal):
    keyword = ui.TextInput(
        label="Trigger Keyword", 
        placeholder="e.g. price", 
        min_length=1, 
        max_length=50,
        required=True
    )
    response = ui.TextInput(
        label="Bot Response", 
        placeholder="e.g. The price is $5. Contact admin for details...", 
        style=discord.TextStyle.paragraph, 
        min_length=1, 
        max_length=1500,
        required=True
    )

    def __init__(self, bot, cog, strict, guild_id, user_id, main_view):
        mode = "Strict" if strict else "Smart"
        super().__init__(title=f"New {mode} Trigger")
        self.bot = bot
        self.cog = cog
        self.strict = strict
        self.guild_id = guild_id
        self.user_id = user_id
        self.main_view = main_view

    async def on_submit(self, interaction: discord.Interaction):
        keyword_val = self.keyword.value.lower().strip()
        response_val = self.response.value
        
        # 1. Check Limits
        current_count = self.cog.get_user_trigger_count(self.user_id)
        is_premium = check_premium_status(self.user_id)
        limit = 20 if is_premium else 2
        
        if current_count >= limit:
            embed = discord.Embed(title="⛔ Limit Reached", color=discord.Color.red())
            embed.description = (
                f"You have used **{current_count}/{limit}** triggers.\n\n"
                f"{'👑 **Upgrade to Premium** to get 20 triggers!' if not is_premium else 'You have reached the global premium limit.'}"
            )
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        # 2. Check Duplicates
        db = get_db()
        exists = db.smart_triggers.find_one({"guild_id": self.guild_id, "keyword": keyword_val})
        if exists:
            return await interaction.response.send_message(f"❌ A trigger for `{keyword_val}` already exists in this server.", ephemeral=True)

        # 3. Save to DB
        new_trigger = {
            "guild_id": self.guild_id,
            "keyword": keyword_val,
            "response": response_val,
            "strict": self.strict,
            "owner_id": self.user_id,
            "created_at": time.time()
        }
        db.smart_triggers.insert_one(new_trigger)

        # 4. Update Cache
        if self.guild_id not in self.cog.trigger_cache:
            self.cog.trigger_cache[self.guild_id] = []
        
        self.cog.trigger_cache[self.guild_id].append({
            "keyword": keyword_val,
            "response": response_val,
            "strict": self.strict,
            "owner_id": self.user_id
        })

        mode_icon = "🎯" if self.strict else "🧠"
        status_msg = f"✅ **Success:** Added {mode_icon} trigger for `{keyword_val}`."
        
        # Refresh Main View with success message
        await self.main_view.render_main(interaction, status=status_msg)

class TriggerTypeView(ui.View):
    def __init__(self, bot, cog, ctx, main_view):
        super().__init__(timeout=60)
        self.bot = bot
        self.cog = cog
        self.ctx = ctx
        self.main_view = main_view

    @ui.button(label="Smart Match (Contains)", style=discord.ButtonStyle.primary, emoji="🧠")
    async def smart_btn(self, interaction: discord.Interaction, button: ui.Button):
        if interaction.user.id != self.ctx.author.id: return
        await interaction.response.send_modal(TriggerModal(self.bot, self.cog, False, interaction.guild.id, interaction.user.id, self.main_view))

    @ui.button(label="Strict Match (Exact)", style=discord.ButtonStyle.secondary, emoji="🎯")
    async def strict_btn(self, interaction: discord.Interaction, button: ui.Button):
        if interaction.user.id != self.ctx.author.id: return
        await interaction.response.send_modal(TriggerModal(self.bot, self.cog, True, interaction.guild.id, interaction.user.id, self.main_view))

    @ui.button(label="Back", style=discord.ButtonStyle.secondary)
    async def back_btn(self, interaction: discord.Interaction, button: ui.Button):
        if interaction.user.id != self.ctx.author.id: return
        await self.main_view.render_main(interaction)

class ConfirmDeleteView(ui.View):
    def __init__(self, cog, keyword, main_view, ctx):
        super().__init__(timeout=60)
        self.cog = cog
        self.keyword = keyword
        self.main_view = main_view
        self.ctx = ctx

    @ui.button(label="Confirm Delete", style=discord.ButtonStyle.danger, emoji="🗑️")
    async def confirm(self, interaction: discord.Interaction, button: ui.Button):
        if interaction.user.id != self.ctx.author.id: return
        
        db = get_db()
        result = db.smart_triggers.delete_one({"guild_id": interaction.guild.id, "keyword": self.keyword})
        
        if result.deleted_count > 0:
            # Refresh Cache
            current_list = self.cog.trigger_cache.get(interaction.guild.id, [])
            self.cog.trigger_cache[interaction.guild.id] = [t for t in current_list if t["keyword"] != self.keyword]
            
            await self.main_view.render_main(interaction, status=f"🗑️ **Deleted:** Trigger `{self.keyword}` removed.")
        else:
            await self.main_view.render_main(interaction, status=f"❌ **Error:** Trigger `{self.keyword}` not found.")

    @ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: ui.Button):
        if interaction.user.id != self.ctx.author.id: return
        await self.main_view.render_main(interaction, status="🚫 Deletion Cancelled.")

class DeleteTriggerSelect(ui.Select):
    def __init__(self, triggers):
        options = []
        # Discord select menus max out at 25 options
        for t in triggers[:25]:
            icon = "🎯" if t['strict'] else "🧠"
            label = t['keyword'][:100]
            desc = t['response'][:90] + "..." if len(t['response']) > 90 else t['response']
            options.append(discord.SelectOption(label=label, description=desc, emoji=icon, value=t['keyword']))
        
        super().__init__(placeholder="Select a trigger to delete...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        keyword = self.values[0]
        # Transition to Confirmation View instead of deleting immediately
        view = ConfirmDeleteView(self.view.cog, keyword, self.view.main_view, self.view.ctx)
        
        embed = discord.Embed(
            title="⚠️ Confirm Deletion",
            description=f"Are you sure you want to delete the trigger **`{keyword}`**?\nThis action cannot be undone.",
            color=discord.Color.orange()
        )
        await interaction.response.edit_message(embed=embed, view=view)

class DeleteView(ui.View):
    def __init__(self, cog, triggers, main_view, ctx):
        super().__init__(timeout=60)
        self.cog = cog
        self.main_view = main_view
        self.ctx = ctx
        self.add_item(DeleteTriggerSelect(triggers))

    @ui.button(label="Back", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: ui.Button):
        await self.main_view.render_main(interaction)

class TriggerDashboardView(ui.View):
    def __init__(self, bot, cog, ctx):
        super().__init__(timeout=180)
        self.bot = bot
        self.cog = cog
        self.ctx = ctx

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.ctx.author.id:
            await interaction.response.send_message("❌ This menu is not for you.", ephemeral=True)
            return False
        return True

    async def render_main(self, interaction: discord.Interaction, status=None):
        triggers = self.cog.trigger_cache.get(interaction.guild.id, [])
        
        embed = discord.Embed(
            title="🤖 Auto-Trigger Dashboard", 
            description="Manage your server's automated text responses.", 
            color=discord.Color.gold()
        )
        
        if status:
            embed.description = f"{status}\n\n{embed.description}"

        embed.add_field(name="📊 Statistics", value=f"**Active Triggers:** `{len(triggers)}`", inline=False)
        
        # Preview triggers
        if triggers:
            preview_text = ""
            for t in triggers[:5]:
                icon = "🎯" if t['strict'] else "🧠"
                preview_text += f"{icon} **`{t['keyword']}`**\n"
            if len(triggers) > 5:
                preview_text += f"*...and {len(triggers)-5} more*"
            embed.add_field(name="👀 Preview", value=preview_text, inline=False)
        else:
            embed.add_field(name="👀 Preview", value="*No triggers set yet.*", inline=False)

        embed.set_thumbnail(url=self.bot.user.avatar.url if self.bot.user.avatar else None)
        
        # Recreate view to refresh state
        view = TriggerDashboardView(self.bot, self.cog, self.ctx)
        
        # Check if we are responding to a modal submit (requires special handling) or a button click
        if interaction.type == discord.InteractionType.modal_submit:
             await interaction.response.edit_message(content=None, embed=embed, view=view)
        else:
             await interaction.response.edit_message(content=None, embed=embed, view=view)

    @ui.button(label="Add Trigger", style=discord.ButtonStyle.success, emoji="➕", row=0)
    async def add_btn(self, interaction: discord.Interaction, button: ui.Button):
        embed = discord.Embed(title="✨ Add New Trigger", color=discord.Color.blurple())
        embed.add_field(name="🧠 Smart Match", value="Triggers when keyword is *contained* in message.\n`hello` matches \"oh hello there\"")
        embed.add_field(name="🎯 Strict Match", value="Triggers ONLY on *exact* message match.\n`hello` matches only \"hello\"")
        
        view = TriggerTypeView(self.bot, self.cog, self.ctx, self)
        await interaction.response.edit_message(embed=embed, view=view)

    @ui.button(label="Remove Trigger", style=discord.ButtonStyle.danger, emoji="➖", row=0)
    async def remove_btn(self, interaction: discord.Interaction, button: ui.Button):
        triggers = self.cog.trigger_cache.get(interaction.guild.id, [])
        if not triggers:
            return await interaction.response.send_message("📭 No triggers to remove.", ephemeral=True)
        
        view = DeleteView(self.cog, triggers, self, self.ctx)
        embed = discord.Embed(title="🗑️ Delete Trigger", description="Select a trigger from the dropdown below to remove it.", color=discord.Color.red())
        await interaction.response.edit_message(embed=embed, view=view)

    @ui.button(label="List All", style=discord.ButtonStyle.primary, emoji="📜", row=0)
    async def list_btn(self, interaction: discord.Interaction, button: ui.Button):
        triggers = self.cog.trigger_cache.get(interaction.guild.id, [])
        if not triggers:
            return await interaction.response.send_message("📭 No triggers setup.", ephemeral=True)
        
        embed = discord.Embed(title=f"📋 Full Trigger List ({len(triggers)})", color=discord.Color.blue())
        
        desc = ""
        for t in triggers[:15]: 
            icon = "🎯" if t['strict'] else "🧠"
            match_type = "Strict" if t['strict'] else "Smart"
            # Single line format as requested
            desc += f"• {icon} **`{t['keyword']}`** ({match_type}) → {t['response'][:50]}...\n"
        
        if len(triggers) > 15:
            desc += f"\n**...and {len(triggers) - 15} more triggers.**"

        embed.description = desc
        embed.set_footer(text="Click 'Back' to return to the dashboard.")
        
        # Hide main buttons, show only back button
        view = ui.View()
        back_btn = ui.Button(label="Back", style=discord.ButtonStyle.secondary)
        
        async def back_callback(interaction):
            await self.render_main(interaction)
            
        back_btn.callback = back_callback
        view.add_item(back_btn)
        
        await interaction.response.edit_message(embed=embed, view=view)

# --- COG ---

class SmartTriggers(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Cache Structure: {guild_id: [ {keyword, response, strict, owner_id} ] }
        self.trigger_cache = {}
        self.cooldowns = {} 
        self.channel_cooldowns = {} 
        self.load_cache()

    def load_cache(self):
        """Loads all triggers from MongoDB to memory for instant responses."""
        db = get_db()
        self.trigger_cache = {}
        
        cursor = db.smart_triggers.find({})
        count = 0
        
        for doc in cursor:
            gid = doc["guild_id"]
            if gid not in self.trigger_cache:
                self.trigger_cache[gid] = []
            
            self.trigger_cache[gid].append({
                "keyword": doc["keyword"],
                "response": doc["response"],
                "strict": doc.get("strict", False),
                "owner_id": doc.get("owner_id")
            })
        print(f"📦 Loaded {count} smart triggers.")

    def get_user_trigger_count(self, user_id):
        """Counts how many triggers a user has created across all servers."""
        db = get_db()
        return db.smart_triggers.count_documents({"owner_id": user_id})

    # --- COMMANDS ---

    @commands.hybrid_command(name="trigger", description="Open the Auto-Trigger Dashboard.")
    @commands.has_permissions(manage_messages=True)
    async def trigger_dashboard(self, ctx):
        embed = discord.Embed(title="🤖 Auto-Trigger Dashboard", description="Configure how the bot responds to text patterns.", color=discord.Color.gold())
        count = len(self.trigger_cache.get(ctx.guild.id, []))
        embed.add_field(name="Active Triggers", value=f"`{count}`", inline=True)
        embed.set_footer(text="Manage your server's automated replies.")
        embed.set_thumbnail(url=self.bot.user.avatar.url if self.bot.user.avatar else None)
        
        view = TriggerDashboardView(self.bot, self, ctx)
        await ctx.send(embed=embed, view=view, ephemeral=True)

    # --- LISTENER ---

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or not message.guild: return

        guild_triggers = self.trigger_cache.get(message.guild.id)
        if not guild_triggers: return

        # 1. Global Channel Throttle (Anti-Spam)
        now = time.time()
        last_channel_msg = self.channel_cooldowns.get(message.channel.id, 0)
        if now - last_channel_msg < 3: 
            return 

        content = message.content.lower()

        # Check cooldown bucket for this channel 
        if message.channel.id not in self.cooldowns:
            self.cooldowns[message.channel.id] = {}

        for t in guild_triggers:
            triggered = False
            
            if t['strict']:
                if content == t['keyword']:
                    triggered = True
            else:
                # Smart Match
                if f" {t['keyword']} " in f" {content} " or content.startswith(f"{t['keyword']} ") or content.endswith(f" {t['keyword']}"):
                    triggered = True
                elif content == t['keyword']:
                    triggered = True

            if triggered:
                # 2. Specific Trigger Cooldown (5 Seconds)
                last_time = self.cooldowns[message.channel.id].get(t['keyword'], 0)
                if now - last_time > 5:
                    await message.channel.send(t['response'])
                    self.cooldowns[message.channel.id][t['keyword']] = now
                    self.channel_cooldowns[message.channel.id] = now
                    break 

async def setup(bot):
    await bot.add_cog(SmartTriggers(bot))