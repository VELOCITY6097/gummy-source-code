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
            "**`/redeem [key]`**\nActivate a Premium License.\n\n"
            "**`/snipe`**\nReveal the last deleted message in the channel.\n\n"
            "**`/afk [reason]`**\nSet your status to AFK (Auto-reply to mentions).\n\n"
            "**`/uptime`**\nCheck how long the bot has been online."
        )
        embed.add_field(name="🛠️ General Commands", value=general_cmds, inline=False)

        # Moderation & Admin Commands
        mod_cmds = (
            "**`/stick [message]`**\nStick a message to the bottom of the chat.\n\n"
            "**`/unstick`**\nRemove the sticky message.\n\n"
            "**`/trigger`**\nManage smart auto-response triggers.\n\n"
            "**`/purge [amount]`**\nBulk delete messages (Safe Mode with Confirmation).\n\n"
            "**`/setprefix [prefix]`**\nChange the bot's text prefix."
        )
        embed.add_field(name="🛡️ Moderation & Admin", value=mod_cmds, inline=False)

        # Premium Features
        premium_cmds = (
            "*> Requires Gumit Gold*\n\n"
            "**`/ai_chat [query]`**\nChat with the advanced Gemini/Llama AI.\n\n"
            "**`/reset_ai`**\nClear your AI conversation history."
        )
        embed.add_field(name="💎 Premium Features", value=premium_cmds, inline=False)

        # Fun & Stats Commands
        fun_cmds = (
            "**`/membercount`**\nView server member statistics (Humans vs Bots).\n\n"
            "**`/userinfo [user]`**\nView detailed user information.\n\n"
            "**`/serverinfo`**\nView server details.\n\n"
            "**`/avatar [user]`**\nGet a user's profile picture.\n\n"
            "**`/banner [user]`**\nGet a user's profile banner."
        )
        embed.add_field(name="📊 Fun & Statistics", value=fun_cmds, inline=False)
        
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Help(bot))