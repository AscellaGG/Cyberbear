import asyncio
import os
from urllib.request import urlopen

import feedparser
import discord
from dotenv import load_dotenv

load_dotenv()

token = os.getenv("DISCORD_TOKEN")
if not token:
    raise RuntimeError("DISCORD_TOKEN saknas. Lägg till den i .env-filen.")

intents = discord.Intents.default()
client = discord.Client(intents=intents)
tree = discord.app_commands.CommandTree(client)


RSS_URL = "https://thehackernews.com/feeds/posts/default?alt=rss"


def get_latest_articles():
    # Bound the network wait so the interaction cannot remain pending forever.
    with urlopen(RSS_URL, timeout=10) as response:
        feed = feedparser.parse(response.read())
    return feed.entries

def print_articles(articles):
    for article in articles[:5]:
        print(article.title)
        print(article.published)
        print(article.link)
        print()

def make_briefing(articles):
    lines = [
        "# Hallå allesammans, vi kör lite nyheter så här på morgonkvisten innan vi kör igång dagen!",
        "",
        "## 📰  Toppnyheter:",
        "",
    ]

    for article in articles[:3]:
        lines.append(f"**{article.title}**")
        lines.append(f"[Läs artikeln]({article.link})")
        lines.append("")

    lines.extend([
        "## 🛡️  Nya sårbarheter:",
        "### Kommer snart.",
    ])
    return "\n".join(lines)


@client.event
async def on_ready():
    synced = await tree.sync()
    print(f"Synkade {len(synced)} globala kommandon.")
    print(f"Inloggad som {client.user}.")

@tree.command(name="brief", description="Få en briefing på nyheter inom cybersäkerhet från Cyberbear.")
async def brief(interaction: discord.Interaction):
    await interaction.response.defer(thinking=True)

    articles = await asyncio.to_thread(get_latest_articles)
    message = make_briefing(articles)
    await interaction.followup.send(message, suppress_embeds=True)

@tree.command(name="test", description="test")
async def test(interaction: discord.Interaction):
    await interaction.response.send_message("Hello!")

client.run(token)
