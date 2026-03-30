"""
classifier.py — classifies URLs by subdomain into category strings
"""
from urllib.parse import urlparse
from config import SUBDOMAIN_CATEGORIES, ALLOWED_DOMAIN


def classify_url(url: str) -> str:
    """
    Returns a category string such as 'dept_cs', 'library', or 'main'.
    Unknown subdomains fall back to 'other_<subdomain>'.
    """
    host = urlparse(url).netloc.lower().split(":")[0]

    # strip the base domain to get the subdomain part
    if host.endswith("." + ALLOWED_DOMAIN):
        sub = host[: -(len(ALLOWED_DOMAIN) + 1)]   # e.g. "www.cs" or "cs"
    elif host == ALLOWED_DOMAIN:
        sub = ""
    else:
        return "external"

    # handle multi-level subdomains: www.cs.nccu.edu.tw → try "cs"
    # but nccur.lib.nccu.edu.tw → try "nccur.lib" first, then "lib"
    candidates = [sub]
    parts = sub.split(".")
    # add all suffixes from longest to shortest
    for i in range(len(parts)):
        candidates.append(".".join(parts[i:]))

    for candidate in candidates:
        if candidate in SUBDOMAIN_CATEGORIES:
            return SUBDOMAIN_CATEGORIES[candidate]

    # fallback to the last segment
    leaf = parts[-1] if parts else sub
    return f"other_{leaf}" if leaf else "other"


def build_classification_summary(records: list[dict]) -> dict:
    """Takes visited records and returns a {category: {count, urls}} summary."""
    summary: dict = {}
    for rec in records:
        cat = rec.get("category", "other")
        if cat not in summary:
            summary[cat] = {"count": 0, "urls": []}
        summary[cat]["count"] += 1
        summary[cat]["urls"].append(rec["url"])
    return summary
