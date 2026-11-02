# Cyberbear Discord Bot

Cyberbear is a Python Discord bot for delivering a morning cybersecurity briefing. The current `/brief` command fetches recent headlines from The Hacker News RSS feed. CVE coverage and article prioritization are planned next steps.

## Current features

- `/brief` fetches up to three recent articles from The Hacker News.
- Article links are included in the response without link preview cards.
- The response includes a placeholder for future vulnerability coverage.

## Requirements

- Python 3.10 or later
- A Discord application and bot token

Install the Python dependencies in an activated virtual environment:

```bash
python -m pip install -r requirements.txt
```

## Configuration

Create a `.env` file in the project root:

```dotenv
DISCORD_TOKEN=your-discord-bot-token
```

Keep the token secret. The `.env` file is excluded from Git.

Invite the bot to your Discord server with the `bot` and `applications.commands` OAuth2 scopes. The bot currently uses global application commands, so updates may take some time to appear in Discord.

## Run the bot

With the virtual environment activated, run:

```bash
python bot.py
```

Restart the process after changing the code.

## Development roadmap

- Filter articles to the previous day's publication date.
- Rank news by practical importance rather than feed order.
- Add a small number of relevant CVEs to the briefing.
- Add an automated morning post after the on-demand `/brief` workflow is reliable.

## Project files

- `bot.py` — Discord bot, slash commands, RSS fetching and briefing formatting.
- `requirements.txt` — Python dependencies.
- `.env` — local configuration and bot token; do not commit this file.
