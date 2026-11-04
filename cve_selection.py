import json
import re
from pathlib import Path

WATCHLIST_FILE = Path(__file__).with_name("cve_watchlist.json")

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