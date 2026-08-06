"""
Generic scraper for provider changelog / blog pages.

Strategy: rather than fight ten different, ever-changing HTML layouts with
brittle per-site CSS selectors, we pull every link + its nearby text from the
main content area of the page, keep the first N (assumed newest-first, which
is how virtually every changelog/blog page is ordered), and let main.py diff
that list against what we've already notified on. Anything not seen before
is "new" -> gets included in today's notification.
"""

import re
import requests
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; AIUpdatesBot/1.0; +https://github.com/)"
}


def clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def _root_domain(url: str) -> str:
    """"openai.com" from "developers.openai.com", "anthropic.com" from "www.anthropic.com"."""
    netloc = urlparse(url).netloc.lower().split(":")[0]
    parts = netloc.split(".")
    return ".".join(parts[-2:]) if len(parts) >= 2 else netloc


def fetch_entries(provider: dict) -> list[dict]:
    """
    Returns a list of dicts: {"url": str, "title": str, "snippet": str}
    ordered as they appear on the page (newest first, per site convention).
    """
    url = provider["url"]
    link_filter = provider.get("link_filter")
    max_items = provider.get("max_items", 15)
    allowed_domain = _root_domain(url)

    resp = requests.get(url, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    # Prefer <main> or <article> as the content root if present, else whole doc
    root = soup.find("main") or soup.find("article") or soup

    entries = []
    seen_urls = set()
    seen_parents = set()

    for a in root.find_all("a", href=True):
        href = a["href"]

        # Normalize relative URLs
        if href.startswith("/"):
            href = urljoin(url, href)
        if not href.startswith("http"):
            continue

        # Only trust links on the provider's own domain (e.g. developers.openai.com
        # and platform.openai.com both match "openai.com") -- filters out stray
        # third-party links like preview/staging deployments that occasionally
        # leak onto a provider's live page.
        if _root_domain(href) != allowed_domain:
            continue

        if link_filter and link_filter not in href:
            continue

        if href in seen_urls:
            continue

        title = clean_text(a.get_text())
        if not title or len(title) < 4:
            continue

        # Multiple links inside the same list item / paragraph usually mean
        # one changelog entry mentioning several things (e.g. "Usage API" and
        # "Costs API" both linked from one bullet) -- keep only the first
        # link per parent so it doesn't turn into duplicate "new" items.
        parent = a.find_parent(["li", "p", "div", "section", "article"])
        if parent is not None:
            parent_key = id(parent)
            if parent_key in seen_parents:
                continue
            seen_parents.add(parent_key)

        snippet = clean_text(parent.get_text()) if parent is not None else ""
        if not snippet:
            snippet = title

        seen_urls.add(href)
        entries.append({"url": href, "title": title, "snippet": snippet[:600]})

        if len(entries) >= max_items:
            break

    return entries
