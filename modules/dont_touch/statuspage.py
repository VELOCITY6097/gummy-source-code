import discord
from discord.ext import commands, tasks
import datetime
import psutil
import math

# ─── CONFIG ─────────────────────────────────────────────
STATUS_CHANNEL_ID = 1390787417463722165
UPDATE_INTERVAL = 30  # seconds
# ─────────────────────────────────────────────────────────

class StatusPage(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.message_id = None
        self.status_task.start()

    def cog_unload(self):
        self.status_task.cancel()

    # ─── DEBUG COMMAND ────────────────────────────────────
    @commands.command()
    async def teststatus(self, ctx):
        await ctx.send("🕵️ **Running StatusPage diagnostics...**")

        # psutil check
        try:
            cpu = psutil.cpu_percent()
            await ctx.send(f"✅ psutil OK (CPU: {cpu}%)")
        except Exception:
            return await ctx.send("❌ psutil missing → `pip install psutil`")

        # channel check
        channel = self.bot.get_channel(STATUS_CHANNEL_ID)
        if not channel:
            return await ctx.send("❌ Status channel not found")

        await ctx.send(f"✅ Channel found: {channel.mention}")

        # permission check
        perms = channel.permissions_for(ctx.guild.me)
        if not perms.send_messages or not perms.embed_links:
            return await ctx.send("❌ Missing Send Messages / Embed Links permission")

        await ctx.send("✅ Permissions OK — forcing update...")
        await self.update_status_embed(channel)
        await ctx.send("✅ Status embed updated")

    # ─── TASK LOOP ────────────────────────────────────────
    @tasks.loop(seconds=UPDATE_INTERVAL)
    async def status_task(self):
        channel = self.bot.get_channel(STATUS_CHANNEL_ID)
        if not channel:
            print(f"[StatusPage] ❌ Cannot find channel {STATUS_CHANNEL_ID}")
            return

        await self.update_status_embed(channel)

    @status_task.before_loop
    async def before_status_task(self):
        await self.bot.wait_until_ready()
        print("[StatusPage] ✅ Status task started")

    # ─── CORE UPDATE LOGIC ─────────────────────────────────
    async def update_status_embed(self, channel: discord.TextChannel):
        print("[StatusPage] 🔄 Updating status embed")

        # ─── TIME (UTC → IST) ──────────────────────────────
        now_utc = discord.utils.utcnow()
        ist = datetime.timezone(datetime.timedelta(hours=5, minutes=30))
        now_ist = now_utc.astimezone(ist)
        ist_time_str = now_ist.strftime("%I:%M %p IST")

        # ─── NETWORK ───────────────────────────────────────
        latency = self.bot.latency or 0
        ping = 0 if math.isinf(latency) else round(latency * 1000)

        # ─── UPTIME ────────────────────────────────────────
        uptime_str = "Unknown"
        if hasattr(self.bot, "start_time"):
            delta = int((now_utc - self.bot.start_time).total_seconds())
            d, r = divmod(delta, 86400)
            h, r = divmod(r, 3600)
            m, _ = divmod(r, 60)
            uptime_str = f"{d}d {h}h {m}m"

        # ─── SYSTEM ────────────────────────────────────────
        cpu = psutil.cpu_percent(interval=None)
        ram = psutil.virtual_memory()

        # ─── BOT REACH ─────────────────────────────────────
        guilds = len(self.bot.guilds)
        users = sum(g.member_count or 0 for g in self.bot.guilds)

        # ─── STATUS LOGIC ──────────────────────────────────
        status_text = "🟢 Systems Operational"
        color = discord.Color.green()

        if self.bot.status == discord.Status.dnd:
            status_text = "🟠 Maintenance Mode"
            color = discord.Color.orange()
        elif cpu > 90 or ram.percent > 95:
            status_text = "🔴 Critical System Load"
            color = discord.Color.red()
        elif ping > 800:
            status_text = "🔴 Connection Unstable"
            color = discord.Color.red()
        elif ping > 400 or cpu > 75:
            status_text = "🟡 Performance Degraded"
            color = discord.Color.gold()

        # ─── EMBED ─────────────────────────────────────────
        embed = discord.Embed(
            title=f"📊 {self.bot.user.name} Status",
            description=(
                f"**Current Status:** {status_text}\n"
                f"Last Updated: <t:{int(now_utc.timestamp())}:R>\n"
                f"`{ist_time_str}`"
            ),
            color=color,
            timestamp=now_utc
        )

        if self.bot.user.avatar:
            embed.set_thumbnail(url=self.bot.user.avatar.url)

        embed.add_field(
            name="📶 Network",
            value=f"```yaml\nPing   : {ping} ms\nStatus : Connected```",
            inline=True
        )

        embed.add_field(
            name="⏱️ Uptime",
            value=f"```yaml\nTime : {uptime_str}\nSince: Boot```",
            inline=True
        )

        embed.add_field(
            name="💻 System Load",
            value=f"```yaml\nCPU : {cpu}%\nRAM : {ram.percent}%```",
            inline=False
        )

        embed.add_field(
            name="🛡️ Service Reach",
            value=f"```yaml\nServers : {guilds}\nUsers   : {users:,}```",
            inline=False
        )

        embed.set_footer(text=f"Refreshes every {UPDATE_INTERVAL}s | Server Time: IST")

        # ─── SEND / EDIT LOGIC ─────────────────────────────
        if self.message_id:
            try:
                msg = await channel.fetch_message(self.message_id)
                await msg.edit(embed=embed)
                return
            except Exception:
                self.message_id = None

        async for msg in channel.history(limit=5):
            if msg.author == self.bot.user and msg.embeds:
                if msg.embeds[0].footer and "Refreshes every" in msg.embeds[0].footer.text:
                    self.message_id = msg.id
                    await msg.edit(embed=embed)
                    return

        msg = await channel.send(embed=embed)
        self.message_id = msg.id


async def setup(bot: commands.Bot):
    await bot.add_cog(StatusPage(bot))
