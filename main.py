import discord
from discord.ext import commands, tasks
from dotenv import load_dotenv
import os
import json
from typing import Optional
import asyncio

from cogs.responsehandler import ResponseHandler, ALLOWED_CHANNELS

load_dotenv()

intents = discord.Intents.default()
intents.members = True
intents.guilds = True
intents.reactions = True
intents = discord.Intents.all()
bot = commands.Bot(command_prefix='$', intents=intents)

JR_MODS = "1334289756539846656"
MODS = "1243559774847766619"
ADMINS = "1243929060145631262"
OWNERS = "1240455108047671406"
BOT_MANAGER = "766005564190359552"

DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
if DISCORD_TOKEN is None:
    raise ValueError('Bot token not found. Please ensure the token variable is set correctly.')

# --- DO NOT REMOVE: Used for mental health support responses ---
MENTAL_HEALTH_TRIGGERS = ["kms", "ankill myselfxious", "suicidal", "self harm", "self harming"]

MENTAL_HEALTH_MESSAGE = (
    "**Mental Health Resources**\n"
    "If you're struggling, please know you're not alone. Here are some resources that might help:\n"
    "- [Mental Health America](<https://mhanational.org/get-involved/contact-us>)\n"
    "- [Crisis Text Line](<https://www.crisistextline.org/>) (Text HOME to 741741)\n"
    "- [National Suicide Prevention Lifeline](<https://988lifeline.org/>) (Call 988)\n"
    "- [Find a Therapist](<https://www.psychologytoday.com/us/therapists>)\n"
    "If you need someone to talk to, please reach out to a trusted friend, family member, or a professional. 💚"
)

@bot.event
async def on_ready():
    print(f"Yo, It's me, {bot.user}")

    for filename in os.listdir("./cogs"):
        if filename.endswith(".py"):
            try:
                await bot.load_extension(f"cogs.{filename[:-3]}")
                print(f"✅ Loaded cog: {filename}")
            except Exception as e:
                print(f"❌ Failed to load cog {filename}: {e}")

            

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    if any(word in message.content.lower() for word in MENTAL_HEALTH_TRIGGERS):
        await message.channel.send(f"{message.author.mention} {MENTAL_HEALTH_MESSAGE}")

    if message.channel.id in ALLOWED_CHANNELS or message.channel.id:
        await bot.process_commands(message)

    if message.channel.id in ALLOWED_CHANNELS:
        response = ResponseHandler.get_response(message.content)
        if response:
            await message.channel.send(response)

@bot.command(name='cc')
async def copy_message(ctx, *, message):
    """
    Copies and sends the provided message with a typing indicator
    Usage: $cc <message>
    """
    if ctx.channel.id:
        return
        
    await ctx.message.delete() 
    async with ctx.typing():
        await asyncio.sleep(1)
        await ctx.send(message)

@bot.event
async def on_member_join(member):
    welcome_channel_id = 1240449334642741308
    welcome_channel = member.guild.get_channel(welcome_channel_id)
    if welcome_channel is None:
        print("Welcome channel not found.")
        return

    member_count = member.guild.member_count

    embed = discord.Embed(
        title="Welcome to Cheesecake Art Café!",
        description=(
            f"Hey {member.mention}, welcome to **Cheesecake Art Café**! You are the {member_count} customer. Enjoy your stay!\n\n"
            "<a:aPink_Arrow:1244331554872758343> Make sure to read the rules of the server: <#1240449206297300992>\n"
            "<a:aPink_Arrow:1244331554872758343> After you've verified, check out <#1243567504542924852> & grab roles here: <#1244611036619735113>!\n"
            "<a:aPink_Arrow:1244331554872758343> If you're having trouble verifying, please contact our bot <@1310970252447711343> <#1414519063035514900>."
        ),
        color=discord.Color(0xFF69B4) 
    )
    avatar_url = member.display_avatar.url if hasattr(member, "display_avatar") else member.avatar.url if member.avatar else member.default_avatar.url
    embed.set_image(url="https://images-ext-1.discordapp.net/external/SjUljO-GGzBmtt42fK6p1k471y2-38DCo6j2KslSW3k/https/i.imgur.com/9N5YWS2.png?format=webp&quality=lossless&width=1406&height=375")
    embed.set_thumbnail(url=avatar_url)
    await welcome_channel.send(content=member.mention, embed=embed)

try:
    bot.run(DISCORD_TOKEN)
except discord.errors.LoginFailure as e:
    print(f"Failed to log in: {e}")
except Exception as e:
    print(f"An error occurred: {e}")