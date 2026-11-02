from urllib.request import urlopen
import feedparser
import json
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

RSS_URL = "https://thehackernews.com/feeds/posts/default?alt=rss"

NVD_API_URL = "https://services.nvd.nist.gov/rest/json/cves/2.0"

def get_latest_articles():
    # Bound the network wait so the interaction cannot remain pending forever.
    with urlopen(RSS_URL, timeout=10) as response:
        feed = feedparser.parse(response.read())
    return feed.entries

def get_latest_cves(limit=3):
    end_date = datetime.now(timezone.utc)
    start_date = end_date - timedelta(hours=24)

    parameters = {
        "pubStartDate": start_date.isoformat(timespec="milliseconds").replace("+00:00", "Z"),
        "pubEndDate": end_date.isoformat(timespec="milliseconds").replace("+00:00", "Z"),
        "resultsPerPage": 250
    }

    url = f"{NVD_API_URL}?{urlencode(parameters)}"

    with urlopen(url, timeout=15) as response:
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
            
            cves.append({
                "id": cve["id"],
                "description": description,
                "published": cve["published"],
                "severity": severity,
                "score": score
            })
        
        cves.sort(key=lambda item: item["published"], reverse=True)
        return cves[:limit]