# NCCU-Crawler

A BFS-based web crawler for National Chengchi University (NCCU) that systematically crawls `*.nccu.edu.tw`, classifies pages by academic unit, and downloads HTML pages and documents (PDF, Office formats, etc.).

## Features

- **BFS traversal** — depth reflects true distance from the seed URL, ensuring shallow/important pages are crawled first
- **URL deduplication** — normalized URLs (decoded paths, stripped redundant query params) prevent duplicate fetches
- **Per-subdomain classification** — 90+ subdomain-to-category mappings route output into named folders
- **Document download** — PDF, DOC, XLS, PPT, etc. saved separately from HTML
- **URL prefix filtering** — optionally restrict crawl to specific path prefixes
- **Multi-seed support** — crawl all known NCCU subdomains in one run with `--all-seeds`
- **Graceful shutdown** — SIGINT/SIGTERM saves progress before exiting

## Requirements

- Python 3.10+

```bash
pip install -r requirements.txt
```

## Usage

```bash
# Crawl a single subdomain (recommended starting point)
python crawler.py --seed https://aca.nccu.edu.tw --url-prefix aca.nccu.edu.tw

# Crawl with custom depth and rate limit
python crawler.py --seed https://aca.nccu.edu.tw --max-depth 10 --delay 1.0

# Restrict to specific path prefixes (can repeat --url-prefix)
python crawler.py \
  --seed "https://aca.nccu.edu.tw/zh/關於本處/註冊組" \
  --url-prefix "aca.nccu.edu.tw/zh/關於本處/註冊組" \
  --url-prefix "aca.nccu.edu.tw/zh/最新消息/註冊組"

# Crawl all known NCCU subdomains
python crawler.py --all-seeds
```

## CLI Options

| Option | Default | Description |
|---|---|---|
| `--seed` | `https://www.nccu.edu.tw` | Starting URL |
| `--all-seeds` | off | Crawl all subdomains listed in `config.py` |
| `--url-prefix` | (none) | Only follow URLs containing this string (repeatable) |
| `--max-depth` | 999 | Maximum BFS depth |
| `--max-pages` | 500000 | Maximum total pages to crawl |
| `--delay` | 0.5s | Seconds to wait between requests |

## Output Structure

```
output/
├── html/
│   └── <category>/          # e.g. admin_academic, dept_cs, library
│       └── <url-stem>__<md5>.html
├── docs/
│   └── <category>/
│       └── <url-stem>__<md5>.<ext>
├── map.json                 # All URL records with metadata
├── classified.json          # Page counts grouped by category
├── extracted_texts.jsonl    # Clean text per page (produced by preprocess_all.py)
└── crawler.log              # Full execution log
```

### map.json Record Format

```json
{
  "url": "https://aca.nccu.edu.tw/zh/關於本處/註冊組",
  "depth": 2,
  "parent": "https://aca.nccu.edu.tw/",
  "status": "ok",
  "type": "html",
  "category": "admin_academic",
  "saved_path": "output/html/admin_academic/...",
  "file_size": 45231,
  "fetched_at": "2026-03-22T20:45:12",
  "child_count": 38
}
```

## Post-Crawl Text Extraction

Once the crawler has finished, run `preprocess_all.py` to extract clean text from all saved HTML and PDF files into a single JSONL file suitable for passing to an LLM or RAG pipeline.

**Prerequisite:** `output/map.json` must exist (produced by the crawler).

```bash
python preprocess_all.py           # extract all files
python preprocess_all.py --test    # quick test: process first 20 records only
```

Output: `output/extracted_texts.jsonl` — one JSON record per page:

```json
{
  "url":         "https://aca.nccu.edu.tw/zh/...",
  "title":       "last-path-segment",
  "source_type": "html",
  "category":    "admin_academic",
  "text":        "clean extracted text..."
}
```

`source_type` is either `html` or `pdf`. Records with no extractable text or a non-OK crawl status are skipped.

> This project is the crawler component of the NCCU Academic Affairs RAG system. See `RAG_README.md` for the full pipeline (chunking, embedding, Qdrant indexing, and LLM answer generation).

## Architecture

| Module | Role |
|---|---|
| `crawler.py` | BFS orchestration, CLI entry point, signal handling |
| `config.py` | All tunables: limits, timeouts, subdomain→category mapping table |
| `classifier.py` | Maps subdomain strings to category names |
| `downloader.py` | HTTP fetching (httpx), content-type detection, file saving |

## Configuration

Key settings in `config.py`:

| Setting | Default | Description |
|---|---|---|
| `MAX_DEPTH` | 999 | BFS depth cap (deduplication prevents infinite loops) |
| `MAX_PAGES_TOTAL` | 500000 | Global page limit |
| `MAX_PAGES_PER_HOST` | 10000 | Per-subdomain limit |
| `REQUEST_DELAY` | 0.5s | Delay between requests |
| `REQUEST_TIMEOUT` | 15s | HTTP timeout |
| `MAX_DOC_BYTES` | 200 MB | Maximum document file size |

To add a new subdomain category, add an entry to `SUBDOMAIN_CATEGORIES` in `config.py`.

## Sample Crawl Results

Crawling `aca.nccu.edu.tw` (NCCU Office of Academic Affairs):

| Metric | Value |
|---|---|
| HTML pages | 2,188 |
| Documents (PDF/DOC/etc.) | 4,110 |
| Total size | ~1.25 GB |
| Max BFS depth reached | 16 |
| Runtime | ~80 minutes |

> The crawler supports all `*.nccu.edu.tw` subdomains. Currently only `aca.nccu.edu.tw` (Office of Academic Affairs) has been fully crawled and verified.
