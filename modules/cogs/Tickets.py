import discord
from discord.ext import commands
from discord import ui

# --- VIEWS ---

class TicketControlView(ui.View):
    def __init__(self):
        super().__init__(timeout=None) # Persistent view

    @ui.button(label="Close Ticket", style=discord.ButtonStyle.red, emoji="🔒", custom_id="ticket_close_btn")
    async def close(self, interaction: discord.Interaction, button: ui.Button):
        # Confirmation
        await interaction.response.send_message("⚠️ Deleting ticket in 5 seconds...", ephemeral=True)
        await asyncio.sleep(5)
        await interaction.channel.delete()

class TicketLaunchView(ui.View):
    def __init__(self):
        super().__init__(timeout=None) # Persistent view

    @ui.button(label="Open Ticket", style=discord.ButtonStyle.primary, emoji="📩", custom_id="ticket_create_btn")
    async def create_ticket(self, interaction: discord.Interaction, button: ui.Button):
        guild = interaction.guild
        user = interaction.user
        
        # Check for existing ticket
        existing_channel = discord.utils.get(guild.channels, name=f"ticket-{user.name.lower()}")
        if existing_channel:
            return await interaction.response.send_message(f"❌ You already have a ticket: {existing_channel.mention}", ephemeral=True)

        # Create Private Channel
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_channels=True)
        }
        
        # Add Admin/Mod role permissions if configured (simple version: allows anyone with Manage Channels)
        
        category = discord.utils.get(guild.categories, name="Tickets")
        if not category:
            category = await guild.create_category("Tickets")

        try:
            channel = await guild.create_text_channel(
                name=f"ticket-{user.name}",
                category=category,
                overwrites=overwrites,
                topic=f"Ticket for {user.id}"
            )
        except Exception as e:
            return await interaction.response.send_message(f"❌ Error creating channel: {e}", ephemeral=True)

        # Send Control Panel inside the new ticket
        embed = discord.Embed(
            title=f"🎫 Ticket: {user.name}",
            description="Support will be with you shortly.\nClick 🔒 to close this ticket.",
            color=discord.Color.green()
        )
        await channel.send(f"{user.mention} Welcome!", embed=embed, view=TicketControlView())
        
        await interaction.response.send_message(f"✅ Ticket created: {channel.mention}", ephemeral=True)

# --- COG ---

import asyncio

class Tickets(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def cog_load(self):
        # Register persistent views so they work after bot restart
        self.bot.add_view(TicketLaunchView())
        self.bot.add_view(TicketControlView())

    @commands.hybrid_command(name="ticketpanel", description="Setup the support ticket panel.")
    @commands.has_permissions(administrator=True)
    async def ticket_panel(self, ctx):
        embed = discord.Embed(
            title="📩 Support Center",
            description="Click the button below to open a private support ticket.",
            color=discord.Color.blurple()
        )
        embed.set_thumbnail(url=ctx.guild.icon.url if ctx.guild.icon else None)
        embed.set_footer(text="Gumit Support System")
        
        await ctx.send(embed=embed, view=TicketLaunchView())
        await ctx.send("✅ Panel setup complete!", ephemeral=True)

async def setup(bot):
    await bot.add_cog(Tickets(bot))
