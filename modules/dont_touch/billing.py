import discord
from discord import app_commands
from discord.ext import commands
import secrets
from datetime import datetime
from utils import OWNER_ID, SUPPORT_SERVER_ID, PREMIUM_ROLE_ID, get_db

# ---------------------------------------------------------
# ⚠️ ACTION REQUIRED: REPLACE THIS LINK WITH YOUR REAL INVITE
SUPPORT_INVITE_LINK = "https://discord.gg/xHx7S5q482"
# ---------------------------------------------------------

class Billing(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Register Context Menu for Right-Clicking Users
        self.ctx_menu = app_commands.ContextMenu(
            name="Grant Premium Key",
            callback=self.generate_key_context,
        )
        self.bot.tree.add_command(self.ctx_menu)

    async def cog_unload(self):
        # Cleanup menu on reload
        self.bot.tree.remove_command(self.ctx_menu.name, type=self.ctx_menu.type)

    def is_owner():
        async def predicate(ctx):
            return ctx.author.id == OWNER_ID
        return commands.check(predicate)

    # --- CONTEXT MENU CALLBACK (Right Click -> Apps) ---
    async def generate_key_context(self, interaction: discord.Interaction, user: discord.User):
        # 1. Permission Check
        if interaction.user.id != OWNER_ID:
            return await interaction.response.send_message("❌ Owner Only.", ephemeral=True)

        await interaction.response.defer(ephemeral=True)

        # 2. Generate Logic
        key = f"GUMIT-{secrets.token_hex(4).upper()}"
        db = get_db()
        db.license_keys.insert_one({
            "_id": key,
            "created_at": datetime.now(),
            "target_user": user.id # Optional tracking
        })

        # 3. Create Instructions Embed
        embed = discord.Embed(
            title="🎁 You received a Premium Key!",
            description=f"Congratulations **{user.name}**! You have been gifted a Gumit Premium License.",
            color=discord.Color.gold()
        )
        embed.add_field(name="🔑 Your Key", value=f"```\n{key}\n```", inline=False)
        embed.add_field(
            name="🚀 How to Activate", 
            value=f"1. Join the **[Support Server]({SUPPORT_INVITE_LINK})**\n2. Run the command:\n`/redeem key:{key}`", 
            inline=False
        )
        embed.set_footer(text="Do not share this key. It is one-time use.")
        embed.set_thumbnail(url="https://cdn-icons-png.flaticon.com/512/616/616490.png") # Gift icon

        # 4. DM the User
        try:
            await user.send(embed=embed)
            await interaction.followup.send(f"✅ **Success:** Key generated and sent to {user.mention}.", ephemeral=True)
        except discord.Forbidden:
            await interaction.followup.send(
                f"⚠️ **DM Failed:** {user.mention} has DMs off.\nHere is the key to send manually: `{key}`", 
                ephemeral=True
            )

    # --- COMMANDS ---

    @commands.hybrid_command(name="genkey", description="Owner Only: Generate Premium Key manually.")
    @is_owner()
    async def genkey(self, ctx):
        await ctx.defer(ephemeral=True)
        key = f"GUMIT-{secrets.token_hex(4).upper()}"
        db = get_db()
        db.license_keys.insert_one({"_id": key, "created_at": datetime.now()})
        await ctx.send(f"🔑 Key Generated: `{key}`", ephemeral=True)

    @commands.hybrid_command(name="deactivate_key", description="Owner Only: Delete an unused key.")
    @is_owner()
    async def deactivate_key(self, ctx, key: str):
        await ctx.defer(ephemeral=True)
        db = get_db()
        result = db.license_keys.delete_one({"_id": key})
        
        if result.deleted_count > 0:
            await ctx.send(f"🗑️ Key `{key}` has been deactivated/deleted.", ephemeral=True)
        else:
            await ctx.send(f"❌ Key `{key}` not found (or already used).", ephemeral=True)

    @commands.hybrid_command(name="revoke_premium", description="Owner Only: Remove Premium from a user.")
    @is_owner()
    async def revoke_premium(self, ctx, user: discord.User):
        await ctx.defer(ephemeral=True)
        db = get_db()
        result = db.premium_users.delete_one({"_id": user.id})
        
        if result.deleted_count > 0:
            # Try to remove role if possible
            try:
                support_guild = self.bot.get_guild(SUPPORT_SERVER_ID)
                if support_guild:
                    member = await support_guild.fetch_member(user.id)
                    role = support_guild.get_role(PREMIUM_ROLE_ID)
                    if member and role:
                        await member.remove_roles(role, reason="Premium Revoked by Owner")
            except: 
                pass # Ignore role errors if user left server
            
            await ctx.send(f"📉 **Revoked:** {user.mention} is no longer Premium.", ephemeral=True)
        else:
            await ctx.send(f"⚠️ {user.mention} is not in the database.", ephemeral=True)

    @commands.hybrid_command(name="redeem", description="Redeem Premium Key.")
    async def redeem(self, ctx, key: str):
        await ctx.defer(ephemeral=True)
        db = get_db()
        
        # 1. Validate Key
        key_doc = db.license_keys.find_one({"_id": key})
        if not key_doc:
            return await ctx.send("❌ **Invalid Key.** Please check the code and try again.", ephemeral=True)

        # 2. Check Premium Status
        if db.premium_users.find_one({"_id": ctx.author.id}):
            return await ctx.send("⚠️ **You are already a Premium Member!**", ephemeral=True)

        # 3. Verify Support Server
        # Force convert to integer to prevent config errors
        try:
            target_guild_id = int(SUPPORT_SERVER_ID)
            target_role_id = int(PREMIUM_ROLE_ID)
        except (ValueError, TypeError):
            return await ctx.send("❌ **Config Error:** IDs in `.env` are invalid.", ephemeral=True)

        support_guild = self.bot.get_guild(target_guild_id)
        if not support_guild:
            return await ctx.send("❌ **System Error:** Main Support Server not found.", ephemeral=True)

        member_in_support = None
        try:
            member_in_support = await support_guild.fetch_member(ctx.author.id)
        except discord.NotFound:
            pass 

        # 4. Enforce Join Requirement
        if not member_in_support:
            embed = discord.Embed(
                title="🔒 Activation Locked",
                description=(
                    f"**Requirement Missing:** You must be a member of the Official Support Server to activate Premium.\n\n"
                    f"1️⃣ **[Click Here to Join Support Server]({SUPPORT_INVITE_LINK})**\n"
                    f"2️⃣ Run `/redeem {{ key }}` again here after joining."
                ),
                color=discord.Color.red()
            )
            embed.set_footer(text="Verification Required")
            embed.set_thumbnail(url="https://cdn-icons-png.flaticon.com/512/564/564619.png")
            return await ctx.send(embed=embed, ephemeral=True)

        # 5. Success
        try:
            db.premium_users.insert_one({
                "_id": ctx.author.id,
                "added_at": datetime.now()
            })
            
            db.license_keys.delete_one({"_id": key})
            
            # Grant Role
            role_status = ""
            try:
                role = support_guild.get_role(target_role_id)
                if role and support_guild.me.guild_permissions.manage_roles and support_guild.me.top_role > role:
                    await member_in_support.add_roles(role, reason="Redeemed Premium Key")
                    role_status = f"\n🏷️ **Role:** Granted {role.mention} in support server."
            except Exception as e:
                print(f"Role Error: {e}")

            embed = discord.Embed(
                title="🌟 Premium Activated Successfully!",
                description=(
                    f"Welcome to **Gumit Gold**, {ctx.author.mention}!\n\n"
                    "✅ **Global Access:** You can now use Premium commands in **ANY server**."
                    f"{role_status}"
                ),
                color=discord.Color.gold()
            )
            if ctx.author.avatar:
                embed.set_thumbnail(url=ctx.author.avatar.url)
            
            await ctx.send(embed=embed)

        except Exception as e:
            print(f"Redeem Error: {e}")
            await ctx.send("❌ An unexpected database error occurred.", ephemeral=True)

async def setup(bot):
    await bot.add_cog(Billing(bot))