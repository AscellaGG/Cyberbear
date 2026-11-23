import asyncio
import os
import discord
import json
import logging

from dotenv import load_dotenv
from datetime import datetime, time
from zoneinfo import ZoneInfo
from discord.ext import tasks
from pathlib import Path
from config.logging_config import configure_logging

from briefing import make_briefing, shorten_description
from cves import get_relevant_cves
from ai_ranking import get_ai_ranked_articles
from feeds import check_all_feeds_once

load_dotenv()
configure_logging()

logger = logging.getLogger(__name__)

token = os.getenv("DISCORD_TOKEN")
if not token:
    raise RuntimeError("DISCORD_TOKEN saknas. Lägg till den i .env-filen.")

BOT_ENV = os.getenv("BOT_ENV", "production").lower()
IS_TEST = BOT_ENV == "test"

intents = discord.Intents.default()
client = discord.Client(intents=intents)
tree = discord.app_commands.CommandTree(client)

MORNING_TIME = time(
    hour=8,
    minute=0,
    tzinfo=ZoneInfo("Europe/Stockholm"),
)

EVENING_TIME = time(
    hour=20,
    minute=0,
    tzinfo=ZoneInfo("Europe/Stockholm"),
)

async def create_briefing_message(period):
    articles, ai_ranked = await asyncio.to_thread(get_ai_ranked_articles)
    cves = await get_relevant_cves()

    return make_briefing(articles, cves[:3], period, ai_ranked)

async def send_scheduled_briefing(period):
    now = datetime.now(ZoneInfo("Europe/Stockholm"))

    if now.weekday() >= 5:
        logger.info("Hoppar över %s-briefing: helg.", period)
        return    
    
    await client.wait_until_ready()

    channel_ids = [
        int(value.strip())
        for value in os.getenv("BRIEFING_CHANNEL_IDS", "").split(",")
        if value.strip()
    ]

    if not channel_ids:
        raise RuntimeError("No briefing channels are configured.")

    message = await create_briefing_message(period)

    for channel_id in channel_ids:
        channel = client.get_channel(channel_id)

        if channel is None:
            channel = await client.fetch_channel(channel_id)

        await channel.send(message, suppress_embeds=True)

    return len(channel_ids)

async def run_scheduled_briefing(period):
    try:
        logger.info("Starting %s scheduled briefing.", period)
        sent_channel_count = await send_scheduled_briefing(period)
    except Exception:
        logger.exception("Scheduled %s briefing failed.", period)
    else:
        logger.info(
            "Scheduled %s briefing sent to %d channel(s).",
            period,
            sent_channel_count,
        )

@tasks.loop(time=MORNING_TIME)
async def scheduled_morning_briefing():
    await run_scheduled_briefing("morning")

@tasks.loop(time=EVENING_TIME)
async def scheduled_evening_briefing():
    await run_scheduled_briefing("evening")

async def send_feed_message(message):
    channel_ids = [
        int(value.strip())
        for value in os.getenv("BRIEFING_CHANNEL_IDS", "").split(",")
        if value.strip()
    ]

    if not channel_ids:
        raise RuntimeError("No breifinf channels are configured.")

    for channel_id in channel_ids:
        channel = client.get_channel(channel_id)

        if channel is None:
            channel = await client.fetch_channel(channel_id)

        await channel.send(message, suppress_embeds=True)

@tasks.loop(minutes=10)
async def scheduled_feed_check():
    try:
        posted_count = await check_all_feeds_once(send_feed_message)
        logger.info("Feed check completed; posted %d article(s).", posted_count)
    except Exception:
        logger.exception("Scheduled feed check failed.")

@scheduled_feed_check.before_loop
async def before_check_feeds():
    await client.wait_until_ready()

@client.event
async def on_ready():
    try:
        synced = await tree.sync()
    except Exception:
        logger.exception("Failed to sync application commands.")
    else:
        logger.info("Synced %d global application command(s).", len(synced))

    logger.info("Logged in as %s.", client.user)

    if IS_TEST:
        logger.info("Test environment: automatic scheduled jobs are disabled.")
        return

    if not scheduled_morning_briefing.is_running():
        scheduled_morning_briefing.start()

    if not scheduled_evening_briefing.is_running():
        scheduled_evening_briefing.start()

    if not scheduled_feed_check.is_running():
        scheduled_feed_check.start()

@tree.command(name="brief", description="Få en briefing på nyheter inom cybersäkerhet från Cyberbear.")
async def brief(interaction: discord.Interaction):
    await interaction.response.defer(thinking=True)

    message = await create_briefing_message("other")

    await interaction.followup.send(message, suppress_embeds=True)

@tree.command(name="check_feeds", description="Kontrollera nyhets-flöden nu.")
async def check_feeds_command(interaction: discord.Interaction):
    await interaction.response.defer(thinking=True, ephemeral=True)

    new_articles = await check_all_feeds_once(send_feed_message)

    if new_articles:
        await interaction.followup.send(
            f"Feed-kontrollen är klar. Skickade {new_articles} ny(a) artikel/artiklar.",
            ephemeral=True,
        )
    else:
        await interaction.followup.send(
            "Det finns inga nya artiklar. <:sadge:1568301148895584363>",
            ephemeral=True,
        )

@tree.command(name="check_cve", description="Kolla nya CVEr.")
async def check_cve(interaction: discord.Interaction):
    await interaction.response.defer(thinking=True, ephemeral=True)

    cves = await get_relevant_cves()

    lines = [
        "## 🛡️  Nya sårbarheter:"
    ]

    for cve in cves[:3]:
        lines.append(f"### {cve['id']}")
        lines.append(f"**Allvarlighetsgrad:** {cve['severity']}, {cve['score']}")

        description = shorten_description(cve['description'])
        lines.append(description)

        lines.append(f"[Läs mer](https://nvd.nist.gov/vuln/detail/{cve['id']})")
        lines.append("")

    await interaction.followup.send(
        "\n".join(lines),
        suppress_embeds=True,
        ephemeral=True,
    )

# --------------------
# FOR TESTING PURPOSES

if IS_TEST:
    @tree.command(name="preview_svt", description="Visa SVT-artiklar som filtret väljer.")
    async def preview_svt(interaction: discord.Interaction):
        await interaction.response.defer(thinking=True, ephemeral=True)

        entries = await asyncio.to_thread(get_svt_articles)
        matches = await asyncio.to_thread(filter_svt_articles, entries)

        if not matches:
            await interaction.followup.send(
                f"Hämtade {len(entries)} artiklar från SVT, men filtret hittade inga träffar.",
                ephemeral=True,
            )
            return

        lines = ["**SVT-träffar i det aktuella flödet:**"]

        for article in matches[:10]:
            title = article.get("title", "Artikel utan rubrik")
            link = article.get("link", "")
            lines.append(f"• [{title}]({link})")

        await interaction.followup.send("\n".join(lines), ephemeral=True)

    @tree.command(name="test", description="test")
    async def test(interaction: discord.Interaction):
        await interaction.response.send_message("Hello!")

# --------------------


@tree.error
async def on_app_command_error(
    interaction: discord.Interaction,
    error: discord.app_commands.AppCommandError,
):
    command_name = interaction.command.name if interaction.command else "unknown"

    original_error = (
        error.original
        if isinstance(error, discord.app_commands.CommandInvokeError)
        else error
    )

    logger.error(
        "Command /%s failed: %s",
        command_name,
        original_error,
        exc_info=(
            type(original_error),
            original_error,
            original_error.__traceback__,
        ),
    )

    message = "Something went wrong while Cyberbear was running that command."

    if interaction.response.is_done():
        await interaction.followup.send(message, ephemeral=True)
    else:
        await interaction.response.send_message(message, ephemeral=True)


client.run(token)
