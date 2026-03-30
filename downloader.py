"""
downloader.py — fetch HTML and documents, classify by content type, save to disk
"""
import os
import re
import time
import hashlib
import logging
import mimetypes
import httpx
from pathlib import Path
from urllib.parse import urlparse
from config import (
    HTML_DIR, DOCS_DIR, REQUEST_TIMEOUT,
    DOCUMENT_EXTENSIONS, IGNORED_EXTENSIONS, MAX_DOC_BYTES,
)

logger = logging.getLogger("nccu_crawler")
MAX_RETRIES   = 2

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; NCCU-Edu-Crawler/1.0; "
        "+https://www.nccu.edu.tw) Academic research bot"
    ),
    "Accept": "text/html,application/xhtml+xml,application/pdf,"
              "application/msword,*/*;q=0.8",
    "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
}

# MIME type → file extension mapping
MIME_TO_EXT = {
    "application/pdf":                                          ".pdf",
    "application/msword":                                       ".doc",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
    "application/vnd.ms-excel":                                 ".xls",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ".xlsx",
    "application/vnd.ms-powerpoint":                            ".ppt",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": ".pptx",
    "application/zip":                                          ".zip",
    "text/plain":                                               ".txt",
    "text/csv":                                                 ".csv",
    "text/html":                                                ".html",
    "application/xhtml+xml":                                    ".html",
}


def _ext_from_url(url: str) -> str:
    """Guess file extension from URL path (lowercase)."""
    path = urlparse(url).path.lower()
    return Path(path).suffix  # e.g. ".pdf"


def _ext_from_mime(content_type: str) -> str:
    """Guess file extension from Content-Type header."""
    mime = content_type.split(";")[0].strip().lower()
    return MIME_TO_EXT.get(mime, "")


def classify_content(url: str, content_type: str) -> str:
    """
    Returns 'html' | 'document' | 'ignore'
    """
    url_ext  = _ext_from_url(url)
    mime_ext = _ext_from_mime(content_type)
    ext      = url_ext or mime_ext   # URL extension takes priority over MIME

    if ext in DOCUMENT_EXTENSIONS:
        return "document"
    if ext in IGNORED_EXTENSIONS:
        return "ignore"
    # no clear extension — check MIME
    if "html" in content_type or "xhtml" in content_type:
        return "html"
    if mime_ext in DOCUMENT_EXTENSIONS:
        return "document"
    if mime_ext in IGNORED_EXTENSIONS or mime_ext in ("", ".json", ".xml"):
        return "ignore"
    return "html"   # default: treat as HTML


def fetch(url: str, client: httpx.Client) -> tuple[str, bytes | None]:
    """
    GET the given URL.
    Returns (content_type, body_bytes) on success.
    Returns ('', None) on failure.
    """
    for attempt in range(MAX_RETRIES + 1):
        try:
            resp = client.get(url, timeout=REQUEST_TIMEOUT, follow_redirects=True)
            if resp.status_code == 200:
                ct = resp.headers.get("content-type", "")
                return ct, resp.content
            elif resp.status_code in (400, 401, 403, 404, 410):
                logger.warning(f"  [http-{resp.status_code}] {url}")
                return "", None
        except (httpx.TimeoutException, httpx.ConnectError,
                httpx.ReadError, httpx.RemoteProtocolError):
            if attempt < MAX_RETRIES:
                time.sleep(1.5 * (attempt + 1))
        except httpx.ProxyError:
            logger.warning(f"  [proxy-blocked] {url}")
            return "", None
        except Exception as e:
            logger.debug(f"  [fetch-error] {url}: {e}")
            return "", None
    return "", None


def url_to_stem(url: str) -> str:
    """Convert a URL to a safe, human-readable base filename (no extension)."""
    p = urlparse(url)
    readable = re.sub(r"[^\w\-.]", "_", (p.netloc + p.path).strip("/"))[:80]
    h = hashlib.md5(url.encode()).hexdigest()[:8]
    return f"{readable}__{h}"


def save_html(url: str, html_bytes: bytes, category: str) -> str:
    """Save HTML to output/html/<category>/."""
    dest = os.path.join(HTML_DIR, category)
    os.makedirs(dest, exist_ok=True)
    fname = url_to_stem(url) + ".html"
    path = os.path.join(dest, fname)
    with open(path, "wb") as f:
        f.write(html_bytes)
    return path


def save_document(url: str, data: bytes, category: str, content_type: str) -> str:
    """
    Save a document to output/docs/<category>/.
    File extension is determined from URL path or MIME type.
    """
    if len(data) > MAX_DOC_BYTES:
        logger.warning(f"  [doc-too-large] {url}  ({len(data)//1024}KB > 50MB, skipped)")
        return ""

    # determine extension
    ext = _ext_from_url(url) or _ext_from_mime(content_type) or ".bin"
    dest = os.path.join(DOCS_DIR, category)
    os.makedirs(dest, exist_ok=True)
    fname = url_to_stem(url) + ext
    path = os.path.join(dest, fname)
    with open(path, "wb") as f:
        f.write(data)
    return path


def make_client() -> httpx.Client:
    return httpx.Client(headers=HEADERS, verify=False, max_redirects=5)
