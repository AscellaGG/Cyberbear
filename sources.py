from urllib.request import urlopen
import feedparser
import json
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode
from pathlib import Path

RSS_URL = "https://thehackernews.com/feeds/posts/default?alt=rss"

SVT_RSS_URL = "https://www.svt.se/nyheter/rss.xml"
CONFIG_DIR = Path(__file__).resolve().parent / "config"
KEYWORDS_FILE = CONFIG_DIR / "keywords.json"

NVD_API_URL = "https://services.nvd.nist.gov/rest/json/cves/2.0"

def get_latest_articles():
    # Bound the network wait so the interaction cannot remain pending forever.
    with urlopen(RSS_URL, timeout=10) as response:
        feed = feedparser.parse(response.read())

    articles = [
        {
            "id": article.get("id") or article.get("link"),
            "title": article.get("title", ""),
            "summary": article.get("summary", ""),
            "link": article.get("link", ""),
            "published": article.get("published", "")
        }
        for article in feed.entries
    ]

    with open("test.txt", "w", encoding="utf-8") as file:
        json.dump(articles, file, indent=2, ensure_ascii=False)

    return articles

def get_svt_articles():
    with urlopen(SVT_RSS_URL, timeout=10) as response:
        feed = feedparser.parse(response.read())
    return feed.entries

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


def get_latest_cves():
    end_date = datetime.now(timezone.utc)
    start_date = end_date - timedelta(hours=24)

    parameters = {
        "pubStartDate": start_date.isoformat(timespec="milliseconds").replace("+00:00", "Z"),
        "pubEndDate": end_date.isoformat(timespec="milliseconds").replace("+00:00", "Z"),
        "resultsPerPage": 250
    }

    url = f"{NVD_API_URL}?{urlencode(parameters)}"

    with urlopen(url, timeout=30) as response:
        data = json.loads(response.read().decode("utf-8"))

        cves = []

        for item in data.get("vulnerabilities", []):
            cve = item["cve"]

            if cve.get("vulnStatus") == "Rejected":
                continue

            descriptions = cve.get("descriptions", [])
            description = next(
                (
                    entry["value"]
                    for entry in descriptions
                    if entry.get("lang") == "en"
                ),
                "No English description available.",
            )

            severity = "Not yet rated"
            score = None
            metrics = cve.get("metrics", {})

            for metric_name in (
                "cvssMetricV40",
                "cvssMetricV31",
                "cvssMetricV30",
                "cvssMetricV2",
            ):
                metric_list = metrics.get(metric_name, [])
                if metric_list:
                    cvss_data = metric_list[0]["cvssData"]
                    severity = cvss_data.get("baseSeverity", "Not yet rated")
                    score = cvss_data.get("baseScore")
                    break
            
            if score is None or severity == "Not yet rated":
                continue

            cves.append({
                "id": cve["id"],
                "description": description,
                "published": cve["published"],
                "severity": severity,
                "score": score,
                "affected_products": extract_affected_products(cve),
            })
        
        cves.sort(key=lambda item: item["score"], reverse=True)
        return cves

def extract_affected_products(cve):
    products = set()

    for source in cve.get("affected", []):
        for affected in source.get("affectedData", []):
            vendor = affected.get("vendor", "").strip()
            product = affected.get("product", "").strip()

            if vendor or product:
                products.add(f"{vendor}:{product}".casefold())

            for module in affected.get("modules", []):
                products.add(f"{vendor}:{product}:{module}".casefold())

    for configuration in cve.get("configurations", []):
        for node in configuration.get("nodes", []):
            for match in node.get("cpeMatch", []):
                if not match.get("vulnerable", False):
                    continue

                criteria = match.get("criteria", "")
                parts = criteria.split(":")

                # A CPE 2.3 string has vendor at index 3 and product at index 4
                if len(parts) > 4 and parts[0] == "cpe" and parts[1] == "2.3":
                    vendor = parts[3]
                    product = parts[4]
                    products.add(f"{vendor}:{product}".casefold())

    return sorted(products)
