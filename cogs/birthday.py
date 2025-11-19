import discord
from discord.ext import commands
import pymysql
from datetime import datetime
from config import DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME, BIRTHDAY_CHANNEL_ID

def get_db():
    return pymysql.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        autocommit=True
    )

def ensure_birthday_table():
    db = get_db()
    cursor = db.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS birthdays (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id BIGINT,
            birthday VARCHAR(5)
        )
    """)
    db.commit()
    cursor.close()
    db.close()

ensure_birthday_table()

class Birthday(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="addbday")
    @commands.has_any_role(1334950965408956527, 1243560048077049858)
    async def add_birthday(self, ctx, date: str):
        """Add your birthday (DD/MM)"""
        try:
            datetime.strptime(date, "%d/%m")
        except ValueError:
            embed = discord.Embed(
                title="Error",
                description="Invalid date format. Use DD/MM.",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return

        db = get_db()
        cursor = db.cursor()
        cursor.execute(
            "REPLACE INTO birthdays (user_id, birthday) VALUES (%s, %s)", 
            (ctx.author.id, date)
        )
        db.commit()
        cursor.close()
        db.close()

        embed = discord.Embed(
            title="Birthday Set",
            description=f"Birthday set for <@{ctx.author.id}>: `{date}`",
            color=discord.Color.green()
        )
        await ctx.send(embed=embed)

    @commands.command(name="removebday")
    @commands.has_any_role(1243929060145631262, 1240455108047671406)
    async def remove_birthday(self, ctx, user_id: int):
        """Remove a user's birthday by their user ID"""
        db = get_db()
        cursor = db.cursor()
        cursor.execute("DELETE FROM birthdays WHERE user_id = %s", (user_id,))
        db.commit()
        deleted = cursor.rowcount
        cursor.close()
        db.close()

        if deleted > 0:
            embed = discord.Embed(
                title="Birthday Removed",
                description=f"Removed birthday for <@{user_id}> (`{user_id}`).",
                color=discord.Color.orange()
            )
        else:
            embed = discord.Embed(
                title="Not Found",
                description=f"No birthday found for <@{user_id}> (`{user_id}`).",
                color=discord.Color.red()
            )
        await ctx.send(embed=embed)

    @commands.command(name="bdaylist")
    async def birthday_list(self, ctx):
        """List all birthdays"""
        db = get_db()
        cursor = db.cursor()
        cursor.execute("SELECT user_id, birthday FROM birthdays")
        rows = cursor.fetchall() or []
        cursor.close()
        db.close()

        if not rows:
            embed = discord.Embed(
                title="Birthday List",
                description="No birthdays found.",
                color=discord.Color.yellow()
            )
            await ctx.send(embed=embed)
            return

        msg = "\n".join([f"<@{row[0]}>: {row[1]}" for row in rows])
        embed = discord.Embed(
            title="🎂 Birthday List 🎂",
            description=msg,
            color=discord.Color.blue()
        )
        await ctx.send(embed=embed)

    async def birthday_check(self):
        today = datetime.utcnow().strftime("%d/%m")
        db = get_db()
        cursor = db.cursor()
        cursor.execute("SELECT user_id FROM birthdays WHERE birthday = %s", (today,))
        rows = cursor.fetchall() or []
        cursor.close()
        db.close()

        channel = self.bot.get_channel(BIRTHDAY_CHANNEL_ID)
        for row in rows:
            user_id = row[0]
            if channel:
                await channel.send(f"🎂 Happy Birthday <@{user_id}>! 🎉")

async def setup(bot):
    await bot.add_cog(Birthday(bot))
