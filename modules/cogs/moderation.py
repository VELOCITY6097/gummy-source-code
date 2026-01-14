import discord
from discord.ext import commands
from datetime import timedelta
import time
from utils import get_db

class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # --- HELPER: LOG TO DB ---
    def add_warning(self, guild_id, user_id, moderator_id, reason):
        db = get_db()
        warn_data = {
            "guild_id": guild_id,
            "user_id": user_id,
            "mod_id": moderator_id,
            "reason": reason,
            "timestamp": time.time()
        }
        db.warnings.insert_one(warn_data)
        # Return total warnings count
        return db.warnings.count_documents({"guild_id": guild_id, "user_id": user_id})

    # --- COMMANDS ---

    @commands.hybrid_command(name="timeout", description="Timeout (mute) a user.")
    @commands.has_permissions(moderate_members=True)
    async def timeout(self, ctx, member: discord.Member, minutes: int, *, reason: str = "No reason provided"):
        if member.top_role >= ctx.author.top_role:
            return await ctx.send("❌ You cannot timeout someone with a higher or equal role.")
        
        duration = timedelta(minutes=minutes)
        await member.timeout(duration, reason=reason)
        await ctx.send(f"🔇 **{member}** has been timed out for {minutes} minutes.\n📝 Reason: {reason}")

    @commands.hybrid_command(name="untimeout", description="Remove a timeout.")
    @commands.has_permissions(moderate_members=True)
    async def untimeout(self, ctx, member: discord.Member):
        await member.timeout(None)
        await ctx.send(f"🔊 Timeout removed for **{member}**.")

    @commands.hybrid_command(name="kick", description="Kick a user from the server.")
    @commands.has_permissions(kick_members=True)
    async def kick(self, ctx, member: discord.Member, *, reason: str = "No reason provided"):
        if member.top_role >= ctx.author.top_role:
            return await ctx.send("❌ Hierarchy Error: Target role is higher/equal to yours.")
        
        await member.kick(reason=reason)
        await ctx.send(f"👢 **{member}** was kicked. (Reason: {reason})")

    @commands.hybrid_command(name="ban", description="Ban a user from the server.")
    @commands.has_permissions(ban_members=True)
    async def ban(self, ctx, member: discord.Member, *, reason: str = "No reason provided"):
        if member.top_role >= ctx.author.top_role:
            return await ctx.send("❌ Hierarchy Error: Target role is higher/equal to yours.")
        
        await member.ban(reason=reason)
        await ctx.send(f"🔨 **{member}** was BANNED. (Reason: {reason})")

    @commands.hybrid_command(name="warn", description="Warn a user and save to database.")
    @commands.has_permissions(manage_messages=True)
    async def warn(self, ctx, member: discord.Member, *, reason: str):
        if member.bot: return await ctx.send("🤖 You cannot warn bots.")
        
        count = self.add_warning(ctx.guild.id, member.id, ctx.author.id, reason)
        
        embed = discord.Embed(title="⚠️ User Warned", color=discord.Color.orange())
        embed.add_field(name="User", value=f"{member.mention} (`{member.id}`)", inline=True)
        embed.add_field(name="Moderator", value=ctx.author.mention, inline=True)
        embed.add_field(name="Reason", value=reason, inline=False)
        embed.set_footer(text=f"Total Warnings: {count}")
        
        await ctx.send(embed=embed)
        
        # Try DMing the user
        try:
            await member.send(f"⚠️ You were warned in **{ctx.guild.name}**: {reason}")
        except: pass

    @commands.hybrid_command(name="warnings", description="Check warnings for a user.")
    @commands.has_permissions(manage_messages=True)
    async def warnings(self, ctx, member: discord.Member):
        db = get_db()
        cursor = db.warnings.find({"guild_id": ctx.guild.id, "user_id": member.id}).sort("timestamp", -1)
        warnings = list(cursor)
        
        if not warnings:
            return await ctx.send(f"✅ **{member.name}** has no warnings.")

        embed = discord.Embed(title=f"📜 Warnings for {member.name}", color=discord.Color.yellow())
        
        desc = ""
        for w in warnings[:10]: # Show last 10
            mod = ctx.guild.get_member(w['mod_id'])
            mod_name = mod.name if mod else "Unknown"
            date = f"<t:{int(w['timestamp'])}:R>"
            desc += f"• **{date}** by `{mod_name}`: {w['reason']}\n"
            
        embed.description = desc
        embed.set_footer(text=f"Total Records: {len(warnings)}")
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Moderation(bot))
