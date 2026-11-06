import json
import re
import feedparser
import json
import logging
import asyncio

from pathlib import Path
from urllib.request import urlopen
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode
from pathlib import Path
from calendar import timegm

logger = logging.getLogger(__name__)

CONFIG_DIR = Path(__file__).resolve().parent / "config"
WATCHLIST_FILE = CONFIG_DIR / "cve_watchlist.json"

SVT_RSS_URLS = [
    "https://www.svt.se/nyheter/inrikes/rss.xml",
    "https://www.svt.se/nyheter/utrikes/rss.xml",
]

NVD_API_URL = "https://services.nvd.nist.gov/rest/json/cves/2.0"

def get_latest_cves():
    end_date = datetime.now(timezone.utc)
    start_date = end_date - timedelta(hours=12)

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

def normalize_text(value):
    text = str(value).casefold()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())

def contains_phrase(text, phrase):
    normalized_text = normalize_text(text)
    normalized_phrase = normalize_text(phrase)

    return f" {normalized_phrase} " in f" {normalized_text} "

def find_matching_categories(cve, watchlist):
    products = cve.get("affected_products", [])
    matching_labels = []

    for category in watchlist["categories"].values():
        for term in category["terms"]:
            if any(contains_phrase(product, term) for product in products):
                matching_labels.append(category["label"])
                break
    
    return matching_labels

def select_relevant_cves(cves, limit=3):
    with WATCHLIST_FILE.open(encoding="utf-8") as file:
        watchlist = json.load(file)

    matching_cves = []

    for cve in cves:
        categories = find_matching_categories(cve, watchlist)

        if not categories:
            continue
        
        selected_cve = cve.copy()
        selected_cve["matched_categories"] = categories
        matching_cves.append(selected_cve)

    matching_cves.sort(key=lambda cve: cve["score"], reverse=True)
    return matching_cves[:limit]

async def get_relevant_cves():
    candidates = await asyncio.to_thread(get_latest_cves)
    return await asyncio.to_thread(select_relevant_cves, candidates, 3)
