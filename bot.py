import asyncio
import os
import discord
from dotenv import load_dotenv
from datetime import time
from zoneinfo import ZoneInfo
from discord.ext import tasks

from sources import get_latest_articles, get_latest_cves
from briefing import make_briefing

load_dotenv()

token = os.getenv("DISCORD_TOKEN")
if not token:
    raise RuntimeError("DISCORD_TOKEN saknas. Lägg till den i .env-filen.")

intents = discord.Intents.default()
client = discord.Client(intents=intents)
tree = discord.app_commands.CommandTree(client)

BRIEFING_TIME = time(
    hour=8,
    minute=0,
    tzinfo=ZoneInfo("Europe/Stockholm"),
)

async def create_briefing_message():
    articles = await asyncio.to_thread(get_latest_articles)
    cves = await asyncio.to_thread(get_latest_cves)
    return make_briefing(articles, cves)


@tasks.loop(time=BRIEFING_TIME)
async def scheduled_briefing():
    message = await create_briefing_message()

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

@scheduled_briefing.before_loop
async def before_scheduled_briefing():
    await client.wait_until_ready()

@client.event
async def on_ready():
    synced = await tree.sync()
    print(f"Synkade {len(synced)} globala kommandon.")
    print(f"Inloggad som {client.user}.")

    if not scheduled_briefing.is_running():
        scheduled_briefing.start()

@tree.command(name="brief", description="Få en briefing på nyheter inom cybersäkerhet från Cyberbear.")
async def brief(interaction: discord.Interaction):
    await interaction.response.defer(thinking=True)

    message = await create_briefing_message()

    await interaction.followup.send(message, suppress_embeds=True)

@tree.command(name="test", description="test")
async def test(interaction: discord.Interaction):
    await interaction.response.send_message("Hello!")

client.run(token)
