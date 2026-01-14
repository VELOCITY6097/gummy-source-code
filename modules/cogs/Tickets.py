import discord
from discord.ext import commands
from discord import ui
import asyncio
import uuid
import io
import time
import datetime
from utils import get_db

# --- CONSTANTS ---
OPEN_COLOR = 0x5865F2    # Blurple
CLOSED_COLOR = 0x2F3136  # Dark Grey
HOLD_COLOR = 0xFEE75C    # Yellow
ACC_COLOR = 0x57F287     # Green
REJ_COLOR = 0xED4245     # Red

DEFAULT_CONFIG = {
    "title": "Support Tickets",
    "desc": "Click the button below to open a ticket.",
    "btn_text": "Open Ticket",
    "btn_emoji": "📩",
    "welcome": "Hi {user}! Support will be with you shortly.",
    "closing": "Ticket closed by {user}.",
    "ping_role": None,
    "templates": {} 
}

# --- HELPERS ---

def get_config(guild_id):
    db = get_db()
    conf = db.ticket_configs.find_one({"_id": guild_id})
    if not conf: return DEFAULT_CONFIG.copy()
    merged = DEFAULT_CONFIG.copy()
    merged.update(conf)
    if "templates" not in merged: merged["templates"] = {}
    return merged

def update_config(guild_id, data):
    db = get_db()
    db.ticket_configs.update_one({"_id": guild_id}, {"$set": data}, upsert=True)

def is_staff(interaction):
    if interaction.user.guild_permissions.administrator: return True
    db = get_db()
    
    g_conf = db.guild_configs.find_one({"_id": interaction.guild.id}) or {}
    if "mod_roles" in g_conf:
        if any(r.id in g_conf["mod_roles"] for r in interaction.user.roles): return True
        
    t_conf = db.ticket_configs.find_one({"_id": interaction.guild.id}) or {}
    if t_conf.get("ping_role"):
        if interaction.user.get_role(t_conf["ping_role"]): return True
    return False

async def close_ticket_logic(interaction, closed_by_user, reason="No reason provided"):
    await interaction.channel.send("🔒 **Archiving Ticket...** Generating transcript...")
    
    transcript = f"TRANSCRIPT - {interaction.channel.name}\nServer: {interaction.guild.name}\nTime: {datetime.datetime.now()}\n"
    transcript += f"Closed By: {closed_by_user.name}\nReason: {reason}\n\n"
    
    async for m in interaction.channel.history(limit=5000, oldest_first=True):
        transcript += f"[{m.created_at.strftime('%Y-%m-%d %H:%M')}] {m.author.name}: {m.content}\n"
    
    db = get_db()
    case_id = str(uuid.uuid4())[:8]
    db.ticket_transcripts.insert_one({
        "case_id": case_id,
        "guild_id": interaction.guild.id,
        "content": transcript,
        "closed_by": closed_by_user.id,
        "timestamp": time.time()
    })
    
    if interaction.channel.topic and "Owner:" in interaction.channel.topic:
        try:
            uid = int(interaction.channel.topic.split("Owner:")[-1].strip())
            owner = interaction.guild.get_member(uid)
            if owner:
                conf = get_config(interaction.guild.id)
                msg = conf.get("closing", "Ticket Closed.").replace("{user}", owner.name).replace("{server}", interaction.guild.name)
                f = discord.File(io.StringIO(transcript), filename=f"ticket-{case_id}.txt")
                await owner.send(f"{msg}\n**Reason:** {reason}\nCase ID: `{case_id}`", file=f)
        except: pass

    await interaction.channel.delete()

# --- MODALS ---

class UserCloseRequestModal(ui.Modal, title="Request to Close Ticket"):
    reason = ui.TextInput(label="Reason for Closing", style=discord.TextStyle.paragraph, required=True, placeholder="My issue is resolved...")

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()
        
        conf = get_config(interaction.guild.id)
        ping = f"<@&{conf['ping_role']}>" if conf.get('ping_role') else "Staff"
        
        embed = discord.Embed(title="⚠️ User Requested Close", description=f"**Reason:** {self.reason.value}", color=discord.Color.orange())
        embed.set_author(name=interaction.user.name, icon_url=interaction.user.avatar.url)
        embed.set_footer(text="Staff: Click 'Close' to confirm.")
        
        await interaction.channel.send(content=ping, embed=embed)

class TemplateAddModal(ui.Modal, title="➕ Add Smart Reply"):
    name = ui.TextInput(label="Short Name", placeholder="e.g. renew", max_length=20)
    content = ui.TextInput(label="Message Content", style=discord.TextStyle.paragraph, required=True)
    image_url = ui.TextInput(label="Image URL (Optional)", placeholder="https://...", required=False)

    def __init__(self, view):
        super().__init__()
        self.view_ref = view

    async def on_submit(self, interaction: discord.Interaction):
        conf = get_config(interaction.guild.id)
        templates = conf.get("templates", {})
        
        templates[self.name.value.lower()] = {
            "content": self.content.value,
            "image": self.image_url.value if self.image_url.value else None
        }
        
        conf["templates"] = templates
        update_config(interaction.guild.id, conf)
        await interaction.response.send_message(f"✅ Template `{self.name.value}` saved!", ephemeral=True)

class AnonReplyModal(ui.Modal, title="🕵️ Anonymous Reply"):
    message = ui.TextInput(label="Message", style=discord.TextStyle.paragraph, required=True)

    async def on_submit(self, interaction: discord.Interaction):
        embed = discord.Embed(description=self.message.value, color=discord.Color.blue())
        embed.set_author(name="Support Staff (Anonymous)", icon_url=interaction.guild.icon.url if interaction.guild.icon else None)
        embed.set_footer(text="Staff Reply")
        await interaction.channel.send(embed=embed)
        await interaction.response.send_message("✅ Sent.", ephemeral=True)

class ResolutionReasonModal(ui.Modal):
    def __init__(self, status_label, color, view, is_reject=False):
        super().__init__(title=f"{status_label} Ticket")
        self.status_label = status_label
        self.color = color
        self.view_ref = view
        self.is_reject = is_reject
        self.reason = ui.TextInput(label="Reason", style=discord.TextStyle.paragraph, required=True)
        self.add_item(self.reason)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()
        embed = discord.Embed(title=f"Ticket {self.status_label}", description=f"**Reason:** {self.reason.value}", color=self.color)
        embed.set_author(name=interaction.user.name, icon_url=interaction.user.avatar.url)
        await interaction.channel.send(embed=embed)
        
        if self.is_reject:
            await asyncio.sleep(3)
            await close_ticket_logic(interaction, interaction.user, reason=f"Rejected: {self.reason.value}")

class ConfigTextModal(ui.Modal, title="📝 Edit Ticket Design"):
    m_title = ui.TextInput(label="Title", default="Support Tickets")
    m_desc = ui.TextInput(label="Description", style=discord.TextStyle.paragraph)
    m_btn_txt = ui.TextInput(label="Button Label", default="Open Ticket")
    m_btn_emoji = ui.TextInput(label="Button Emoji", default="📩")
    m_welcome = ui.TextInput(label="Welcome Message", style=discord.TextStyle.paragraph)

    def __init__(self, current_conf, dashboard_view):
        super().__init__()
        self.dashboard_view = dashboard_view
        self.m_desc.default = current_conf['desc']
        self.m_welcome.default = current_conf['welcome']
        self.m_title.default = current_conf['title']
        self.m_btn_txt.default = current_conf['btn_text']
        self.m_btn_emoji.default = current_conf['btn_emoji']

    async def on_submit(self, interaction: discord.Interaction):
        new_data = {"title": self.m_title.value, "desc": self.m_desc.value, "btn_text": self.m_btn_txt.value, "btn_emoji": self.m_btn_emoji.value, "welcome": self.m_welcome.value}
        self.dashboard_view.config.update(new_data)
        update_config(interaction.guild.id, self.dashboard_view.config)
        await self.dashboard_view.refresh_dashboard(interaction)

# --- VIEWS ---

class SmartReplySelect(ui.Select):
    def __init__(self, templates):
        options = []
        self.clean_templates = {} 
        
        for name, data in templates.items():
            if isinstance(data, str):
                content = data
                img = None
            else:
                content = data.get("content", "")
                img = data.get("image")
            
            self.clean_templates[name] = {"content": content, "image": img}
            options.append(discord.SelectOption(label=name, description=content[:50]+"..."))

        if not options: 
            options = [discord.SelectOption(label="No Templates", description="Add them in /ticket", default=True)]
            
        super().__init__(placeholder="Select a Template...", min_values=1, max_values=1, options=options, disabled=(len(options)==0 and options[0].label=="No Templates"))

    async def callback(self, interaction: discord.Interaction):
        key = self.values[0]
        if key in self.clean_templates:
            data = self.clean_templates[key]
            
            embed = discord.Embed(description=data['content'], color=discord.Color.blue())
            embed.set_author(name=f"Support ({interaction.user.name})", icon_url=interaction.user.avatar.url)
            if data['image']:
                embed.set_image(url=data['image'])
            
            await interaction.channel.send(embed=embed)
            await interaction.response.send_message("✅ Template sent.", ephemeral=True)

class SmartReplyView(ui.View):
    def __init__(self, templates):
        super().__init__(timeout=60)
        self.add_item(SmartReplySelect(templates))

class TicketLaunchView(ui.View):
    def __init__(self, label, emoji):
        super().__init__(timeout=None)
        self.add_item(ui.Button(label=label, emoji=emoji, style=discord.ButtonStyle.primary, custom_id="ticket_create_v6"))

class TicketActionsView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(label="Close", style=discord.ButtonStyle.secondary, emoji="🔒", custom_id="tick_act_close", row=0)
    async def close(self, interaction: discord.Interaction, button: ui.Button):
        if is_staff(interaction):
            await interaction.response.defer()
            await close_ticket_logic(interaction, interaction.user, "Staff Closed")
        else:
            await interaction.response.send_modal(UserCloseRequestModal())

    @ui.button(label="Accepted", style=discord.ButtonStyle.success, emoji="✅", custom_id="tick_act_acc", row=0)
    async def accepted(self, interaction: discord.Interaction, button: ui.Button):
        if not is_staff(interaction): return await interaction.response.send_message("⛔ Staff Only.", ephemeral=True)
        await interaction.response.send_modal(ResolutionReasonModal("Accepted", ACC_COLOR, self))

    @ui.button(label="Rejected", style=discord.ButtonStyle.danger, emoji="✖️", custom_id="tick_act_rej", row=0)
    async def rejected(self, interaction: discord.Interaction, button: ui.Button):
        if not is_staff(interaction): return await interaction.response.send_message("⛔ Staff Only.", ephemeral=True)
        await interaction.response.send_modal(ResolutionReasonModal("Rejected", REJ_COLOR, self, is_reject=True))

    @ui.button(label="Hold", style=discord.ButtonStyle.primary, emoji="✋", custom_id="tick_act_hold", row=1)
    async def hold(self, interaction: discord.Interaction, button: ui.Button):
        if not is_staff(interaction): return await interaction.response.send_message("⛔ Staff Only.", ephemeral=True)
        await interaction.response.defer()
        embed = interaction.message.embeds[0]
        if embed.color.value == HOLD_COLOR:
            embed.color = OPEN_COLOR
            embed.set_footer(text="Status: Active")
            button.label = "Hold"
            button.style = discord.ButtonStyle.primary
            await interaction.channel.send("▶️ **Ticket Resumed.**", delete_after=3)
        else:
            embed.color = HOLD_COLOR
            embed.set_footer(text="Status: ⚠️ Tickets are on Hold")
            button.label = "Unhold"
            button.style = discord.ButtonStyle.danger
            await interaction.channel.send("⏸️ **Ticket Placed on Hold.**", delete_after=3)
        await interaction.message.edit(embed=embed, view=self)

    @ui.button(label="Smart Reply", style=discord.ButtonStyle.secondary, emoji="🤖", custom_id="tick_act_smart", row=1)
    async def smart_reply(self, interaction: discord.Interaction, button: ui.Button):
        if not is_staff(interaction): return await interaction.response.send_message("⛔ Staff Only.", ephemeral=True)
        
        conf = get_config(interaction.guild.id)
        templates = conf.get("templates", {})
        
        # DISPLAY ACTIVE TEMPLATES
        embed = discord.Embed(title="🤖 Smart Reply Templates", color=discord.Color.gold())
        
        if templates:
            desc = ""
            for name, data in templates.items():
                txt = data if isinstance(data, str) else data.get("content", "")
                img = "🖼️" if (isinstance(data, dict) and data.get("image")) else ""
                desc += f"• **{name}**: {txt[:40]}... {img}\n"
            embed.description = desc
        else:
            embed.description = "No templates found. Add them in `/ticket`."
            
        await interaction.response.send_message(embed=embed, view=SmartReplyView(templates), ephemeral=True)

    @ui.button(label="Anon Reply", style=discord.ButtonStyle.secondary, emoji="🕵️", custom_id="tick_act_anon", row=1)
    async def anon_reply(self, interaction: discord.Interaction, button: ui.Button):
        if not is_staff(interaction): return await interaction.response.send_message("⛔ Staff Only.", ephemeral=True)
        await interaction.response.send_modal(AnonReplyModal())

# --- ADMIN DASHBOARD ---

class TemplateManagerView(ui.View):
    def __init__(self, guild_id):
        super().__init__(timeout=60)
        self.guild_id = guild_id

    @ui.button(label="Add Template", style=discord.ButtonStyle.success, emoji="➕")
    async def add_t(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_modal(TemplateAddModal(self))

    @ui.button(label="Delete Template", style=discord.ButtonStyle.danger, emoji="🗑️")
    async def del_t(self, interaction: discord.Interaction, button: ui.Button):
        conf = get_config(self.guild_id)
        templates = conf.get("templates", {})
        if not templates: return await interaction.response.send_message("❌ No templates.", ephemeral=True)
        
        options = [discord.SelectOption(label=name) for name in templates.keys()]
        view = ui.View()
        select = ui.Select(placeholder="Delete...", options=options)
        
        async def callback(inter):
            del conf["templates"][select.values[0]]
            update_config(self.guild_id, conf)
            await inter.response.send_message(f"🗑️ Deleted `{select.values[0]}`.", ephemeral=True)
        
        select.callback = callback
        view.add_item(select)
        await interaction.response.send_message("Select to delete:", view=view, ephemeral=True)

class RoleSelectionView(ui.View):
    def __init__(self, dashboard_view):
        super().__init__(timeout=60)
        self.dashboard_view = dashboard_view
    @ui.select(cls=discord.ui.RoleSelect, placeholder="Select Support Role", min_values=1, max_values=1)
    async def select_role(self, interaction: discord.Interaction, select: ui.RoleSelect):
        self.dashboard_view.config["ping_role"] = select.values[0].id
        update_config(interaction.guild.id, self.dashboard_view.config)
        await self.dashboard_view.refresh_dashboard(interaction)

class AdminDashboardView(ui.View):
    def __init__(self, guild_id):
        super().__init__(timeout=None)
        self.guild_id = guild_id
        self.config = get_config(guild_id)

    def create_embed(self):
        embed = discord.Embed(title="🎛️ Ticket System Admin", color=discord.Color.blue())
        
        role_ping = f"<@&{self.config['ping_role']}>" if self.config['ping_role'] else "`None`"
        t_count = len(self.config.get("templates", {}))
        
        config_desc = (
            f"**Title:** {self.config['title']}\n"
            f"**Desc:** {self.config['desc']}\n"
            f"**Button:** {self.config['btn_emoji']} {self.config['btn_text']}\n"
            f"**Ping Role:** {role_ping}\n"
            f"**Templates:** {t_count} presets"
        )
        embed.add_field(name="⚙️ Current Settings", value=config_desc, inline=False)
        
        controls_desc = (
            "📝 **Edit Design:** Customize the main panel.\n"
            "🔔 **Set Role:** Choose role to ping on open/close request.\n"
            "📑 **Templates:** Add/Remove Smart Replies.\n"
            "📤 **Send Panel:** Post the widget to this channel."
        )
        embed.add_field(name="🕹️ Controls", value=controls_desc, inline=False)
        return embed

    async def refresh_dashboard(self, interaction):
        embed = self.create_embed()
        if interaction.response.is_done(): await interaction.message.edit(embed=embed, view=self)
        else: await interaction.response.edit_message(embed=embed, view=self)

    @ui.button(label="Edit Design", style=discord.ButtonStyle.primary, emoji="📝", row=1)
    async def edit(self, interaction: discord.Interaction, button: ui.Button): await interaction.response.send_modal(ConfigTextModal(self.config, self))
    @ui.button(label="Set Role", style=discord.ButtonStyle.secondary, emoji="🔔", row=1)
    async def role(self, interaction: discord.Interaction, button: ui.Button): await interaction.response.edit_message(embed=discord.Embed(title="Select Role"), view=RoleSelectionView(self))
    
    @ui.button(label="Templates", style=discord.ButtonStyle.secondary, emoji="📑", row=1)
    async def templates(self, interaction: discord.Interaction, button: ui.Button):
        # --- THIS IS THE FIX ---
        # Fetch fresh config to ensure list is up to date
        conf = get_config(self.guild_id)
        templates = conf.get("templates", {})
        
        embed = discord.Embed(title="Template Manager", color=discord.Color.gold())
        if templates:
            desc = ""
            for name, data in templates.items():
                txt = data if isinstance(data, str) else data.get("content", "")
                img = "🖼️" if (isinstance(data, dict) and data.get("image")) else ""
                desc += f"• **{name}**: {txt[:40]}... {img}\n"
            embed.description = desc
        else:
            embed.description = "No active templates. Click 'Add Template' to create one."
            
        await interaction.response.send_message(embed=embed, view=TemplateManagerView(self.guild_id), ephemeral=True)

    @ui.button(label="Send Panel", style=discord.ButtonStyle.success, emoji="📤", row=2)
    async def send(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.channel.send(embed=discord.Embed(title=self.config['title'], description=self.config['desc'], color=discord.Color.green()), view=TicketLaunchView(self.config['btn_text'], self.config['btn_emoji']))
        await interaction.response.send_message("✅ Sent!", ephemeral=True)
    @ui.button(label="Close Menu", style=discord.ButtonStyle.danger, emoji="✖️", row=2)
    async def close_menu(self, interaction: discord.Interaction, button: ui.Button): await interaction.response.edit_message(content="👋 Config closed.", embed=None, view=None)

# --- COG & COMMANDS ---

class Tickets(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def cog_load(self):
        self.bot.add_view(TicketLaunchView("Open Ticket", "📩"))
        self.bot.add_view(TicketActionsView())

    @commands.hybrid_command(name="ticket", description="Open the Ticket Administration Dashboard.")
    @commands.has_permissions(administrator=True)
    async def ticket_cmd(self, ctx):
        view = AdminDashboardView(ctx.guild.id)
        embed = view.create_embed()
        await ctx.send(embed=embed, view=view)

    # --- TICKET MANAGEMENT COMMANDS ---
    @commands.hybrid_group(name="ticket_manage", description="Manage active tickets.")
    async def t_manage(self, ctx): pass

    @t_manage.command(name="add", description="Add user to ticket.")
    @commands.has_permissions(manage_messages=True)
    async def add_member(self, ctx, member: discord.Member):
        if not ctx.channel.name.startswith("ticket-"): return await ctx.send("❌ Tickets only.", ephemeral=True)
        await ctx.channel.set_permissions(member, read_messages=True, send_messages=True)
        await ctx.send(f"✅ Added {member.mention}.")

    @t_manage.command(name="remove", description="Remove user from ticket.")
    @commands.has_permissions(manage_messages=True)
    async def remove_member(self, ctx, member: discord.Member):
        if not ctx.channel.name.startswith("ticket-"): return await ctx.send("❌ Tickets only.", ephemeral=True)
        await ctx.channel.set_permissions(member, read_messages=False, send_messages=False)
        await ctx.send(f"👋 Removed {member.mention}.")

    @t_manage.command(name="anon", description="Reply anonymously.")
    @commands.has_permissions(manage_messages=True)
    async def anon_cmd(self, ctx, *, message: str):
        await ctx.message.delete()
        embed = discord.Embed(description=message, color=discord.Color.blue())
        embed.set_author(name="Support Staff (Anonymous)", icon_url=ctx.guild.icon.url)
        embed.set_footer(text="Staff Reply")
        await ctx.send(embed=embed)

    @commands.Cog.listener()
    async def on_interaction(self, interaction):
        if interaction.type != discord.InteractionType.component: return
        if interaction.data.get("custom_id") != "ticket_create_v6": return
        conf = get_config(interaction.guild.id)
        existing = discord.utils.get(interaction.guild.text_channels, topic=f"Owner: {interaction.user.id}")
        if existing: return await interaction.response.send_message(f"❌ Ticket exists: {existing.mention}", ephemeral=True)

        try:
            guild = interaction.guild
            user = interaction.user
            overwrites = {guild.default_role: discord.PermissionOverwrite(read_messages=False), user: discord.PermissionOverwrite(read_messages=True, send_messages=True), guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)}
            if conf['ping_role']:
                r = guild.get_role(conf['ping_role'])
                if r: overwrites[r] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
            cat = discord.utils.get(guild.categories, name="Tickets") or await guild.create_category("Tickets")
            chan = await guild.create_text_channel(f"ticket-{user.name}", category=cat, overwrites=overwrites, topic=f"Owner: {user.id}")
            
            welcome = conf['welcome'].replace("{user}", user.mention).replace("{server}", guild.name)
            ping = f"<@&{conf['ping_role']}>" if conf['ping_role'] else ""
            embed = discord.Embed(description=welcome, color=OPEN_COLOR)
            embed.set_footer(text="Status: Active")
            await chan.send(f"{user.mention} {ping}", embed=embed, view=TicketActionsView())
            await interaction.response.send_message(f"✅ Created: {chan.mention}", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Error: {e}", ephemeral=True)

async def setup(bot):
    await bot.add_cog(Tickets(bot))