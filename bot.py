import asyncio
import os
import discord
import json

from dotenv import load_dotenv
from datetime import datetime, time
from zoneinfo import ZoneInfo
from discord.ext import tasks
from pathlib import Path

from sources import (
    get_latest_articles, 
    get_latest_cves,
    get_svt_articles,
    filter_svt_articles
    )
from briefing import make_briefing, shorten_description
from cve_selection import select_relevant_cves
from ai_ranking import get_ai_ranked_articles

load_dotenv()

token = os.getenv("DISCORD_TOKEN")
if not token:
    raise RuntimeError("DISCORD_TOKEN saknas. Lägg till den i .env-filen.")

intents = discord.Intents.default()
client = discord.Client(intents=intents)
tree = discord.app_commands.CommandTree(client)

SVT_STATE_FILE = Path(__file__).with_name("sent_svt_articles.json")

def load_seen_svt_ids():
    if not SVT_STATE_FILE.exists():
        return None
    
    with SVT_STATE_FILE.open(encoding="utf-8") as file:
        return set(json.load(file))

def save_seen_svt_ids(seen_ids):
    with SVT_STATE_FILE.open("w", encoding="utf-8") as file:
        json.dump(sorted(seen_ids), file, indent=2)

def format_svt_article(article):
    title = article.get("title", "Artikel utan rubrik")
    link = article.get("link", "")

    return (
        f"**🔐  {title}**\n"
        f"[SVT Nyheter · Läs artikeln]({link})"
    )

async def get_relevant_cves():
    candidates = await asyncio.to_thread(get_latest_cves)
    return await asyncio.to_thread(select_relevant_cves, candidates, 3)

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
    await send_scheduled_briefing("morning")

@tasks.loop(time=EVENING_TIME)
async def scheduled_evening_briefing():
    await send_scheduled_briefing("evening")

async def check_svt_feed_once():
    entries = await asyncio.to_thread(get_svt_articles)

    current_ids = {
        entry.get("id") or entry.get("link")
        for entry in entries
        if entry.get("id") or entry.get("link")
    }

    seen_ids = load_seen_svt_ids()

    if seen_ids is None:
        save_seen_svt_ids(current_ids)
        return
    
    new_entries = []
    
    for entry in reversed(entries):
        article_id = entry.get("id") or entry.get("link")

        if article_id and article_id not in seen_ids:
            new_entries.append(entry)

    if not new_entries:
        return

    relevant_entries = filter_svt_articles(new_entries)

    channel_ids = [
        int(value.strip())
        for value in os.getenv("BRIEFING_CHANNEL_IDS", "").split(",")
        if value.strip()
    ]    

    if not channel_ids:
        return

    for entry in new_entries:
        article_id = entry.get("id") or entry.get("link")

        if entry in relevant_entries: 
            message = format_svt_article(entry)

            for channel_id in channel_ids:
                channel = client.get_channel(channel_id)

                if channel is None:
                    channel = await client.fetch_channel(channel_id)
                    
                await channel.send(message, suppress_embeds=True)
            
        seen_ids.add(article_id)
        save_seen_svt_ids(seen_ids)

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

    await check_svt_feed_once()

    await interaction.followup.send(
        "SVT-flödet har kontrollerats. Eventuella nya relevanta artiklar skickas till briefingkanalerna.",
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

# @tree.command(name="preview_svt", description="Visa SVT-artiklar som filtret väljer.")
# async def preview_svt(interaction: discord.Interaction):
#     await interaction.response.defer(thinking=True, ephemeral=True)

#     entries = await asyncio.to_thread(get_svt_articles)
#     matches = await asyncio.to_thread(filter_svt_articles, entries)

#     if not matches:
#         await interaction.followup.send(
#             f"Hämtade {len(entries)} artiklar från SVT, men filtret hittade inga träffar.",
#             ephemeral=True,
#         )
#         return

#     lines = ["**SVT-träffar i det aktuella flödet:**"]

#     for article in matches[:10]:
#         title = article.get("title", "Artikel utan rubrik")
#         link = article.get("link", "")
#         lines.append(f"• [{title}]({link})")

#     await interaction.followup.send("\n".join(lines), ephemeral=True)

# @tree.command(name="test", description="test")
# async def test(interaction: discord.Interaction):
#     await interaction.response.send_message("Hello!")

# --------------------

client.run(token)
