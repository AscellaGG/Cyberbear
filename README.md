# Cyberbear Discord Bot

Cyberbear is a Python Discord bot that shares cybersecurity news and vulnerability information. It creates a daily morning briefing from The Hacker News and recent CVEs, and monitors SVT News for new Swedish cybersecurity-related stories.

## Features

- `/brief` creates and sends the current morning briefing on demand.
- The briefing includes up to three recent articles from The Hacker News.
- It includes up to three CVEs published during the previous 24 hours, with their ID, severity, short description, and NVD link.
- CVEs without a CVSS rating are shown as `Not yet rated`.
- A scheduled briefing runs daily at 08:00 in the `Europe/Stockholm` time zone.
- The scheduled briefing is sent to the Discord channels configured in `BRIEFING_CHANNEL_IDS`.
- SVT News is checked at bot startup and then every 10 minutes for new articles matching the keyword rules in `keywords.json`.
- Matching SVT articles are sent to the same channels configured in `BRIEFING_CHANNEL_IDS`.
- `/check_svt` triggers an SVT check immediately. Any new matching articles are sent to the briefing channels.
- Previously handled SVT article IDs are stored in `sent_svt_articles.json` to prevent duplicate posts. On the first run, the current articles in the feed are recorded without posting them, so old stories are not sent in a batch.
- Link previews are suppressed in bot messages.

The NVD request asks for up to 250 results from the 24-hour window and then selects up to three. If more than 250 CVEs are published in that period, the response may not include every CVE.

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

Replace the example channel IDs with the IDs of the channels where the briefing and matching SVT articles should be posted. Separate multiple IDs with commas. The bot needs permission to view each channel and send messages there.

Keep the bot token secret. The `.env` file is excluded from Git.

Invite the bot to each Discord server with the `bot` and `applications.commands` OAuth2 scopes. The bot uses global application commands, so updates may take time to appear.

## SVT keyword filtering

`keywords.json` contains the words used to identify relevant SVT articles. The filter accepts an article when either:

1. Its title or summary contains a direct cybersecurity keyword, or
2. It contains both an attack signal and a system or target keyword.

This second rule helps catch incidents involving systems such as store refrigeration equipment even when the article does not use a specific cybersecurity term. The keyword filter is intentionally simple and may need adjustments as you see false positives or missed stories.

## Run with Docker Compose

Install Docker Engine and the Docker Compose plugin on the machine that will host the bot. Copy `.env.example` to `.env` and fill in the production bot token and channel IDs. Keep `.env` private; it is ignored by Git and excluded from the Docker build context.

Build the image and start the bot in the background:

```bash
docker compose up -d --build
```

See live logs with:

```bash
docker compose logs -f
```

Stop the bot with:

```bash
docker compose down
```

After pulling code changes, rebuild and restart it with `docker compose up -d --build`. The `unless-stopped` restart policy brings it back after a machine restart or process exit. Only run one production copy at a time, or scheduled briefings and news posts may be duplicated.

### Automatically deploy pushes to `main` on Ubuntu

The `deploy/` files provide a systemd timer that checks the public GitHub repository every five minutes. On a new commit, it updates the dedicated server checkout and rebuilds/restarts the Compose service. It does not require an inbound connection to the home server. Install it on a server checkout located at `/opt/cyberbear`:

```bash
sudo install -d -m 755 /var/lib/cyberbear
sudo cp deploy/cyberbear-deploy.service deploy/cyberbear-deploy.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now cyberbear-deploy.timer
sudo systemctl start cyberbear-deploy.service
```

The initial service run deploys the current `main` commit too. View its output with `sudo journalctl -u cyberbear-deploy.service -n 100 --no-pager`, and view the timer with `systemctl status cyberbear-deploy.timer`. The timer runs as root, so the deployment checkout and `.env` should be dedicated to this bot; do not keep hand-edited files in that checkout. Put the production `.env` at `/opt/cyberbear/.env` and restrict it with `sudo chmod 600 /opt/cyberbear/.env`.

## Run directly with Python

With the virtual environment activated, run:

```bash
python bot.py
```

The bot must remain running and connected for the scheduled briefing and SVT monitoring to work. Restart it after code changes.

## Project files

- `bot.py` — Discord client, slash commands, scheduled briefing, and SVT monitoring.
- `sources.py` — The Hacker News and SVT RSS feeds, keyword filtering, and NVD CVE retrieval.
- `keywords.json` — Swedish and English keywords used by the SVT article filter.
- `briefing.py` — Morning briefing message formatting.
- `sent_svt_articles.json` — Runtime state containing handled SVT article IDs; generated automatically and excluded from Git.
- `requirements.txt` — Python dependencies.
- `Dockerfile` and `compose.yaml` — Container image and service configuration.
- `.env` — Local configuration and bot token; do not commit this file.
