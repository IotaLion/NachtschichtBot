import discord
from discord.ext import commands, tasks
from datetime import datetime
import pytz
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Bot configuration
BOT_TOKEN = os.getenv('DISCORD_TOKEN')
CHANNEL_NAME = 'nachtschicht'
ROLE_NAME = 'Gast'

# ALLOWED_START_HOUR = 23  # start time: 23 Uhr
# ALLOWED_END_HOUR = 6  # end time: 6 Uhr

TIMEZONE = 'Europe/Berlin'


ALLOWED_START_HOUR = 19  # debug
ALLOWED_END_HOUR = 22  # debug

# Set up bot intents
intents = discord.Intents.default()
intents.guilds = True
intents.guild_messages = True
intents.message_content = True  # needed for commands.Bot with on_message (if used)

# Create bot instance
bot = commands.Bot(command_prefix='!', intents=intents)


def is_in_allowed_time_window():
    tz = pytz.timezone(TIMEZONE)
    now = datetime.now(tz)
    current_hour = now.hour

    if ALLOWED_START_HOUR < ALLOWED_END_HOUR:
        return ALLOWED_START_HOUR <= current_hour < ALLOWED_END_HOUR
    else:
        # Interval crosses midnight
        return current_hour >= ALLOWED_START_HOUR or current_hour < ALLOWED_END_HOUR


def get_time_message():
    tz = pytz.timezone(TIMEZONE)
    now = datetime.now(tz)
    current_hour = now.hour

    if current_hour < ALLOWED_END_HOUR:
        return f"🌙 Die Nachtschicht ist aktiv! Du kannst bis {ALLOWED_END_HOUR:02d}:00 Uhr schreiben."
    elif current_hour < ALLOWED_START_HOUR:
        return f"☀️ Die Nachtschicht ist geschlossen! Du kannst ab {ALLOWED_START_HOUR:02d}:00 Uhr wieder schreiben."
    else:
        return f"🌙 Die Nachtschicht ist aktiv! Du kannst bis {ALLOWED_END_HOUR:02d}:00 Uhr schreiben."


async def log_channel_status(channel):
    is_allowed = is_in_allowed_time_window()
    status = "unlocked" if is_allowed else "locked"
    print(f"📋 Channel '{channel.name}' status: {status} for 'Gast' role")


async def check_all_channels():
    for guild in bot.guilds:
        for channel in guild.text_channels:
            if channel.name == CHANNEL_NAME:
                await log_channel_status(channel)


@bot.event
async def on_ready():
    print(f'{bot.user} has logged in!')
    print(f'Monitoring channel: {CHANNEL_NAME}')
    print(f'Intercepting messages from role: {ROLE_NAME}')
    print(f'Allowed hours: {ALLOWED_START_HOUR:02d}:00 - {ALLOWED_END_HOUR:02d}:00')

    check_time_loop.start()
    await check_all_channels()


@bot.event
async def on_message(message):
    if message.author.bot:
        return

    if message.channel.name == CHANNEL_NAME:
        gast_role = discord.utils.get(message.guild.roles, name=ROLE_NAME)

        if gast_role and gast_role in message.author.roles:
            if not is_in_allowed_time_window():
                try:
                    # Delete user's message
                    await message.delete()

                    # Embed message
                    embed = discord.Embed(
                        description=f"⏰ Deine Nachricht konnte nicht gesendet werden.\n"
                                    f"Die Nachtschicht ist nur zwischen "
                                    f"**{ALLOWED_START_HOUR:02d}:00** und **{ALLOWED_END_HOUR:02d}:00** Uhr aktiv.",
                        color=0xff6b6b
                    )

                    # Send embed mentioning the user
                    warning_msg = await message.channel.send(
                        content=f"{message.author.mention}",
                        embed=embed
                    )

                    # Add reaction so user can delete it
                    await warning_msg.add_reaction("🆗")

                except discord.errors.NotFound:
                    pass

                return

    await bot.process_commands(message)


@bot.event
async def on_reaction_add(reaction, user):
    if user.bot:
        return

    if reaction.emoji == "🆗" and reaction.message.mentions and user in reaction.message.mentions:
        try:
            await reaction.message.delete()
        except discord.errors.NotFound:
            pass


@tasks.loop(minutes=5)
async def check_time_loop():
    await check_all_channels()


@bot.command(name='nachtschicht_status')
async def check_status(ctx):
    status_msg = get_time_message()
    is_allowed = is_in_allowed_time_window()

    embed = discord.Embed(
        title="Nachtschicht Status",
        description=status_msg,
        color=0x2ecc71 if is_allowed else 0xe74c3c
    )

    tz = pytz.timezone(TIMEZONE)
    now = datetime.now(tz)
    embed.add_field(name="Aktuelle Zeit", value=now.strftime("%H:%M:%S"), inline=True)
    embed.add_field(name="Erlaubte Zeiten", value=f"{ALLOWED_START_HOUR:02d}:00 - {ALLOWED_END_HOUR:02d}:00", inline=True)

    await ctx.send(embed=embed)


@bot.command(name='nachtschicht_force_check')
@commands.has_permissions(administrator=True)
async def force_check(ctx):
    await check_all_channels()
    await ctx.send("✅ Channel status checked!")


@force_check.error
async def force_check_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ Du benötigst Administrator-Rechte für diesen Befehl!")


if __name__ == "__main__":
    bot.run(BOT_TOKEN)