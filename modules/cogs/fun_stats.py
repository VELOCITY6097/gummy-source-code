import discord
from discord.ext import commands

class FunStats(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(name="membercount", description="Show human vs bot count.")
    async def membercount(self, ctx):
        guild = ctx.guild
        humans = len([m for m in guild.members if not m.bot])
        bots = len([m for m in guild.members if m.bot])
        
        embed = discord.Embed(title=f"📊 Members: {guild.member_count}", color=discord.Color.blue())
        embed.add_field(name="👤 Humans", value=str(humans), inline=True)
        embed.add_field(name="🤖 Bots", value=str(bots), inline=True)
        embed.set_thumbnail(url=guild.icon.url if guild.icon else None)
        
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="userinfo", description="Get details about a user.")
    async def userinfo(self, ctx, member: discord.Member = None):
        member = member or ctx.author
        
        embed = discord.Embed(title=f"User Info: {member.name}", color=member.color)
        embed.set_thumbnail(url=member.avatar.url if member.avatar else member.default_avatar.url)
        
        embed.add_field(name="🆔 ID", value=member.id, inline=True)
        embed.add_field(name="📅 Created At", value=member.created_at.strftime("%Y-%m-%d %H:%M"), inline=True)
        embed.add_field(name="📥 Joined At", value=member.joined_at.strftime("%Y-%m-%d %H:%M"), inline=True)
        
        roles = [r.mention for r in member.roles if r.name != "@everyone"]
        role_str = ", ".join(roles) if roles else "None"
        if len(role_str) > 1024: role_str = f"{len(roles)} Roles"
        
        embed.add_field(name=f"🎭 Roles ({len(roles)})", value=role_str, inline=False)
        
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="serverinfo", description="Get details about this server.")
    async def serverinfo(self, ctx):
        guild = ctx.guild
        
        embed = discord.Embed(title=f"Server Info: {guild.name}", color=discord.Color.gold())
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)
            
        embed.add_field(name="👑 Owner", value=guild.owner.mention, inline=True)
        embed.add_field(name="👥 Members", value=str(guild.member_count), inline=True)
        embed.add_field(name="💬 Channels", value=str(len(guild.channels)), inline=True)
        embed.add_field(name="📅 Created On", value=guild.created_at.strftime("%Y-%m-%d"), inline=True)
        embed.add_field(name="🆔 Server ID", value=guild.id, inline=True)
        
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="avatar", description="Get a user's profile picture.")
    async def avatar(self, ctx, user: discord.User = None):
        user = user or ctx.author
        
        embed = discord.Embed(title=f"{user.name}'s Avatar", color=discord.Color.purple())
        embed.set_image(url=user.avatar.url if user.avatar else user.default_avatar.url)
        
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="banner", description="Get a user's profile banner.")
    async def banner(self, ctx, user: discord.User = None):
        user = user or ctx.author
        # Fetch user to get banner info (cached user object doesn't always have it)
        user = await self.bot.fetch_user(user.id)
        
        if user.banner:
            embed = discord.Embed(title=f"{user.name}'s Banner", color=discord.Color.purple())
            embed.set_image(url=user.banner.url)
            await ctx.send(embed=embed)
        else:
            await ctx.send(f"❌ **{user.name}** does not have a banner set.", ephemeral=True)

async def setup(bot):
    await bot.add_cog(FunStats(bot))