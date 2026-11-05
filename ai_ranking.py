from dotenv import load_dotenv
from anthropic import Anthropic
import os
from urllib.request import urlopen
import feedparser
import json
import threading
import time
from datetime import datetime, timedelta, timezone 
from urllib.parse import urlencode
from pathlib import Path

load_dotenv()  # Loads ANTHROPIC_API_KEY from your .env file
client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

RSS_URL = "https://thehackernews.com/feeds/posts/default?alt=rss"
SYSTEM_PROMPT_FILE = Path(__file__).resolve().with_name("systemprompt.txt")
AI_CACHE_SECONDS = 60 * 60
_ai_cache_lock = threading.Lock()
_cached_ranked_articles = None
_ai_cache_created_at = 0.0

def call_ai(user_content):
    sysfile = ""

    with SYSTEM_PROMPT_FILE.open(encoding="utf-8") as file:
        sysfile = file.read()

    articles_json = json.dumps(user_content, ensure_ascii=False, indent=2)

    response = client.messages.create(
        model="claude-haiku-5-5",
        max_tokens=20000,
        thinking={"type": "disabled"},
        system=sysfile,
        messages=[
            {"role": "user", "content": articles_json}
        ],
    )

    response_text = next(
        (block.text for block in response.content if block.type == "text"),
        None,
    )
    if response_text is None:
        raise ValueError("The AI response did not contain a text block.")

    return response_text


def get_ai_ranked_articles():
    global _cached_ranked_articles, _ai_cache_created_at

    with _ai_cache_lock:
        now = time.monotonic()
        if (
            _cached_ranked_articles is not None
            and now - _ai_cache_created_at < AI_CACHE_SECONDS
        ):
            print("Using cached AI-ranked articles.")
            return _cached_ranked_articles

        ranked_articles = _fetch_and_rank_articles()
        _cached_ranked_articles = ranked_articles
        _ai_cache_created_at = time.monotonic()
        return ranked_articles


def _fetch_and_rank_articles():
    # Bound the network wait so the interaction cannot remain pending forever.
    with urlopen(RSS_URL, timeout=10) as response:
        feed = feedparser.parse(response.read())

    articles = []

    for article in feed.entries:

        articles.append(
            {
                "id": article.get("id") or article.get("link"),
                "title": article.get("title", ""),
                "summary": article.get("summary", ""),
                "link": article.get("link", ""),
                "published": article.get("published", "")
            }
        )
        
    filtered_articles = filter_articles(articles)

    ai_response = call_ai(filtered_articles)

    ai_data = json.loads(ai_response)

    with open("ai_response.txt", "w", encoding="utf-8") as file:
        json.dump(ai_data, file, indent=2, ensure_ascii=False)

    ranked_articles = ai_data.get("ranked_articles")
    if not isinstance(ranked_articles, list):
        raise ValueError("The AI response is missing the ranked_articles list.")

    return ranked_articles

def filter_articles(articles):
    filtered_articles = []
    
    end_date = datetime.now(timezone.utc)
    start_date = end_date - timedelta(hours=24)
    

    for article in articles:
        
        if not article["published"]:
            continue
        
        published = datetime.strptime(article["published"], "%a, %d %b %Y %H:%M:%S %z")

        if published > start_date:
            filtered_articles.append(article)

    return filtered_articles

