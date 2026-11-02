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

def make_briefing(articles, cves):
    lines = [
        "# Hallå allesammans, vi kör lite nyheter så här på morgonkvisten innan vi kör igång dagen!",
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
        lines.append(f"### {cve["id"]}")
        lines.append(f"**Allvarlighetsgrad:** {cve['severity']}")

        description = shorten_description(cve["description"])
        lines.append(description)

        lines.append(f"[Läs mer](https://nvd.nist.gov/vuln/detail/{cve['id']})")
        lines.append("")

    return "\n".join(lines)
