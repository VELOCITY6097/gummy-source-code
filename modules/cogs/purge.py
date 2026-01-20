import discord
from discord.ext import commands
import asyncio
import time
from datetime import datetime, timedelta, timezone

class PurgeView(discord.ui.View):
    def __init__(self, ctx):
        super().__init__(timeout=60)
        self.ctx = ctx
        self.confirmed = False

    @discord.ui.button(label="Confirm Purge", style=discord.ButtonStyle.danger, emoji="🗑️")
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message("❌ Not your command.", ephemeral=True)
        
        self.confirmed = True
        self.disable_all()
        # Edit the existing message to show processing state
        await interaction.response.edit_message(content="**🗑️ Processing Purge...**", embed=None, view=None)
        self.stop()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary, emoji="✖️")
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message("❌ Not your command.", ephemeral=True)
        
        self.confirmed = False
        await interaction.response.edit_message(content="✅ **Purge Cancelled.**", embed=None, view=None)
        self.stop()

    def disable_all(self):
        for child in self.children:
            child.disabled = True

class Purge(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.active_purges = set()

    @commands.hybrid_command(name="purge", description="Robustly delete messages (Admin Only).")
    @commands.has_permissions(administrator=True)
    async def purge(self, ctx, amount: int):
        if amount < 1:
            return await ctx.send("❌ Amount must be greater than 0.", ephemeral=True)
        
        if ctx.channel.id in self.active_purges:
            return await ctx.send("⚠️ A purge is already running in this channel. Please wait.", ephemeral=True)

        # 1. ANALYZE PHASE
        # We defer immediately so we have a webhook/interaction to edit later
        if ctx.interaction:
            await ctx.defer(ephemeral=True)
        
        two_weeks_ago = datetime.now(timezone.utc) - timedelta(days=14)
        
        msgs_to_analyze = []
        old_msgs_count = 0
        link_count = 0
        image_count = 0
        
        scan_limit = min(amount, 500)
        
        # Determine iterator for history
        history_iterator = ctx.channel.history(limit=scan_limit)
        async for msg in history_iterator:
            msgs_to_analyze.append(msg)
            if msg.created_at < two_weeks_ago:
                old_msgs_count += 1
            if len(msg.attachments) > 0:
                image_count += 1
            if "http" in msg.content:
                link_count += 1

        # 2. REPORT EMBED
        embed = discord.Embed(
            title="⚠️ Confirm Purge",
            description=f"Request to delete **{amount}** messages.",
            color=discord.Color.orange()
        )
        embed.add_field(name="Analyzed Sample", value=f"{len(msgs_to_analyze)} msgs", inline=True)
        embed.add_field(name="Contains Links", value=str(link_count), inline=True)
        embed.add_field(name="Images/Files", value=str(image_count), inline=True)
        
        if old_msgs_count > 0:
            embed.add_field(
                name="⚠️ Old Messages (>14 days)", 
                value=f"{old_msgs_count}+ found.\n*These cannot be bulk deleted and will be skipped.*", 
                inline=False
            )

        embed.set_footer(text="Click Confirm to start the robust deletion process.")
        
        view = PurgeView(ctx)
        
        # Send the dashboard message
        # We store 'dashboard_msg' to edit it later if needed (mostly for text commands)
        if ctx.interaction:
            dashboard_msg = await ctx.interaction.followup.send(embed=embed, view=view, ephemeral=True)
        else:
            dashboard_msg = await ctx.send(embed=embed, view=view)

        await view.wait()

        if not view.confirmed:
            # If timed out or cancelled, we stop here.
            # The view handles the "Cancelled" edit message on button click.
            # If it timed out, we might want to edit it to say "Timed Out".
            if ctx.interaction and not view.confirmed:
                try:
                    await ctx.interaction.edit_original_response(content="❌ **Purge Timed Out.**", embed=None, view=None)
                except:
                    pass
            elif not ctx.interaction and not view.confirmed:
                try: 
                    await dashboard_msg.edit(content="❌ **Purge Timed Out.**", embed=None, view=None)
                except: 
                    pass
            return

        # 3. EXECUTE PHASE
        self.active_purges.add(ctx.channel.id)
        start_time = time.time()
        total_deleted = 0

        try:
            deleted_list = await ctx.channel.purge(
                limit=amount,
                check=lambda m: not m.pinned, 
                bulk=True, 
                before=None, 
                after=two_weeks_ago 
            )
            total_deleted = len(deleted_list)
            elapsed = round(time.time() - start_time, 2)
            
            success_embed = discord.Embed(
                title="✅ Purge Complete",
                color=discord.Color.green(),
                description=f"Deleted **{total_deleted}** messages in `{elapsed}s`."
            )
            
            if total_deleted < amount and old_msgs_count > 0:
                success_embed.add_field(
                    name="ℹ️ Note", 
                    value="Some messages were skipped because they are older than 14 days (Discord API Limitation)."
                )

            # EDIT THE SAME MESSAGE WITH SUCCESS EMBED
            if ctx.interaction:
                await ctx.interaction.edit_original_response(content=None, embed=success_embed, view=None)
            else:
                await dashboard_msg.edit(content=None, embed=success_embed, view=None)

        except Exception as e:
            error_content = f"❌ Critical Purge Error: {e}"
            if ctx.interaction:
                await ctx.interaction.edit_original_response(content=error_content, embed=None, view=None)
            else:
                await dashboard_msg.edit(content=error_content, embed=None, view=None)
            
            # Raise so devnoti catches it
            raise e 
        
        finally:
            self.active_purges.discard(ctx.channel.id)

async def setup(bot):
    await bot.add_cog(Purge(bot))
