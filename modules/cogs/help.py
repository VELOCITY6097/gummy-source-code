import discord
from discord.ext import commands

class Help(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(name="help", description="Show the command menu.")
    async def help_command(self, ctx):
        embed = discord.Embed(
            title="🤖 Gumit Bot Help", 
            description="Here are the available commands for Gumit Bot.",
            color=discord.Color.gold()
        )
        embed.set_footer(text="Gumit Systems • All Systems Operational")
        embed.set_thumbnail(url=self.bot.user.avatar.url if self.bot.user.avatar else None)

        # General Commands
        general_cmds = (
            "**`/snipe`**\nReveal the last deleted message in the channel.\n\n"
            "**`/afk [reason]`**\nSet your status to AFK (Auto-reply to mentions)."
        )
        embed.add_field(name="🛠️ General Commands", value=general_cmds, inline=False)

        # Moderation & Admin Commands
        # Includes commands from moderation.py, purge.py, sticky.py, and temprole from general.py
        mod_cmds = (
            "**`/kick [member] [reason]`**\nKick a user from the server.\n\n"
            "**`/ban [member] [reason]`**\nBan a user from the server.\n\n"
            "**`/unban [user_id]`**\nUnban a user by their ID.\n\n"
            "**`/temprole [member] [role] [duration]`**\nTemporarily assign a role (e.g. `1h`, `30m`).\n\n"
            "**`/purge [amount]`**\nBulk delete messages (Safe Mode with Confirmation).\n\n"
            "**`/stick`** / **`/unstick`**\nStick or unstick a message in the channel."
        )
        embed.add_field(name="🛡️ Moderation & Admin", value=mod_cmds, inline=False)

        # Configuration Commands
        # Includes commands from configuration.py and general.py
        config_cmds = (
            "**`/setup`**\nRun the interactive server setup wizard.\n\n"
            "**`/setwelcome [channel]`**\nSet the welcome message channel.\n\n"
            "**`/setprefix [prefix]`**\nChange the bot's text prefix."
        )
        embed.add_field(name="⚙️ Configuration", value=config_cmds, inline=False)

        # Ticket System Commands
        # Includes commands from Tickets.py
        ticket_cmds = (
            "**`/ticket`**\nOpen the Ticket Administration Dashboard.\n\n"
            "**`/ticket_manage add [member]`**\nAdd a user to a ticket channel.\n\n"
            "**`/ticket_manage remove [member]`**\nRemove a user from a ticket channel.\n\n"
            "**`/ticket_manage anon [message]`**\nSend an anonymous reply in a ticket."
        )
        embed.add_field(name="🎫 Ticket System", value=ticket_cmds, inline=False)
        
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Help(bot))s
