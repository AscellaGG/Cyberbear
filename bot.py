import asyncio
import os
import discord
import json
import logging

from dotenv import load_dotenv
from datetime import time
from zoneinfo import ZoneInfo
from discord.ext import tasks
from pathlib import Path
from config.logging_config import configure_logging

from briefing import make_briefing, shorten_description
from cves import get_relevant_cves
from svt_monitor import get_relevant_svt_articles, format_svt_article, load_seen_svt_ids, save_seen_svt_ids
from ai_ranking import get_ai_ranked_articles

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
    await client.wait_until_ready()

    message = await create_briefing_message(period)

    channel_ids = [
        int(value.strip())
        for value in os.getenv("BRIEFING_CHANNEL_IDS", "").split(",")
        if value.strip()
    ]

    for channel_id in channel_ids:
        channel = client.get_channel(channel_id)

        if channel is None:
            channel = await client.fetch_channel(channel_id)
        
        await channel.send(message, suppress_embeds=True)

@tasks.loop(time=MORNING_TIME)
async def scheduled_morning_briefing():
    logger.info("Sending morning brief...")
    await send_scheduled_briefing("morning")

@tasks.loop(time=EVENING_TIME)
async def scheduled_evening_briefing():
    logger.info("Sending evening brief...")
    await send_scheduled_briefing("evening")

async def check_svt_feed_once():
    try:
        channel_ids = [
            int(value.strip())
            for value in os.getenv("BRIEFING_CHANNEL_IDS", "").split(",")
            if value.strip()
        ]    

        if not channel_ids:
            return

        articles = await get_relevant_svt_articles()

        seen_ids = load_seen_svt_ids()

        if articles:
            for entry in articles:
                article_id = entry.get("id") or entry.get("link")

                message = format_svt_article(entry)

                for channel_id in channel_ids:
                    channel = client.get_channel(channel_id)

                    if channel is None:
                        channel = await client.fetch_channel(channel_id)
                        
                    await channel.send(message, suppress_embeds=True)
                
                seen_ids.add(article_id)
                save_seen_svt_ids(seen_ids)
                
                return True
        elif articles == []:
            return False

    except Exception as error :
        logger.exception(error)

@tasks.loop(minutes=10)
async def check_svt_feed():
    await check_svt_feed_once()

@check_svt_feed.before_loop
async def before_check_svt_feed():
    await client.wait_until_ready()

@client.event
async def on_ready():
    synced = await tree.sync()
    print(f"Synkade {len(synced)} globala kommandon.")
    print(f"Inloggad som {client.user}.")

    if not scheduled_morning_briefing.is_running():
        scheduled_morning_briefing.start()

    if not scheduled_evening_briefing.is_running():
        scheduled_evening_briefing.start()

    if not check_svt_feed.is_running():
        check_svt_feed.start()

@tree.command(name="brief", description="Få en briefing på nyheter inom cybersäkerhet från Cyberbear.")
async def brief(interaction: discord.Interaction):
    await interaction.response.defer(thinking=True)

    message = await create_briefing_message("other")

    await interaction.followup.send(message, suppress_embeds=True)

@tree.command(name="check_svt", description="Kontrollera SVT-flödet nu.")
async def check_svt(interaction: discord.Interaction):
    await interaction.response.defer(thinking=True, ephemeral=True)

    new_articles = await check_svt_feed_once()

    if new_articles:
        await interaction.followup.send(
            "SVT-flödet har kontrollerats. Eventuella nya relevanta artiklar skickas till briefingkanalerna.",
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

client.run(token)
