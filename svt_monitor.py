from urllib.request import urlopen
import feedparser
import json
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode
from pathlib import Path
from calendar import timegm
import logging
import asyncio

logger = logging.getLogger(__name__)

SVT_RSS_URLS = [
    "https://www.svt.se/nyheter/inrikes/rss.xml",
    "https://www.svt.se/nyheter/utrikes/rss.xml",
]

SVT_STATE_FILE = Path(__file__).with_name("sent_svt_articles.json")

CONFIG_DIR = Path(__file__).resolve().parent / "config"
KEYWORDS_FILE = CONFIG_DIR / "keywords.json"

def get_svt_articles():
    try:
        articles_by_id = {}

        for rss_url in SVT_RSS_URLS:
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

    except Exception as error:
        logger.error("Failed to fetch SVT articles.")
        raise

def filter_svt_articles(entries):
    try:
        with KEYWORDS_FILE.open(encoding="utf-8") as file:
            keywords = json.load(file)
        
        direct_keywords = keywords["direct_match"]
        contextual_keywords = keywords["contextual_match"]
        attack_signals = contextual_keywords["attack_signals"]
        systems_or_targets = contextual_keywords["systems_or_targets"]

        relevant_articles = []

        for article in entries:
            title = article.get("title", "")
            summary = article.get("summary", "")
            text = f"{title} {summary}".casefold()

            has_direct_keyword = any(
                word.casefold() in text
                for word in direct_keywords
            )

            has_attack_signal = any(
                word.casefold() in text
                for word in attack_signals
            )

            has_system_or_target = any(
                word.casefold() in text
                for word in systems_or_targets
            )

            if has_direct_keyword or (has_attack_signal and has_system_or_target):
                relevant_articles.append(article)

        return relevant_articles

    except Exception as error:
        logging.error("There was an error filtering the articles.")
        raise

def load_seen_svt_ids():
    try:
        if not SVT_STATE_FILE.exists():
            return None
        
        with SVT_STATE_FILE.open(encoding="utf-8") as file:
            return set(json.load(file))
    except Exception as error:
        logger.error("Could not load sent_svt_articles.json.")
        raise

def save_seen_svt_ids(seen_ids):
    try:
        with SVT_STATE_FILE.open("w", encoding="utf-8") as file:
            json.dump(sorted(seen_ids), file, indent=2)
    except Exception as error:
        logger.exception("Could not save to sent_svt_articles.json.")
        raise

def format_svt_article(article):
    title = article.get("title", "Artikel utan rubrik")
    link = article.get("link", "")

    return (
        f"**🔐  {title}**\n"
        f"[SVT Nyheter · Läs artikeln]({link})"
    )

async def get_relevant_svt_articles():

    entries = await asyncio.to_thread(get_svt_articles)

    current_ids = {
        entry.get("id") or entry.get("link")
        for entry in entries
        if entry.get("id") or entry.get("link")
    }

    seen_ids = load_seen_svt_ids()

    if seen_ids is None:
        save_seen_svt_ids(current_ids)
        return []
    
    new_entries = []
    
    for entry in reversed(entries):
        article_id = entry.get("id") or entry.get("link")

        if article_id and article_id not in seen_ids:
            new_entries.append(entry)

    if not new_entries:
        return []

    relevant_entries = filter_svt_articles(new_entries)
    
    return relevant_entries
