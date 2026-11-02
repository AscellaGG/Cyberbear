# Cyberbear Discord Bot

Cyberbear is a Python Discord bot that posts a cybersecurity morning briefing. The briefing combines recent headlines from The Hacker News with recently published CVEs from the National Vulnerability Database (NVD).

## Features

- `/brief` creates and sends the current briefing on demand.
- The briefing includes up to three recent The Hacker News articles.
- It includes up to three CVEs published during the previous 24 hours, with their ID, severity, short description, and NVD link.
- CVEs without a CVSS rating are shown as `Not yet rated`.
- A scheduled briefing runs daily at 08:00 in the `Europe/Stockholm` time zone.
- The scheduled briefing is sent to the Discord channels configured in `BRIEFING_CHANNEL_IDS`.
- Link previews are suppressed in briefing messages.

The NVD request currently asks for up to 250 results from the 24-hour window and then selects up to three. If more than 250 CVEs are published in that period, the response may not include every CVE.

## Requirements

- Python 3.10 or later
- A Discord application and bot token

Install the dependencies in an activated virtual environment:

```bash
python -m pip install -r requirements.txt
```

## Configuration

Create a `.env` file in the project root:

```dotenv
DISCORD_TOKEN=your-discord-bot-token
BRIEFING_CHANNEL_IDS=123456789012345678,234567890123456789
```

Replace the example channel IDs with the IDs of the channels where the scheduled briefing should be posted. Separate multiple IDs with commas. The bot needs permission to view each channel and send messages there.

Keep the bot token secret. The `.env` file is excluded from Git.

Invite the bot to each Discord server with the `bot` and `applications.commands` OAuth2 scopes. The bot uses global application commands, so updates may take time to appear.

## Run the bot

With the virtual environment activated, run:

```bash
python bot.py
```

The bot must remain running and connected for the scheduled 08:00 briefing to be sent. Restart it after code changes.

## Project files

- `bot.py` — Discord client, `/brief` command, and daily schedule.
- `sources.py` — The Hacker News RSS and NVD CVE data retrieval.
- `briefing.py` — Briefing message formatting.
- `requirements.txt` — Python dependencies.
- `.env` — Local configuration and bot token; do not commit this file.
