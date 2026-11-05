import json
import random
from pathlib import Path

PHRASES_FILE = Path(__file__).resolve().parent / "config" / "phrases.json"

def shorten_description(text, max_length=300):
    text = text.strip()

    if len(text) <= max_length:
        return text

    # Om det finns en meningsgräns inom utrymmet, kapa där.
    sentence_end = max(
        text.rfind(".", 0, max_length),
        text.rfind("!", 0, max_length),
        text.rfind("?", 0, max_length),
    )

    if sentence_end > 0:
        return text[: sentence_end + 1]

    # Annars kapa vid ett ordmellanrum.
    shortened = text[:max_length].rsplit(" ", 1)[0]
    return shortened + "…"

def make_briefing(articles, cves, period):

    phrase = get_briefing_phrase(period)

    lines = [
        f"# {phrase}",
        "",
        "## 📰  Senaste nytt:",
        "",
    ]

    for article in articles[:3]:
        lines.append(f"**{article.title}**")
        lines.append(f"[Läs artikeln]({article.link})")
        lines.append("")

    lines.extend([
        "## 🛡️  Nya sårbarheter:"
    ])

    for cve in cves:
        lines.append(f"### {cve['id']}")
        lines.append(f"**Allvarlighetsgrad:** {cve['severity']}, {cve['score']}")

        description = shorten_description(cve['description'])
        lines.append(description)

        lines.append(f"[Läs mer](https://nvd.nist.gov/vuln/detail/{cve['id']})")
        lines.append("")

    return "\n".join(lines)

def get_briefing_phrase(period):
    with PHRASES_FILE.open(encoding="utf-8") as file:
        all_phrases = json.load(file)

    phrases = all_phrases[period]

    phrase = random.choice(phrases)

    return phrase
    # Handle errors???
