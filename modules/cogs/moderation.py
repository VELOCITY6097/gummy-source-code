import discord
from discord.ext import commands
from datetime import datetime
from utils import get_db

class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # --- PERMISSION CHECKS ---
    def is_moderator(self, ctx):
        """Checks if user is admin or has configured mod role."""
        if ctx.author.guild_permissions.administrator: return True
        
        db = get_db()
        config = db.guild_configs.find_one({"_id": ctx.guild.id})
        if config and "mod_roles" in config:
            return any(r.id in config["mod_roles"] for r in ctx.author.roles)
        return False

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Global check for Slash Commands in this Cog."""
        if interaction.user.guild_permissions.administrator: return True
        
        db = get_db()
        config = db.guild_configs.find_one({"_id": interaction.guild.id})
        if config and "mod_roles" in config:
             if any(r.id in config["mod_roles"] for r in interaction.user.roles):
                 return True
        
        await interaction.response.send_message("⛔ **Access Denied:** You do not have permission to use moderation commands.", ephemeral=True)
        return False

    # --- HIERARCHY VALIDATION (ROBUSTNESS) ---
    def validate_action(self, ctx, member: discord.Member):
        """Checks if the target is valid to be punished."""
        # 1. Check Self
        if member.id == ctx.author.id:
            return "❌ You cannot punish yourself."
        
        # 2. Check Bot
        if member.id == self.bot.user.id:
            return "❌ I cannot punish myself."

        # 3. Check Guild Owner
        if member.id == ctx.guild.owner_id:
            return "👑 You cannot punish the Server Owner."

        # 4. Check Mod vs Target Hierarchy (Ignore if Mod is Owner)
        if ctx.author.id != ctx.guild.owner_id:
            if member.top_role >= ctx.author.top_role:
                return "🛡️ **Hierarchy Error:** This user has a role equal to or higher than yours."

        # 5. Check Bot vs Target Hierarchy
        if member.top_role >= ctx.guild.me.top_role:
            return "🤖 **Bot Hierarchy Error:** I cannot punish this user because their role is higher than mine."
            
        return None # No errors

    # --- COMMANDS ---

    @commands.hybrid_command(name="kick", description="Kick a user from the server.")
    async def kick(self, ctx, member: discord.Member, *, reason: str = "No reason provided"):
        if not self.is_moderator(ctx):
            return await ctx.send("⛔ **Access Denied**", delete_after=3)

        # 1. Run Robust Checks
        error = self.validate_action(ctx, member)
        if error:
            # Send error ephemerally so only mod sees it
            return await ctx.send(error, ephemeral=True)

        # Defer immediately to allow time for DMing, set ephemeral=True here!
        await ctx.defer(ephemeral=True)

        # 2. Attempt DM
        dm_status = "✅ DM Sent"
        try:
            embed = discord.Embed(title=f"You were Kicked from {ctx.guild.name}", color=discord.Color.red())
            embed.add_field(name="Reason", value=reason)
            embed.add_field(name="Moderator", value=ctx.author.name)
            await member.send(embed=embed)
        except discord.Forbidden:
            dm_status = "❌ DM Failed (User has DMs off)"

        # 3. Perform Kick
        try:
            await member.kick(reason=reason)
            
            # 4. Success Embed (Private/Ephemeral)
            embed = discord.Embed(title="👢 User has been kicked", color=discord.Color.orange())
            embed.add_field(name="User", value=f"{member.name} (`{member.id}`)", inline=True)
            embed.add_field(name="Reason", value=reason, inline=True)
            embed.set_footer(text=f"{dm_status} • Action by {ctx.author.name}")
            embed.timestamp = datetime.now()
            
            await ctx.send(embed=embed, ephemeral=True)

        except discord.Forbidden:
            await ctx.send("❌ **Error:** I do not have the `Kick Members` permission.", ephemeral=True)
        except Exception as e:
            await ctx.send(f"❌ **Unexpected Error:** {e}", ephemeral=True)

    @commands.hybrid_command(name="ban", description="Ban a user from the server.")
    async def ban(self, ctx, member: discord.Member, *, reason: str = "No reason provided"):
        if not self.is_moderator(ctx):
            return await ctx.send("⛔ **Access Denied**", delete_after=3)

        # 1. Run Robust Checks
        error = self.validate_action(ctx, member)
        if error:
            return await ctx.send(error, ephemeral=True)

        await ctx.defer(ephemeral=True)

        # 2. Attempt DM
        dm_status = "✅ DM Sent"
        try:
            embed = discord.Embed(title=f"You were Banned from {ctx.guild.name}", color=discord.Color.dark_red())
            embed.add_field(name="Reason", value=reason)
            embed.add_field(name="Moderator", value=ctx.author.name)
            await member.send(embed=embed)
        except:
            dm_status = "❌ DM Failed (User has DMs off)"

        # 3. Perform Ban
        try:
            # delete_message_days=0 prevents deleting history.
            await member.ban(reason=reason, delete_message_days=0)
            
            # 4. Success Embed (Private/Ephemeral)
            embed = discord.Embed(title="🔨 User has been banned", color=discord.Color.red())
            embed.set_thumbnail(url=member.avatar.url if member.avatar else None)
            embed.add_field(name="Target", value=f"**{member}**\nID: `{member.id}`", inline=False)
            embed.add_field(name="Reason", value=reason, inline=False)
            embed.set_footer(text=f"{dm_status} • Action by {ctx.author.name}")
            embed.timestamp = datetime.now()
            
            await ctx.send(embed=embed, ephemeral=True)

        except discord.Forbidden:
            await ctx.send("❌ **Error:** I do not have the `Ban Members` permission.", ephemeral=True)
        except Exception as e:
            await ctx.send(f"❌ **Unexpected Error:** {e}", ephemeral=True)

    @commands.hybrid_command(name="unban", description="Unban a user by ID.")
    async def unban(self, ctx, user_id: str, *, reason: str = "No reason provided"):
        if not self.is_moderator(ctx):
            return await ctx.send("⛔ **Access Denied**", delete_after=3)

        await ctx.defer(ephemeral=True)

        try:
            user_obj = discord.Object(id=int(user_id))
            await ctx.guild.unban(user_obj, reason=reason)
            
            embed = discord.Embed(title="🔓 User has been unbanned", color=discord.Color.green())
            embed.description = f"User ID `{user_id}` restored access."
            embed.add_field(name="Moderator", value=ctx.author.mention)
            
            await ctx.send(embed=embed, ephemeral=True)
        except discord.NotFound:
            await ctx.send("❌ User not found in ban list.", ephemeral=True)
        except ValueError:
            await ctx.send("❌ Invalid User ID provided.", ephemeral=True)
        except Exception as e:
            await ctx.send(f"❌ Error: {e}", ephemeral=True)

async def setup(bot):
    await bot.add_cog(Moderation(bot))