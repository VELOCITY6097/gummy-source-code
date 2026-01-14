import discord
from discord.ext import commands
import asyncio

class PurgeView(discord.ui.View):
    def __init__(self, ctx, amount, messages_to_delete):
        super().__init__(timeout=60)
        self.ctx = ctx
        self.amount = amount
        self.messages_to_delete = messages_to_delete
        self.confirmed = False

    @discord.ui.button(label="Confirm Purge", style=discord.ButtonStyle.danger, emoji="🗑️")
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message("❌ This is not your command.", ephemeral=True)
        
        self.confirmed = True
        # Disable buttons to prevent double clicking
        for child in self.children:
            child.disabled = True
        
        await interaction.response.edit_message(content="**🗑️ Purging...**", embed=None, view=self)
        self.stop()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary, emoji="✖️")
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message("❌ This is not your command.", ephemeral=True)
        
        self.confirmed = False
        await interaction.response.edit_message(content="✅ **Purge Cancelled.**", embed=None, view=None)
        self.stop()

class Purge(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(name="purge", description="Safely delete messages (Admin Only).")
    @commands.has_permissions(administrator=True)
    async def purge(self, ctx, amount: int):
        """
        Scans messages first, provides statistics, and asks for confirmation.
        """
        if amount < 1:
            return await ctx.send("❌ Please enter a number greater than 0.")
        
        # Defer if interaction to prevent timeout during analysis
        if ctx.interaction:
            await ctx.defer(ephemeral=True)
        
        # 1. ANALYZE MESSAGES
        # We fetch 'amount' messages to check statistics
        msgs_to_scan = [m async for m in ctx.channel.history(limit=amount)]
        
        link_count = 0
        image_count = 0
        
        for msg in msgs_to_scan:
            # Check for attachments (Images/Files)
            if len(msg.attachments) > 0:
                image_count += 1
            
            # Check for Links (http/https)
            if "http" in msg.content:
                link_count += 1

        # 2. CREATE REPORT EMBED
        embed = discord.Embed(
            title="⚠️ Confirm Purge",
            description=f"You are about to delete **{len(msgs_to_scan)}** messages in {ctx.channel.mention}.",
            color=discord.Color.orange()
        )
        embed.add_field(name="Total Messages", value=str(len(msgs_to_scan)), inline=True)
        embed.add_field(name="Contains Links", value=str(link_count), inline=True)
        embed.add_field(name="Contains Images/Files", value=str(image_count), inline=True)
        embed.set_footer(text="Administrator Permission Verified")

        # 3. ASK FOR CONFIRMATION
        view = PurgeView(ctx, amount, msgs_to_scan)
        
        if ctx.interaction:
            # Send ephemeral follow-up if slash command
            msg = await ctx.interaction.followup.send(embed=embed, view=view, ephemeral=True)
        else:
            msg = await ctx.send(embed=embed, view=view)

        # Wait for button click
        await view.wait()

        if view.confirmed:
            try:
                # 4. EXECUTE PURGE
                # +1 to purge the command message itself if it's not a slash command
                limit_to_purge = amount if ctx.interaction else amount + 1
                deleted = await ctx.channel.purge(limit=limit_to_purge)
                
                success_msg = f"✅ **Purged {len(deleted)} messages.**"
                
                if ctx.interaction:
                    await ctx.interaction.followup.send(success_msg, ephemeral=True)
                else:
                    await ctx.send(success_msg, delete_after=5)
                    # Try to delete the confirmation menu if possible
                    try: await msg.delete()
                    except: pass
            except Exception as e:
                err_msg = f"❌ Error purging: {e}"
                if ctx.interaction:
                    await ctx.interaction.followup.send(err_msg, ephemeral=True)
                else:
                    await ctx.send(err_msg)

async def setup(bot):
    await bot.add_cog(Purge(bot))