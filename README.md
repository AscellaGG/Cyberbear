# Cyberbear Discord Bot

Cyberbear is a Python Discord bot that shares cybersecurity news and vulnerability information. It creates morning and evening briefings with AI-ranked articles from The Hacker News and recent CVEs, and monitors RSS feeds for cybersecurity-related articles.

## Features

- `/brief` creates and sends a briefing on demand using an evening introduction.
- The briefing sends recent The Hacker News articles from the previous 24 hours to Anthropic Claude Haiku 5.5 for relevance ranking, then includes up to the top three.
- Article relevance is judged for cybersecurity engineering students using the instructions in `systemprompt.txt`; the AI preserves article details and adds a rank, relevance score, and reason.
- It checks up to 250 CVEs published during the previous 24 hours, skips CVEs without a CVSS score, matches affected products against `config/cve_watchlist.json`, and displays up to three matching CVEs ranked by numeric CVSS score.
- CVE entries include affected-product hints extracted from NVD's `affected` and CPE configuration data.
- `/check_cve` privately displays the same watchlist-matched CVEs as the morning briefing.
- A morning briefing runs daily at 08:00 and an evening briefing at 20:00 in the `Europe/Stockholm` time zone.
- Both scheduled briefings are sent to the Discord channels configured in `BRIEFING_CHANNEL_IDS`.
- Briefing introductions are chosen randomly from the `morning` or `evening` phrase list in `config/phrases.json`, depending on which scheduled briefing is running.
- In production, configured RSS feeds are checked every 10 minutes. `/check_feeds` checks all configured feeds immediately.
- SVT articles are filtered using the keyword rules in `config/keywords.json`; the CERT feed currently sends every new article without filtering.
- Feed articles are sent to the channels configured in `BRIEFING_CHANNEL_IDS`.
- Processed article IDs are stored by feed in `processed_articles.json` to prevent duplicate posts. The first check for a feed records its current articles as a baseline without posting them, so adding a feed does not send its existing backlog.
- Link previews are suppressed in bot messages.

The watchlist uses broad cybersecurity product areas and normalized whole-word or phrase matching against NVD's affected-product hints. CVEs without affected-product data, or whose product names do not match a watchlist term, are omitted. The current selection does not yet use known-exploited vulnerability data. If more than 250 CVEs are published in the 24-hour window, the response may not include every CVE.

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
ANTHROPIC_API_KEY=your-anthropic-api-key
```

Replace the example channel IDs with the IDs of the channels where the briefing and matching SVT articles should be posted. Separate multiple IDs with commas. The bot needs permission to view each channel and send messages there.

Keep both API keys secret. The `.env` file is excluded from Git. Anthropic API usage is billed separately from Claude chat subscriptions; make sure the Anthropic account has API credits or billing enabled.

Invite the bot to each Discord server with the `bot` and `applications.commands` OAuth2 scopes. The bot uses global application commands, so updates may take time to appear.

## RSS feeds

`feeds.py` contains the shared RSS fetching, deduplication, article history, and feed-checking flow. Each feed has its own key and URL list. To add a feed, add an entry to `FEEDS` with its key, URL list, optional filter, and message formatter. A `None` filter means all new entries are accepted.

`svt_monitor.py` contains SVT-specific settings and behavior: its RSS URLs, keyword filter, and message formatter. SVT's filter accepts an article when either:

`config/keywords.json` contains the words used to identify relevant SVT articles:

1. Its title or summary contains a direct cybersecurity keyword, or
2. It contains both an attack signal and a system or target keyword.

This second rule helps catch incidents involving systems such as store refrigeration equipment even when the article does not use a specific cybersecurity term. The keyword filter is intentionally simple and may need adjustments as you see false positives or missed stories.

## Briefing phrases

`config/phrases.json` contains separate `morning` and `evening` lists. The scheduled briefings select a random introduction from the list for their period. Keep at least one phrase in each list so the bot can choose an introduction.

## Run with Docker Compose

Install Docker Engine and the Docker Compose plugin on the machine that will host the bot. Copy `.env.example` to `.env` and fill in the production bot token, channel IDs, and Anthropic API key. Keep `.env` private; it is ignored by Git and excluded from the Docker build context.

Compose stores the production SQLite database at `/var/lib/cyberbear/cyberbear.sqlite3` on the host. Create `/var/lib/cyberbear` before starting the service; the bot creates the database file and tables on its first startup. This directory is mounted into the container, so the database survives image rebuilds and deployments. Direct local runs with `python bot.py` use `data/cyberbear-dev.sqlite3` by default.

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

The `/var/lib/cyberbear` directory is persistent bot data storage for SQLite as well as deployment state. Keep it when updating or redeploying the bot.

The initial service run deploys the current `main` commit too. View its output with `sudo journalctl -u cyberbear-deploy.service -n 100 --no-pager`, and view the timer with `systemctl status cyberbear-deploy.timer`. The timer runs as root, so the deployment checkout and `.env` should be dedicated to this bot; do not keep hand-edited files in that checkout. Put the production `.env` at `/opt/cyberbear/.env` and restrict it with `sudo chmod 600 /opt/cyberbear/.env`.

## Run directly with Python

With the virtual environment activated, run:

```bash
python bot.py
```

The bot must remain running and connected for the scheduled briefings and feed checks to work. In `BOT_ENV=test`, automatic scheduled jobs are disabled; use `/check_feeds` to check feeds manually. Restart the bot after code changes.

## Project files

- `bot.py` — Discord client, slash commands, scheduled briefings, and scheduled feed-check loop.
- `feeds.py` — RSS retrieval, per-feed filtering and formatting dispatch, processed article IDs, and feed-check orchestration.
- `svt_monitor.py` — SVT RSS URLs, SVT keyword filtering, and SVT message formatting.
- `cve_selection.py` — Watchlist matching and CVE ranking.
- `ai_ranking.py` — Fetches recent Hacker News articles, asks Claude Haiku 5.5 to rank them, and returns the ranked article data.
- `systemprompt.txt` — Instructions for ranking articles by relevance to cybersecurity engineering students.
- `config/keywords.json` — Swedish and English keywords used by the SVT article filter.
- `config/cve_watchlist.json` — Broad cybersecurity topics and product families used to filter CVEs.
- `config/phrases.json` — Morning and evening briefing introduction lists.
- `briefing.py` — Morning briefing message formatting.
- `processed_articles.json` — Runtime state containing handled article IDs grouped by feed; generated automatically and excluded from Git.
- `database.py` — SQLite database initialization for quiz data.
- `requirements.txt` — Python dependencies.
- `Dockerfile` and `compose.yaml` — Container image and service configuration.
- `.env` — Local configuration and bot token; do not commit this file.


## To-Dos

- Add known-exploited vulnerability data to CVE prioritization.
- Send patchnotes on updates
