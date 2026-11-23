import json

from pathlib import Path

SVT_RSS_URLS = [
    "https://www.svt.se/nyheter/inrikes/rss.xml",
    "https://www.svt.se/nyheter/utrikes/rss.xml",
]

CONFIG_DIR = Path(__file__).resolve().parent / "config"
KEYWORDS_FILE = CONFIG_DIR / "keywords.json"

def filter_svt_articles(entries):
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

def format_svt_article(article):
    title = article.get("title", "Artikel utan rubrik")
    link = article.get("link", "")

    return (
        f"**🔐  {title}**\n"
        f"[SVT Nyheter · Läs artikeln]({link})"
    )
