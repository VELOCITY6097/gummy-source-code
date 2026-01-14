import discord
from discord.ext import commands
import logging

class ErrorHandler(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.logger = logging.getLogger("ErrorHandler")

    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        # Ignore if command has its own error handler
        if hasattr(ctx.command, 'on_error'):
            return

        # 1. Permission Errors
        if isinstance(error, commands.MissingPermissions):
            perms = ", ".join(error.missing_permissions)
            return await ctx.send(f"⛔ **Access Denied:** You need `{perms}` permissions.", delete_after=10)
        
        if isinstance(error, commands.BotMissingPermissions):
            perms = ", ".join(error.missing_permissions)
            return await ctx.send(f"❌ I cannot do this. I am missing `{perms}` permissions.")

        # 2. Cooldowns
        if isinstance(error, commands.CommandOnCooldown):
            return await ctx.send(f"⏳ **Cooldown:** Try again in `{round(error.retry_after, 1)}s`.", delete_after=5)

        # 3. User Errors
        if isinstance(error, commands.MissingRequiredArgument):
            return await ctx.send(f"⚠️ **Missing Argument:** Usage: `{ctx.prefix}{ctx.command.qualified_name} {ctx.command.signature}`")
        
        if isinstance(error, commands.BadArgument):
            return await ctx.send("⚠️ **Invalid Argument:** Please check your input.")

        # 4. Unknown Errors (Log them!)
        self.logger.error(f"Command '{ctx.command}' failed: {error}", exc_info=True)
        # Only show generic error to user if not in debug mode
        await ctx.send("❌ An internal error occurred. The developer has been notified.")

async def setup(bot):
    await bot.add_cog(ErrorHandler(bot))
