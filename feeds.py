import feedparser
import json
import logging
import asyncio

from urllib.request import urlopen
from calendar import timegm
from pathlib import Path

from svt_monitor import SVT_RSS_URLS, filter_svt_articles, format_svt_article

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent
STATE_FILE = BASE_DIR / "processed_articles.json"
OLD_SVT_STATE_FILE = BASE_DIR / "sent_svt_articles.json"

def get_article_id(article):
    return article.get("id") or article.get("link")

def get_articles(RSS_URLS):
    articles_by_id = {}

    for rss_url in RSS_URLS:
        with urlopen(rss_url, timeout=10) as response:
            feed = feedparser.parse(response.read())

        for article in feed.entries:
            article_id = article.get("id") or article.get("link")

            if article_id:
                articles_by_id[article_id] = article

    articles = list(articles_by_id.values())

    articles.sort(
        key=lambda article: (
            timegm(article.get("published_parsed"))
            if article.get("published_parsed")
            else 0
        ),
        reverse=True,
    )

    return articles

def format_misc_article(article):
    title = article.get("title", "Artikel utan rubrik")
    link = article.get("link", "")
    return f"**{title}**\n[Läs artikeln]({link})"

FEEDS = [
    {
        "key": "svt",
        "urls": SVT_RSS_URLS,
        "filter": filter_svt_articles,
        "format": format_svt_article,
    },
    {
        "key": "cert",
        "urls": ["https://www.cert.se/feed.rss"],
        "filter": None,
        "format": format_misc_article,
    },
]

def load_article_state():
    if STATE_FILE.exists():
        with STATE_FILE.open(encoding="utf-8") as file:
            return json.load(file)
    
    if OLD_SVT_STATE_FILE.exists():
        with OLD_SVT_STATE_FILE.open(encoding="utf-8") as file:
            old_svt_ids = json.load(file)
        return {"svt": old_svt_ids}

    return {}

def save_article_state(state):
    temporary_file = STATE_FILE.with_suffix(".tmp")

    with temporary_file.open("w", encoding="utf-8") as file:
        json.dump(state, file, indent=2, ensure_ascii=False)

    temporary_file.replace(STATE_FILE)

async def check_all_feeds_once(send_message):
    state = load_article_state()
    posted_count = 0

    for feed_config in FEEDS:
        feed_key = feed_config["key"]

        try:
            entries = await asyncio.to_thread(
                get_articles,
                feed_config["urls"],
            )
        except Exception:
            logger.exception("Could not fetch feed %s.", feed_key)
            continue
        
        current_ids = {
            get_article_id(article)
            for article in entries
            if get_article_id(article)
        }

        if feed_key not in state:
            state[feed_key] = sorted(current_ids)
            save_article_state(state)
            logger.info("Recorded initial article baseline for %s", feed_key)
            continue

        processed_ids = set(state[feed_key])
        new_entries = [
            article
            for article in entries
            if get_article_id(article) not in processed_ids
        ]

        article_filter = feed_config["filter"]
        if article_filter is None:
            accepted_ids = {
                get_article_id(article) for article in new_entries
            }
        else: 
            accepted_enteries = article_filter(new_entries)
            accepted_ids = {
                get_article_id(article) for article in accepted_enteries
            }

        for article in new_entries:
            article_id = get_article_id(article)

            if article_id in accepted_ids:
                message = feed_config["format"](article)

                try:
                    await send_message(message)
                except Exception:
                    logger.exception(
                        "Could not send article from %s: %s",
                        feed_key,
                        article.get("title", article_id)
                    )
                    continue

                posted_count += 1
            
            processed_ids.add(article_id)
            state[feed_key] = sorted(processed_ids)
            save_article_state(state)
    return posted_count
