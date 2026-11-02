import asyncio
import os
import discord
from dotenv import load_dotenv

from sources import get_latest_articles, get_latest_cves
from briefing import make_briefing

load_dotenv()

token = os.getenv("DISCORD_TOKEN")
if not token:
    raise RuntimeError("DISCORD_TOKEN saknas. Lägg till den i .env-filen.")

intents = discord.Intents.default()
client = discord.Client(intents=intents)
tree = discord.app_commands.CommandTree(client)

@client.event
async def on_ready():
    synced = await tree.sync()
    print(f"Synkade {len(synced)} globala kommandon.")
    print(f"Inloggad som {client.user}.")

@tree.command(name="brief", description="Få en briefing på nyheter inom cybersäkerhet från Cyberbear.")
async def brief(interaction: discord.Interaction):
    await interaction.response.defer(thinking=True)

    articles = await asyncio.to_thread(get_latest_articles)
    cves = await asyncio.to_thread(get_latest_cves)

    message = make_briefing(articles, cves)

    await interaction.followup.send(message, suppress_embeds=True)

@tree.command(name="test", description="test")
async def test(interaction: discord.Interaction):
    await interaction.response.send_message("Hello!")

client.run(token)
