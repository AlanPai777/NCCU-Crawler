#!/usr/bin/env python3
"""
crawler.py — BFS web crawler for *.nccu.edu.tw

Crawls all reachable pages and documents under the nccu.edu.tw domain,
classifies them by subdomain, and saves HTML and documents to disk.

Usage:
  python3 crawler.py                                  # full crawl
  python3 crawler.py --max-pages 100 --max-depth 2   # quick test
  python3 crawler.py --seed https://aca.nccu.edu.tw  # single subdomain
"""

import os
import sys
import json
import time
import signal
import argparse
import logging
from collections import defaultdict, deque
from datetime import datetime
from urllib.parse import urlparse, urljoin, urlunparse, parse_qs, urlencode, unquote
from pathlib import Path

import httpx
from bs4 import BeautifulSoup

from config import (
    START_URL, ALLOWED_DOMAIN,
    MAX_DEPTH, MAX_PAGES_TOTAL, MAX_PAGES_PER_HOST, REQUEST_DELAY,
    OUTPUT_DIR, MAP_FILE, CLASSIFIED_FILE, LOG_FILE,
    IGNORED_EXTENSIONS, IGNORED_URL_PATTERNS, DOCUMENT_EXTENSIONS,
    EXTRA_SEEDS,
)
from classifier import classify_url, build_classification_summary
from downloader import (
    fetch, classify_content,
    save_html, save_document, make_client,
)

# ── Logging ──────────────────────────────────────────────────
os.makedirs(OUTPUT_DIR, exist_ok=True)
logger = logging.getLogger("nccu_crawler")
logger.setLevel(logging.INFO)
_fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", "%H:%M:%S")
_fh  = logging.FileHandler(LOG_FILE, encoding="utf-8")
_fh.setFormatter(_fmt)
_ch  = logging.StreamHandler(sys.stdout)
_ch.setFormatter(_fmt)
logger.addHandler(_fh)
logger.addHandler(_ch)

# ── Global State ─────────────────────────────────────────────
visited:        dict[str, dict] = {}   # url → record
pages_per_host: dict[str, int]  = defaultdict(int)
interrupted:    bool            = False
_delay:         float           = REQUEST_DELAY
_url_prefixes:  list[str]       = []   # if set, URLs must match at least one prefix


def _handle_signal(sig, frame):
    global interrupted
    logger.warning("⚠️  Interrupted — finishing current request then saving...")
    interrupted = True


signal.signal(signal.SIGINT,  _handle_signal)
signal.signal(signal.SIGTERM, _handle_signal)


# ── URL Utilities ─────────────────────────────────────────────

def normalize(url: str) -> str:
    p = urlparse(url)
    # Decode percent-encoded paths to deduplicate /zh/page and /zh/%e9%a0%81%e9%9d%a2
    decoded_path = unquote(p.path).rstrip("/") or "/"
    # Strip query params that do not affect content (e.g. ?view=default)
    params = parse_qs(p.query, keep_blank_values=True)
    params.pop("view", None)
    clean_query = urlencode(params, doseq=True)
    return urlunparse((
        p.scheme, p.netloc,
        decoded_path,
        p.params, clean_query, ""
    )).lower()


def subdomain_of(url: str) -> str:
    host = urlparse(url).netloc.lower().split(":")[0]
    if host.endswith("." + ALLOWED_DOMAIN):
        return host[: -(len(ALLOWED_DOMAIN) + 1)]
    return "" if host == ALLOWED_DOMAIN else host


def is_allowed(url: str) -> bool:
    """
    Allow a URL if:
      1. Scheme is http or https
      2. Host is nccu.edu.tw or *.nccu.edu.tw
      3. Extension is not in IGNORED_EXTENSIONS (images, CSS, JS, etc.)
         Note: DOCUMENT_EXTENSIONS (pdf, doc, etc.) are allowed
      4. URL does not match any IGNORED_URL_PATTERNS
      5. If --url-prefix is set, URL must contain at least one prefix
    """
    try:
        p = urlparse(url)
        if p.scheme not in ("http", "https"):
            return False
        host = p.netloc.lower().split(":")[0]
        if host != ALLOWED_DOMAIN and not host.endswith("." + ALLOWED_DOMAIN):
            return False
        ext = Path(p.path.lower()).suffix
        if ext in IGNORED_EXTENSIONS:     # skip images, CSS, JS, etc.
            return False
        raw = url.lower()
        if any(pat in raw for pat in IGNORED_URL_PATTERNS):
            return False
        if _url_prefixes and not any(pfx in raw for pfx in _url_prefixes):
            return False
        return True
    except Exception:
        return False


def extract_links(base: str, html_bytes: bytes) -> list[str]:
    """Extract all allowed links (including document links) from HTML."""
    try:
        soup = BeautifulSoup(html_bytes, "html.parser")
    except Exception:
        return []
    result = set()
    for tag in soup.find_all("a", href=True):
        href = tag["href"].strip()
        if not href:
            continue
        full = urljoin(base, href).replace("http://", "https://")
        norm = normalize(full)
        if is_allowed(norm):
            result.add(norm)
    return list(result)


# ── Sitemap Discovery ──────────────────────────────────────────

def discover_sitemap(base_url: str, client: httpx.Client) -> list[str]:
    """
    Try to fetch /sitemap.xml and /sitemap_index.xml for the given base URL.
    Returns a list of allowed, normalized URLs found in the sitemap(s).
    """
    from xml.etree import ElementTree as ET
    p = urlparse(base_url)
    origin = f"{p.scheme}://{p.netloc}"
    candidates = [f"{origin}/sitemap.xml", f"{origin}/sitemap_index.xml"]
    found: list[str] = []

    for sitemap_url in candidates:
        try:
            _, data = fetch(sitemap_url, client)
            if not data:
                continue
            try:
                root = ET.fromstring(data)
            except ET.ParseError:
                continue
            ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
            # sitemap index: <sitemapindex><sitemap><loc>…
            for loc in root.findall(".//sm:loc", ns):
                url = (loc.text or "").strip()
                if not url:
                    continue
                norm = normalize(url.replace("http://", "https://"))
                # recursively fetch child sitemaps
                if norm.endswith(".xml"):
                    _, sub_data = fetch(norm, client)
                    if sub_data:
                        try:
                            sub_root = ET.fromstring(sub_data)
                            for sub_loc in sub_root.findall(".//sm:loc", ns):
                                sub_url = (sub_loc.text or "").strip()
                                if sub_url:
                                    sub_norm = normalize(sub_url.replace("http://", "https://"))
                                    if is_allowed(sub_norm):
                                        found.append(sub_norm)
                        except ET.ParseError:
                            pass
                elif is_allowed(norm):
                    found.append(norm)
            if found:
                logger.info(f"  [sitemap] {sitemap_url} → {len(found)} URLs found")
                break
        except Exception as e:
            logger.debug(f"  [sitemap-error] {sitemap_url}: {e}")

    return found


# ── BFS Core ─────────────────────────────────────────────────

def bfs(seed_urls: list[str], client: httpx.Client,
        max_depth: int, max_pages: int) -> None:
    """BFS crawl. depth = shortest hop count from seed, never grows unboundedly."""
    queue: deque[tuple[str, int, str | None]] = deque()
    for url in seed_urls:
        if url not in visited:
            queue.append((url, 0, None))

    while queue and not interrupted and len(visited) < max_pages:
        url, depth, parent = queue.popleft()

        if url in visited or depth > max_depth:
            continue

        sub = subdomain_of(url)
        if pages_per_host[sub] >= MAX_PAGES_PER_HOST:
            logger.debug(f"  [host-limit] {sub}")
            continue

        # classify
        category = classify_url(url)

        # reserve slot before fetching to prevent re-entry
        visited[url] = {
            "url":         url,
            "depth":       depth,
            "parent":      parent,
            "status":      "pending",
            "type":        None,
            "fetched_at":  None,
            "category":    category,
            "saved_path":  None,
            "child_count": 0,
            "file_size":   None,
        }
        pages_per_host[sub] += 1

        url_ext = Path(urlparse(url).path.lower()).suffix
        is_doc_url = url_ext in DOCUMENT_EXTENSIONS
        type_label = "📄" if is_doc_url else "🌐"
        logger.info(f"[{len(visited):>4}] d={depth} {type_label} [{category:<22}] {url}")

        time.sleep(_delay)

        content_type, data = fetch(url, client)
        if data is None:
            visited[url]["status"] = "failed"
            continue

        ctype = classify_content(url, content_type)
        visited[url]["status"]     = "ok"
        visited[url]["type"]       = ctype
        visited[url]["fetched_at"] = datetime.now().isoformat()
        visited[url]["file_size"]  = len(data)

        if ctype == "html":
            path = save_html(url, data, category)
            visited[url]["saved_path"] = path
            if depth < max_depth:
                children = extract_links(url, data)
                visited[url]["child_count"] = len(children)
                for child in children:
                    if child not in visited:
                        queue.append((child, depth + 1, url))

        elif ctype == "document":
            path = save_document(url, data, category, content_type)
            visited[url]["saved_path"] = path
            logger.info(f"       ↳ 📥 Saved document ({len(data)//1024}KB) → {path}")

        else:
            visited[url]["status"] = "ignored"


# ── Save Results & Report ─────────────────────────────────────

def save_results():
    records = list(visited.values())

    with open(MAP_FILE, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)
    logger.info(f"✅ URL map saved → {MAP_FILE}  ({len(records)} records)")

    summary = build_classification_summary(records)
    with open(CLASSIFIED_FILE, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    logger.info(f"✅ Classification summary → {CLASSIFIED_FILE}")

    # statistics
    html_ok  = sum(1 for r in records if r.get("type") == "html"     and r["status"] == "ok")
    doc_ok   = sum(1 for r in records if r.get("type") == "document" and r["status"] == "ok")
    failed   = sum(1 for r in records if r["status"] == "failed")
    ignored  = sum(1 for r in records if r["status"] == "ignored")
    total_kb = sum((r.get("file_size") or 0) for r in records) // 1024

    print("\n" + "═" * 66)
    print("  NCCU Crawler Summary")
    print("═" * 66)
    print(f"  HTML pages: {html_ok:>5}  Documents: {doc_ok:>5}  "
          f"Failed: {failed:>4}  Ignored: {ignored:>4}")
    print(f"  Total downloaded: {total_kb:,} KB")
    print()
    print(f"  {'Category':<30} {'HTML':>6} {'Docs':>6}")
    print("  " + "─" * 44)

    cat_html: dict[str, int] = defaultdict(int)
    cat_doc:  dict[str, int] = defaultdict(int)
    for r in records:
        if r["status"] == "ok":
            c = r.get("category", "other")
            if r.get("type") == "html":
                cat_html[c] += 1
            elif r.get("type") == "document":
                cat_doc[c] += 1

    all_cats = sorted(set(list(cat_html) + list(cat_doc)),
                      key=lambda c: -(cat_html.get(c, 0) + cat_doc.get(c, 0)))
    for c in all_cats:
        print(f"  {c:<30} {cat_html.get(c,0):>6} {cat_doc.get(c,0):>6}")

    print("═" * 66)
    print(f"\n  HTML  → output/html/")
    print(f"  Docs  → output/docs/")
    print(f"  Map   → {MAP_FILE}")
    print(f"  Class → {CLASSIFIED_FILE}\n")


# ── Entry Point ───────────────────────────────────────────────

def main():
    global _delay, _url_prefixes

    ap = argparse.ArgumentParser(description="NCCU BFS web crawler for *.nccu.edu.tw")
    ap.add_argument("--seed",       default=START_URL,
                    help="Seed URL (default: www.nccu.edu.tw)")
    ap.add_argument("--all-seeds",  action="store_true",
                    help="Crawl all known NCCU subdomains listed in config.py")
    ap.add_argument("--max-depth",  type=int,   default=MAX_DEPTH)
    ap.add_argument("--max-pages",  type=int,   default=MAX_PAGES_TOTAL)
    ap.add_argument("--delay",      type=float, default=REQUEST_DELAY)
    ap.add_argument(
        "--url-prefix", action="append", dest="url_prefixes", default=[],
        help="Only follow URLs containing this string (repeatable)"
    )
    args = ap.parse_args()
    _delay        = args.delay
    _url_prefixes = [p.lower() for p in args.url_prefixes]

    # build seed list
    if args.all_seeds:
        seeds = [normalize(args.seed)] + [normalize(s) for s in EXTRA_SEEDS]
        # deduplicate while preserving order
        seen_seeds: set[str] = set()
        seeds = [s for s in seeds if not (s in seen_seeds or seen_seeds.add(s))]
    else:
        seeds = [normalize(args.seed)]

    logger.info("═" * 66)
    logger.info("  NCCU BFS Crawler starting")
    logger.info(f"  seeds={len(seeds)}")
    logger.info(f"  max-depth={args.max_depth}  "
                f"max-pages={args.max_pages}  delay={args.delay}s")
    if _url_prefixes:
        for pfx in _url_prefixes:
            logger.info(f"  url-prefix filter: {pfx}")
    logger.info("═" * 66)

    with make_client() as client:
        try:
            # collect all initial URLs (sitemap + seeds) and pass to BFS at once
            seed_urls: list[str] = []
            seen_seed_set: set[str] = set()

            for i, seed in enumerate(seeds, 1):
                logger.info(f"── Seed [{i}/{len(seeds)}] {seed}")
                sitemap_urls = discover_sitemap(seed, client)
                for u in sitemap_urls:
                    if u not in seen_seed_set:
                        seed_urls.append(u)
                        seen_seed_set.add(u)
                if seed not in seen_seed_set:
                    seed_urls.append(seed)
                    seen_seed_set.add(seed)

            bfs(seed_urls, client, args.max_depth, args.max_pages)

        except Exception as e:
            logger.error(f"❌ Unexpected error: {e}", exc_info=True)
        finally:
            save_results()


if __name__ == "__main__":
    main()
