# cogs/event.py
from __future__ import annotations
import discord
from discord.ext import commands
from discord import app_commands, Interaction, ui, ButtonStyle
from typing import Optional, Union, List, Dict, Any
import mysql.connector
import asyncio
import io
import csv
from datetime import datetime, timedelta


DB_CONFIG = dict(
    host="gameswaw7.bisecthosting.com",
    port=3306,
    user="u416861_UjU6KnDZ2f",
    password="j2kDVDBzqKmsQTndSZGljhdv",
    database="s416861_Cheesecake"
)
MIN_ACCOUNT_AGE_DAYS = 30
REQUIRE_VOTER_ID: Optional[int] = 1243576135481294859
MAX_BUTTONS = 20
LOG_CHANNEL_ID: Optional[int] = 1431691032516366337


TextChannelLike = Union[discord.TextChannel, discord.Thread, discord.DMChannel]

def get_conn() -> Any:
    return mysql.connector.connect(**DB_CONFIG)

def now_iso() -> str:
    return datetime.utcnow().isoformat()

def init_db() -> None:
    con = get_conn()
    cur = con.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS submissions (
        submission_id INT AUTO_INCREMENT PRIMARY KEY,
        guild_id BIGINT NOT NULL,
        user_id BIGINT NOT NULL,
        title VARCHAR(255),
        description TEXT,
        attachment_url TEXT,
        approved TINYINT DEFAULT 0,
        created_at DATETIME,
        UNIQUE KEY unique_submission (guild_id, user_id)
    )""")
    cur.execute("""
    CREATE TABLE IF NOT EXISTS polls (
        poll_id INT AUTO_INCREMENT PRIMARY KEY,
        guild_id BIGINT NOT NULL,
        channel_id BIGINT,
        message_id BIGINT,
        title VARCHAR(255),
        is_open TINYINT DEFAULT 1,
        created_at DATETIME
    )""")
    cur.execute("""
    CREATE TABLE IF NOT EXISTS poll_options (
        id INT AUTO_INCREMENT PRIMARY KEY,
        poll_id INT NOT NULL,
        option_index INT NOT NULL,
        submission_id INT NOT NULL
    )""")
    cur.execute("""
    CREATE TABLE IF NOT EXISTS votes (
        vote_id INT AUTO_INCREMENT PRIMARY KEY,
        poll_id INT NOT NULL,
        user_id BIGINT NOT NULL,
        option_index INT NOT NULL,
        created_at DATETIME,
        UNIQUE KEY unique_vote (poll_id, user_id)
    )""")
    cur.execute("""
    CREATE TABLE IF NOT EXISTS audit (
        id INT AUTO_INCREMENT PRIMARY KEY,
        poll_id INT,
        user_id BIGINT,
        action VARCHAR(255),
        detail TEXT,
        ts DATETIME
    )""")
    con.commit()
    cur.close()
    con.close()

init_db()

async def log_audit(poll_id: Optional[int], user_id: Optional[int], action: str, detail: str = "") -> None:
    con = get_conn()
    cur = con.cursor()
    cur.execute(
        "INSERT INTO audit (poll_id, user_id, action, detail, ts) VALUES (%s, %s, %s, %s, %s)",
        (poll_id, user_id, action, detail, now_iso())
    )
    con.commit()
    cur.close()
    con.close()

async def send_to_log_channel(guild: discord.Guild, text: str) -> None:
    if not LOG_CHANNEL_ID:
        return
    ch = guild.get_channel(LOG_CHANNEL_ID)
    if ch and isinstance(ch, (discord.TextChannel, discord.Thread, discord.DMChannel)):
        try:
            await ch.send(text)
        except Exception:
            pass

_poll_locks: Dict[int, asyncio.Lock] = {}
def poll_lock_for(poll_id: int) -> asyncio.Lock:
    if poll_id not in _poll_locks:
        _poll_locks[poll_id] = asyncio.Lock()
    return _poll_locks[poll_id]

async def handle_vote(interaction: Interaction, poll_id: int, option_index: int) -> None:
    guild = interaction.guild
    if guild is None:
        await interaction.response.send_message("This command can only be used in a guild.", ephemeral=True)
        return

    member: discord.Member
    if isinstance(interaction.user, discord.Member):
        member = interaction.user
    else:
        try:
            member = await guild.fetch_member(interaction.user.id)
        except Exception:
            await interaction.response.send_message("Failed to verify you as a guild member.", ephemeral=True)
            return

    if MIN_ACCOUNT_AGE_DAYS:
        acc_age = datetime.utcnow() - member.created_at.replace(tzinfo=None)
        if acc_age < timedelta(days=MIN_ACCOUNT_AGE_DAYS):
            await interaction.response.send_message(f"Your account is too new to vote (minimum {MIN_ACCOUNT_AGE_DAYS} days).", ephemeral=True)
            await log_audit(poll_id, member.id, "rejected_account_new", f"age_days={acc_age.days}")
            return

    roles = member.roles or []
    if REQUIRE_VOTER_ID and REQUIRE_VOTER_ID not in [r.id for r in roles]:
        await interaction.response.send_message(f"You must have the required role to vote.", ephemeral=True)
        await log_audit(poll_id, member.id, "rejected_missing_role", f"required_role_id={REQUIRE_VOTER_ID}")
        return

    lock = poll_lock_for(poll_id)
    async with lock:
        con = get_conn()
        cur = con.cursor()

        cur.execute("SELECT is_open FROM polls WHERE poll_id=%s AND guild_id=%s", (poll_id, guild.id))
        row = cur.fetchone()
        if not row:
            cur.close(); con.close()
            await interaction.response.send_message("Poll not found.", ephemeral=True)
            return
        if row[0] == 0:
            cur.close(); con.close()
            await interaction.response.send_message("This poll is closed.", ephemeral=True)
            return

        cur.execute("SELECT COUNT(*) FROM poll_options WHERE poll_id=%s", (poll_id,))
        total_opts_row = cur.fetchone()
        total_opts = total_opts_row[0] if total_opts_row else 0
        if option_index < 0 or option_index >= total_opts:
            cur.close(); con.close()
            await interaction.response.send_message("Invalid option.", ephemeral=True)
            return

        try:
            cur.execute(
                """
                INSERT INTO votes (poll_id, user_id, option_index, created_at)
                VALUES (%s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE option_index=VALUES(option_index), created_at=VALUES(created_at)
                """,
                (poll_id, member.id, option_index, now_iso())
            )
            con.commit()
        except Exception as e:
            con.rollback(); cur.close(); con.close()
            await interaction.response.send_message("Failed to record vote; try again later.", ephemeral=True)
            await log_audit(poll_id, member.id, "vote_error", str(e))
            return

        cur.execute("""
            SELECT s.title FROM poll_options p
            JOIN submissions s ON p.submission_id = s.submission_id
            WHERE p.poll_id=%s AND p.option_index=%s
        """, (poll_id, option_index))
        sub = cur.fetchone()
        sub_title = sub[0] if sub else f"Option {option_index+1}"

        cur.close(); con.close()
        await interaction.response.send_message(f"✅ Your vote for **{sub_title}** was recorded.", ephemeral=True)
        await log_audit(poll_id, member.id, "vote_cast", f"option={option_index}")
        await send_to_log_channel(guild, f"[VOTE] {member} voted in poll {poll_id} for '{sub_title}'")

class VoteView(ui.View):
    def __init__(self, poll_id: int, option_count: int):
        super().__init__(timeout=None)
        self.poll_id = poll_id
        for i in range(option_count):
            btn = ui.Button(label=str(i + 1), style=ButtonStyle.secondary, custom_id=f"vote:{poll_id}:{i}")

            async def button_callback(interaction: Interaction, idx: int = i) -> None:
                await handle_vote(interaction, poll_id, idx)

            btn.callback = button_callback
            self.add_item(btn)

class EventCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="submit", description="Submit an image for the event (one submission per user).")
    @app_commands.describe(title="Title of your artwork", description="Short description (optional)")
    async def submit(self, interaction: Interaction, title: str, description: str = "") -> None:
        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message("Submissions must be made in a server (not in DMs).", ephemeral=True)
            return

        if isinstance(interaction.user, discord.Member):
            member = interaction.user
        else:
            try:
                member = await guild.fetch_member(interaction.user.id)
            except Exception:
                await interaction.response.send_message("Failed to verify you as a guild member.", ephemeral=True)
                return

        attachments: List[discord.Attachment] = getattr(interaction, "attachments", None) or getattr(getattr(interaction, "message", None), "attachments", None) or []
        if not attachments:
            await interaction.response.send_message("Please attach an image file to your submission.", ephemeral=True)
            return
        att = attachments[0] 

        att = attachments[0]
  
        content_type = getattr(att, "content_type", None)
        if content_type and not content_type.startswith("image/"):
            await interaction.response.send_message("Only image attachments are allowed.", ephemeral=True)
            return


        if MIN_ACCOUNT_AGE_DAYS:
            acc_age = datetime.utcnow() - member.created_at.replace(tzinfo=None)
            if acc_age < timedelta(days=MIN_ACCOUNT_AGE_DAYS):
                await interaction.response.send_message(
                    f"Your account is too new to submit (minimum {MIN_ACCOUNT_AGE_DAYS} days).", ephemeral=True
                )
                await log_audit(None, member.id, "submit_rejected_account_new", f"age_days={acc_age.days}")
                return

        con = get_conn()
        cur = con.cursor()

        cur.execute("SELECT 1 FROM submissions WHERE guild_id=%s AND user_id=%s", (guild.id, member.id))
        if cur.fetchone():
            con.close()
            await interaction.response.send_message("You already submitted an entry for this guild.", ephemeral=True)
            return

        attachment_url = getattr(att, "url", None) or getattr(att, "proxy_url", None)
        cur.execute(
            "INSERT INTO submissions (guild_id, user_id, title, description, attachment_url, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (guild.id, member.id, title, description, attachment_url, now_iso()),
        )
        con.commit()
        con.close()

        await interaction.response.send_message("✅ Submission received — awaiting admin approval.", ephemeral=True)
        await log_audit(None, member.id, "submission_created", title)
        await send_to_log_channel(guild, f"New submission by {member} — {title} — {attachment_url}")

    @app_commands.command(name="list_submissions", description="List pending submissions (admins only).")
    async def list_submissions(self, interaction: Interaction) -> None:
        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message("Use this command in a server.", ephemeral=True)
            return

        if not (isinstance(interaction.user, discord.Member) and interaction.user.guild_permissions.manage_guild):
            await interaction.response.send_message("Admins only (Manage Server permission required).", ephemeral=True)
            return

        con = get_conn()
        cur = con.cursor()
        cur.execute(
            "SELECT submission_id, user_id, title, description, attachment_url, created_at FROM submissions WHERE guild_id=? AND approved=0 ORDER BY created_at ASC",
            (guild.id,),
        )
        rows = cur.fetchall()
        con.close()

        if not rows:
            await interaction.response.send_message("No pending submissions.", ephemeral=True)
            return

        lines = []
        for r in rows:
            sid, uid, title, desc, url, ts = r
            lines.append(f"[{sid}] {title} — by <@{uid}> — {url}")

        text = "\n".join(lines)
        if len(text) > 1900:
            text = text[:1900] + "\n...(truncated)"
        await interaction.response.send_message(f"Pending submissions:\n```\n{text}\n```", ephemeral=True)

    @app_commands.command(name="approve_submission", description="Approve a submission (admins only).")
    @app_commands.describe(submission_id="ID of the submission to approve")
    async def approve_submission(self, interaction: Interaction, submission_id: int) -> None:
        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message("Use this command in a server.", ephemeral=True)
            return

        if not (isinstance(interaction.user, discord.Member) and interaction.user.guild_permissions.manage_guild):
            await interaction.response.send_message("Admins only.", ephemeral=True)
            return

        con = get_conn()
        cur = con.cursor()
        cur.execute("UPDATE submissions SET approved=1 WHERE submission_id=? AND guild_id=?", (submission_id, guild.id))
        con.commit()
        ok = cur.rowcount > 0
        con.close()

        if ok:
            await interaction.response.send_message(f"✅ Submission #{submission_id} approved.", ephemeral=True)
            await log_audit(None, interaction.user.id, "submission_approved", f"id={submission_id}")
            await send_to_log_channel(guild, f"Submission #{submission_id} approved by {interaction.user}")
        else:
            await interaction.response.send_message("Submission not found.", ephemeral=True)

    @app_commands.command(name="reject_submission", description="Reject and remove a submission (admins only).")
    @app_commands.describe(submission_id="ID of the submission to reject", reason="Optional reason")
    async def reject_submission(self, interaction: Interaction, submission_id: int, reason: str = "") -> None:
        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message("Use this command in a server.", ephemeral=True)
            return

        if not (isinstance(interaction.user, discord.Member) and interaction.user.guild_permissions.manage_guild):
            await interaction.response.send_message("Admins only.", ephemeral=True)
            return

        con = get_conn()
        cur = con.cursor()
        cur.execute("SELECT user_id, attachment_url FROM submissions WHERE submission_id=? AND guild_id=?", (submission_id, guild.id))
        row = cur.fetchone()
        if not row:
            con.close()
            await interaction.response.send_message("Submission not found.", ephemeral=True)
            return

        cur.execute("DELETE FROM submissions WHERE submission_id=? AND guild_id=?", (submission_id, guild.id))
        con.commit()
        con.close()

        await interaction.response.send_message(f"Submission #{submission_id} rejected and removed.", ephemeral=True)
        await log_audit(None, interaction.user.id, "submission_rejected", f"id={submission_id} reason={reason}")
        await send_to_log_channel(guild, f"Submission #{submission_id} rejected by {interaction.user}. Reason: {reason}")

    @app_commands.command(name="start_voting", description="Create a voting poll from approved submissions (admins only).")
    @app_commands.describe(title="Title for the voting poll")
    async def start_voting(self, interaction: Interaction, title: str) -> None:
        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message("Use this command in a server.", ephemeral=True)
            return

        if not (isinstance(interaction.user, discord.Member) and interaction.user.guild_permissions.manage_guild):
            await interaction.response.send_message("Admins only.", ephemeral=True)
            return

        con = get_conn()
        cur = con.cursor()
        cur.execute("SELECT submission_id, user_id, title, attachment_url FROM submissions WHERE guild_id=? AND approved=1 ORDER BY created_at ASC", (guild.id,))
        rows = cur.fetchall()

        if not rows:
            con.close()
            await interaction.response.send_message("No approved submissions to start voting.", ephemeral=True)
            return

        if len(rows) > MAX_BUTTONS:
            con.close()
            await interaction.response.send_message(f"Too many approved submissions ({len(rows)}). Increase MAX_BUTTONS or reduce entries.", ephemeral=True)
            return

        cur.execute("INSERT INTO polls (guild_id, channel_id, title, created_at) VALUES (?, ?, ?, ?)", (guild.id, interaction.channel.id if interaction.channel else None, title, now_iso()))
        poll_id = cur.lastrowid

        for idx, r in enumerate(rows):
            submission_id = r[0]
            cur.execute("INSERT INTO poll_options (poll_id, option_index, submission_id) VALUES (?, ?, ?)", (poll_id, idx, submission_id))

        con.commit()

        description_lines = [f"**{i+1}.** {r[2]} — <@{r[1]}>" for i, r in enumerate(rows)]
        embed = discord.Embed(title=f"🎨 {title}", description="\n".join(description_lines))
        embed.set_footer(text="Click the number button to cast your single vote (one vote per user).")

        first_img = rows[0][3] if rows[0][3] else None
        if first_img:
            embed.set_image(url=first_img)

        if poll_id is None:
            await interaction.response.send_message("Failed to create poll.", ephemeral=True)
            return

        view = VoteView(int(poll_id), len(rows))


        try:
            msg = await interaction.channel.send(embed=embed, view=view)  
            cur.execute("UPDATE polls SET message_id=? WHERE poll_id=?", (msg.id, poll_id))
            con.commit()
        except Exception:

            await interaction.response.send_message("Failed to post poll message in channel.", ephemeral=True)
            con.close()
            return

        con.close()
        await interaction.response.send_message(f"✅ Poll #{poll_id} created with {len(rows)} options.", ephemeral=True)
        await log_audit(poll_id, interaction.user.id, "poll_created", f"title={title} options={len(rows)}")
        await send_to_log_channel(guild, f"Poll #{poll_id} started by {interaction.user} — {title}")

 
    @app_commands.command(name="reveal_results", description="Reveal and publish results for a poll (admins only).")
    @app_commands.describe(poll_id="ID of the poll to reveal")
    async def reveal_results(self, interaction: Interaction, poll_id: int) -> None:
        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message("Use this command in a server.", ephemeral=True)
            return

        if not (isinstance(interaction.user, discord.Member) and interaction.user.guild_permissions.manage_guild):
            await interaction.response.send_message("Admins only.", ephemeral=True)
            return

        con = get_conn()
        cur = con.cursor()

        cur.execute("UPDATE polls SET is_open=0 WHERE poll_id=? AND guild_id=?", (poll_id, guild.id))
        con.commit()

        cur.execute("SELECT option_index, COUNT(*) FROM votes WHERE poll_id=? GROUP BY option_index", (poll_id,))
        counts_map = {r[0]: r[1] for r in cur.fetchall()}

        cur.execute("SELECT option_index, submission_id FROM poll_options WHERE poll_id=? ORDER BY option_index ASC", (poll_id,))
        options = cur.fetchall()

        lines = []
        for idx, (opt_idx, submission_id) in enumerate(options):
            cur.execute("SELECT user_id, title, attachment_url FROM submissions WHERE submission_id=?", (submission_id,))
            s = cur.fetchone()
            if not s:
                continue
            author_id, title, attachment_url = s
            votes = counts_map.get(opt_idx, 0)
            lines.append(f"**{idx+1}. {title}** — <@{author_id}> — {votes} votes")

        total_votes = sum(counts_map.values())
        embed = discord.Embed(title=f"🏆 Results — Poll #{poll_id}", description="\n".join(lines))
        embed.set_footer(text=f"Total votes: {total_votes}")
        await interaction.channel.send(embed=embed) 
        con.close()

        await interaction.response.send_message("✅ Results published and poll closed.", ephemeral=True)
        await log_audit(poll_id, interaction.user.id, "poll_revealed", f"votes={total_votes}")
        await send_to_log_channel(guild, f"Poll #{poll_id} results revealed by {interaction.user}")

    @app_commands.command(name="results", description="Show current hidden results for a poll (admins only).")
    @app_commands.describe(poll_id="ID of the poll")
    async def results(self, interaction: Interaction, poll_id: int) -> None:
        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message("Use this command in a server.", ephemeral=True)
            return

        if not (isinstance(interaction.user, discord.Member) and interaction.user.guild_permissions.manage_guild):
            await interaction.response.send_message("Admins only.", ephemeral=True)
            return

        con = get_conn()
        cur = con.cursor()
        cur.execute("SELECT option_index, COUNT(*) FROM votes WHERE poll_id=? GROUP BY option_index", (poll_id,))
        counts_map = {r[0]: r[1] for r in cur.fetchall()}

        cur.execute("SELECT option_index, submission_id FROM poll_options WHERE poll_id=? ORDER BY option_index ASC", (poll_id,))
        options = cur.fetchall()

        lines = []
        for idx, (opt_idx, submission_id) in enumerate(options):
            cur.execute("SELECT title FROM submissions WHERE submission_id=?", (submission_id,))
            s = cur.fetchone()
            if not s:
                continue
            title = s[0]
            votes = counts_map.get(opt_idx, 0)
            lines.append(f"{idx+1}. {title} — {votes} votes")

        total_votes = sum(counts_map.values())
        text = "\n".join(lines) + f"\nTotal votes: {total_votes}"
        if len(text) > 1900:
            text = text[:1900] + "\n...(truncated)"

        con.close()
        await interaction.response.send_message(f"```\n{text}\n```", ephemeral=True)

    @app_commands.command(name="export_votes", description="Export votes CSV for a poll (admins only).")
    @app_commands.describe(poll_id="ID of the poll to export")
    async def export_votes(self, interaction: Interaction, poll_id: int) -> None:
        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message("Use this command in a server.", ephemeral=True)
            return

        if not (isinstance(interaction.user, discord.Member) and interaction.user.guild_permissions.manage_guild):
            await interaction.response.send_message("Admins only.", ephemeral=True)
            return

        con = get_conn()
        cur = con.cursor()
        cur.execute("SELECT poll_id, user_id, option_index, created_at FROM votes WHERE poll_id=?", (poll_id,))
        rows = cur.fetchall()
        con.close()

        if not rows:
            await interaction.response.send_message("No votes found for that poll.", ephemeral=True)
            return

        out = io.StringIO()
        writer = csv.writer(out)
        writer.writerow(["poll_id", "user_id", "option_index", "created_at"])
        writer.writerows(rows)
        out.seek(0)
        file_bytes = out.getvalue().encode("utf-8")
        discord_file = discord.File(io.BytesIO(file_bytes), filename=f"poll_{poll_id}_votes.csv")
        await interaction.response.send_message("Export:", file=discord_file, ephemeral=True)
        await log_audit(poll_id, interaction.user.id, "export_votes", f"count={len(rows)}")


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(EventCog(bot))
