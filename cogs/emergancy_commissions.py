import discord
from discord.ext import commands, tasks
from discord.ui import View, Button
import asyncio
import mysql.connector
from datetime import datetime
import logging
from typing import Optional, Union, Tuple

REVIEW_CHANNEL = 1431344160840880159
PUBLIC_CHANNEL = 1412722866134323270
LOG_CHANNEL = 1430575592503378142

DB_CONFIG = {
    "host": "gameswaw7.bisecthosting.com",
    "port": 3306,
    "user": "u416861_UjU6KnDZ2f",
    "password": "j2kDVDBzqKmsQTndSZGljhdv",
    "database": "s416861_Cheesecake"
}

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


from discord import TextChannel, Thread, DMChannel, GroupChannel


def is_textlike_channel(ch: Optional[discord.abc.Messageable]) -> bool:
    """
    Return True if the channel likely supports send() and fetch_message().
    This helps static type checkers like Pylance and prevents AttributeErrors.
    """
    return isinstance(ch, (TextChannel, Thread, DMChannel, GroupChannel))


class EmergencyCommissions(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db_config = DB_CONFIG
        self.setup_database()

    async def cog_load(self):
        logger.info("EmergencyCommissions cog loaded")
        self.cleanup_old_applications.start()

    async def cog_unload(self):
        logger.info("EmergencyCommissions cog unloaded")
        self.cleanup_old_applications.cancel()

    def get_db_connection(self):
        """Return a fresh MySQL connection using DB_CONFIG."""
        return mysql.connector.connect(**self.db_config)

    def setup_database(self):
        """Ensure table exists (idempotent)."""
        try:
            conn = self.get_db_connection()
            cursor = conn.cursor()
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS emergency_commissions (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id BIGINT NOT NULL,
                    username VARCHAR(255) NOT NULL,
                    application_data TEXT NOT NULL,
                    status ENUM('pending', 'accepted', 'rejected') DEFAULT 'pending',
                    mod_id BIGINT,
                    mod_username VARCHAR(255),
                    rejection_reason TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    message_id BIGINT,
                    application_channel_id BIGINT,
                    UNIQUE KEY unique_user_recent (user_id, created_at)
                )
                """
            )
            conn.commit()
            cursor.close()
            conn.close()
            logger.info("✅ emergency_commissions table ready")
        except Exception:
            logger.exception("Database setup error")
            
    @tasks.loop(hours=24)
    async def cleanup_old_applications(self):
        """Delete applications older than 2 months and notify users."""
        try:
            conn = self.get_db_connection()
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT message_id, application_channel_id, user_id
                FROM emergency_commissions
                WHERE created_at < DATE_SUB(NOW(), INTERVAL 2 MONTH)
                """
            )
            rows = cursor.fetchall()
            deleted = 0
            for message_id, channel_id, user_id in rows:
                try:
                    ch = self.bot.get_channel(channel_id)
                    if is_textlike_channel(ch):
                       
                        try:
                            m = await ch.fetch_message(message_id) 
                            try:
                                await m.delete()
                                deleted += 1
                            except Exception:
                                pass
                        except Exception:
                            pass
                    user = self.bot.get_user(user_id)
                    if user:
                        try:
                            await user.send(
                                "📅 Your emergency commission application older than 2 months was removed. You may apply again."
                            )
                        except Exception:
          
                            pass
                except Exception:
                    logger.exception("Error cleaning application %s", message_id)

            cursor.execute(
                """
                DELETE FROM emergency_commissions
                WHERE created_at < DATE_SUB(NOW(), INTERVAL 2 MONTH)
                """
            )
            conn.commit()
            logger.info("Cleanup done; processed %d rows (deleted messages: %d)", len(rows), deleted)
            cursor.close()
            conn.close()
        except Exception:
            logger.exception("Cleanup task error")


    def user_has_recent_application(self, user_id: int) -> bool:
        """Return True if user has an application in the last 2 months."""
        try:
            conn = self.get_db_connection()
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT 1 FROM emergency_commissions
                WHERE user_id = %s AND created_at >= DATE_SUB(NOW(), INTERVAL 2 MONTH)
                LIMIT 1
                """,
                (user_id,),
            )
            exists = cursor.fetchone() is not None
            cursor.close()
            conn.close()
            return exists
        except Exception:
            logger.exception("Error checking user recent application")
            return False

    @commands.command(name="apply")
    async def apply(self, ctx: commands.Context):
        """
        Start emergency application via DM.
        If run in a guild channel, instruct user to DM the bot.
        """
        if ctx.guild is not None:
            try:
                await ctx.reply("Please run `!apply` in my DMs. I will guide you through the form there.")
            except Exception:
                pass
            return

        user = ctx.author

        if self.user_has_recent_application(user.id):
            await ctx.send("❌ You submitted an application in the last 2 months. You can apply again after the cooldown.")
            return

        questions = [
            {"prompt": "🚨 **Step 1:** Describe your emergency (short summary).", "timeout": 300},
            {"prompt": "📌 **Step 2:** How many open slots? (1–10)", "timeout": 120},
            {"prompt": "📝 **Step 3:** Write your emergency commission post (details, prices, expectations).", "timeout": 600},
            {"prompt": "🔗 **Step 4:** Send portfolio links OR attach images (you may paste links or upload files).", "timeout": 300},
        ]

        answers = []
        await ctx.send("✅ Starting application — you have limited time for each step. Reply to each prompt below.")

        def check_dm(m: discord.Message) -> bool:
            return m.author.id == user.id and isinstance(m.channel, discord.DMChannel)

        try:
            for q in questions:
                await ctx.send(q["prompt"])
                msg: discord.Message = await self.bot.wait_for("message", check=check_dm, timeout=q["timeout"])
                answers.append(msg)
        except asyncio.TimeoutError:
            await ctx.send("⏳ Application timed out. Start again with `!apply` when you're ready.")
            return
        except Exception:
            logger.exception("Error during DM application")
            await ctx.send("❌ Unexpected error. Try again later.")
            return


        emergency_text = answers[0].content.strip() if answers and answers[0].content else ""

        try:
            slots = int(answers[1].content.strip())
            if slots < 1 or slots > 10:
                await ctx.send("❌ Open slots must be between 1 and 10. Application cancelled.")
                return
        except Exception:
            await ctx.send("❌ Invalid number for open slots. Application cancelled.")
            return

        post_text = answers[2].content.strip() if answers and answers[2].content else ""
        portfolio_msg = answers[3]
        portfolio_text = portfolio_msg.content.strip() if portfolio_msg.content else ""
        attachments = [a.url for a in portfolio_msg.attachments] if portfolio_msg.attachments else []


        application_data = (
            f"**Emergency:** {emergency_text}\n\n"
            f"**Open Slots:** {slots}\n\n"
            f"**Commission Post:**\n{post_text}\n\n"
            f"**Portfolios / Images:**\n"
        )
        if portfolio_text:
            application_data += portfolio_text + "\n"
        if attachments:
            application_data += "\n".join(attachments)


        desc = application_data if len(application_data) < 4000 else application_data[:3990] + "..."
        embed = discord.Embed(title="🚨 Emergency Commission Application", description=desc, color=0xffa500, timestamp=datetime.utcnow())
        embed.add_field(name="Artist", value=f"{user} ({user.id})", inline=True)
        embed.add_field(name="Status", value="⏳ Pending Review", inline=True)
        embed.set_footer(text="Use the buttons below to approve or reject; reject asks staff for a reason.")

        # Post to review channel with buttons
        review_channel = self.bot.get_channel(REVIEW_CHANNEL)
        log_channel = self.bot.get_channel(LOG_CHANNEL)
        if not is_textlike_channel(review_channel):
            await ctx.send("❌ Review channel not found or is not a valid text channel. Contact an admin.")
            return

        view = ReviewButtons(self)
        try:
            review_msg = await review_channel.send(embed=embed, view=view)  
        except Exception:
            logger.exception("Error sending to review channel")
            await ctx.send("❌ Failed to submit application to review channel.")
            return


        try:
            conn = self.get_db_connection()
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO emergency_commissions
                (user_id, username, application_data, message_id, application_channel_id)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (user.id, str(user), application_data, review_msg.id, review_channel.id),
            )
            conn.commit()
            cursor.close()
            conn.close()
        except Exception:
            logger.exception("Error inserting application into DB")


        try:
            await ctx.send("✅ Your application has been submitted for staff review. You will be notified when a decision is made.")
        except Exception:
            pass

        if is_textlike_channel(log_channel):
            try:
                await log_channel.send(f"📨 New application submitted by {user.mention} (`{user.id}`) — message {review_msg.id}")  # type: ignore[arg-type]
            except Exception:
                pass

    # ---------- Approve/Deny actions triggered by buttons ----------
    async def accept_application(self, message_id: int, moderator: discord.Member) -> bool:
        """Mark application accepted, notify user, post to public channel, log, update DB."""
        try:
            conn = self.get_db_connection()
            cursor = conn.cursor()
            cursor.execute(
                "SELECT user_id, username, application_data FROM emergency_commissions WHERE message_id=%s",
                (message_id,),
            )
            row = cursor.fetchone()
            if not row:
                cursor.close()
                conn.close()
                return False
            user_id, username, application_data = row


            cursor.execute(
                """
                UPDATE emergency_commissions
                SET status='accepted', mod_id=%s, mod_username=%s
                WHERE message_id=%s
                """,
                (moderator.id, str(moderator), message_id),
            )
            conn.commit()


            public = self.bot.get_channel(PUBLIC_CHANNEL)
            if is_textlike_channel(public):
                embed = discord.Embed(
                    title="🎨 Emergency Commission Artist - ACCEPTED",
                    description=application_data if len(application_data) < 4000 else application_data[:3990] + "...",
                    color=0x00ff00,
                    timestamp=datetime.utcnow(),
                )
                embed.add_field(name="Artist", value=f"<@{user_id}>", inline=True)
                embed.add_field(name="Approved by", value=f"{moderator} ({moderator.id})", inline=True)
                try:
                    await public.send(embed=embed) 
                except Exception:
                    logger.exception("Failed to post to public channel")


            user = self.bot.get_user(user_id)
            if user:
                try:
                    await user.send("🎉 Congratulations! Your emergency commission application has been **APPROVED**.")
                except Exception:
                    pass


            log_ch = self.bot.get_channel(LOG_CHANNEL)
            if is_textlike_channel(log_ch):
                try:
                    await log_ch.send(f"✔️ APPROVED application for `{username}` (`{user_id}`) by {moderator.mention}")  # type: ignore[arg-type]
                except Exception:
                    pass

            cursor.close()
            conn.close()
            return True
        except Exception:
            logger.exception("Error accepting application")
            return False

    async def reject_application_with_reason(self, message_id: int, moderator: discord.Member, reason: str) -> bool:
        """Mark application rejected, notify user with reason, log, update DB."""
        try:
            conn = self.get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT user_id, username FROM emergency_commissions WHERE message_id=%s", (message_id,))
            row = cursor.fetchone()
            if not row:
                cursor.close()
                conn.close()
                return False
            user_id, username = row


            cursor.execute(
                """
                UPDATE emergency_commissions
                SET status='rejected', mod_id=%s, mod_username=%s, rejection_reason=%s
                WHERE message_id=%s
                """,
                (moderator.id, str(moderator), reason, message_id),
            )
            conn.commit()

            user = self.bot.get_user(user_id)
            if user:
                try:
                    await user.send(f"❌ Your emergency commission application was **DECLINED**.\n**Reason:** {reason}")
                except Exception:
                    pass

            # Log
            log_ch = self.bot.get_channel(LOG_CHANNEL)
            if is_textlike_channel(log_ch):
                try:
                    await log_ch.send(
                        f"❌ DENIED application for `{username}` (`{user_id}`) by {moderator.mention}\nReason: {reason}"
                    )  
                except Exception:
                    pass

            cursor.close()
            conn.close()
            return True
        except Exception:
            logger.exception("Error rejecting application")
            return False


class ReviewButtons(View):
    """View attached to the review message with Approve / Reject behavior."""

    def __init__(self, cog: EmergencyCommissions):
        super().__init__(timeout=None)
        self.cog = cog

    @discord.ui.button(label="Accept", style=discord.ButtonStyle.success, custom_id="ec_accept")
    async def accept(self, interaction: discord.Interaction, button: Button):
        # permission check
        if not isinstance(interaction.user, discord.Member) or not interaction.user.guild_permissions.manage_messages:
            await interaction.response.send_message("❌ You don't have permission to perform this action.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        message_id = getattr(interaction.message, "id", None)
        if message_id is None:
            await interaction.followup.send("❌ Could not determine the message ID.", ephemeral=True)
            return

        success = await self.cog.accept_application(message_id, interaction.user)
        if success:

            try:
                if interaction.message and interaction.message.embeds:
                    new_embed = interaction.message.embeds[0]

                    new_embed.color = 0x00ff00

                    found = False
                    for i, f in enumerate(new_embed.fields):
                        if f.name and f.name.lower() == "status":
                            new_embed.set_field_at(i, name="Status", value="✅ Accepted", inline=f.inline)
                            found = True
                            break
                    if not found:
                        new_embed.add_field(name="Status", value="✅ Accepted", inline=True)

                    try:
                        await interaction.message.edit(embed=new_embed, view=None)
                    except Exception:
                        pass
            except Exception:
                logger.exception("Error updating review message after accept")
            await interaction.followup.send("✅ Application accepted and processed.", ephemeral=True)
        else:
            await interaction.followup.send("❌ Failed to accept application. Check logs.", ephemeral=True)

    @discord.ui.button(label="Reject", style=discord.ButtonStyle.danger, custom_id="ec_reject")
    async def reject(self, interaction: discord.Interaction, button: Button):

        if not isinstance(interaction.user, discord.Member) or not interaction.user.guild_permissions.manage_messages:
            await interaction.response.send_message("❌ You don't have permission to perform this action.", ephemeral=True)
            return


        await interaction.response.send_message(
            "✍️ Please type the rejection reason in this channel within 5 minutes. The next message you send here will be used as the reason.",
            ephemeral=True,
        )

        def check(m: discord.Message) -> bool:
            return m.author.id == interaction.user.id and m.channel.id == getattr(interaction.channel, "id", None)

        try:
            reason_msg = await self.cog.bot.wait_for("message", check=check, timeout=300)  # 5 minutes
            reason = reason_msg.content.strip() or "No reason provided"
            message_id = getattr(interaction.message, "id", None)
            if message_id is None:
                await interaction.channel.send("❌ Could not determine the message ID to reject.", ephemeral=True)
                return
            success = await self.cog.reject_application_with_reason(message_id, interaction.user, reason)
            if success:

                try:
                    if interaction.message and interaction.message.embeds:
                        new_embed = interaction.message.embeds[0]
                        new_embed.color = 0xff0000
                        found = False
                        for i, f in enumerate(new_embed.fields):
                            if f.name and f.name.lower() == "status":
                                new_embed.set_field_at(i, name="Status", value="❌ Rejected", inline=f.inline)
                                found = True
                                break
                        if not found:
                            new_embed.add_field(name="Status", value="❌ Rejected", inline=True)
                        try:
                            await interaction.message.edit(embed=new_embed, view=None)
                        except Exception:
                            pass
                except Exception:
                    logger.exception("Error updating review message after reject")

                try:
                    await interaction.channel.send(f"✅ Application rejected. Reason recorded by {interaction.user.mention}.")
                except Exception:
                    pass
            else:
                try:
                    await interaction.channel.send("❌ Failed to reject application. Check logs.")
                except Exception:
                    pass
        except asyncio.TimeoutError:
            await interaction.followup.send("⌛ You did not provide a reason in time. The reject action was cancelled.", ephemeral=True)
        except Exception:
            logger.exception("Error while waiting for rejection reason")
            await interaction.followup.send("❌ An error occurred while processing rejection.", ephemeral=True)



async def setup(bot: commands.Bot):
    await bot.add_cog(EmergencyCommissions(bot))
