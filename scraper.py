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
from datetime import datetime
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; AIUpdatesBot/1.0; +https://github.com/)"
}

# Requires an explicit year -- a bare "Jun 24" next to an entry is ambiguous
# (could be a group heading for a different year) and not worth guessing at.
DATE_RE = re.compile(
    r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|"
    r"Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
    r"\s+\d{1,2},?\s+\d{4}"
)


def clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def _nearby_date(parent) -> str | None:
    """
    Best-effort: only returns a date when the entry's own containing element
    (the same one used for its snippet) has an unambiguous "Month DD, YYYY"
    in it. Many provider pages put the date in a separate group heading we
    can't reliably associate with a specific entry -- those just get None
    rather than a guessed date.
    """
    if parent is None:
        return None
    m = DATE_RE.search(parent.get_text(separator=" "))
    return m.group(0) if m else None


def _fetch_article_date(url: str) -> str | None:
    """
    Best-effort: for pages that don't expose a date on the listing itself
    (e.g. Google's blog), visit the entry's own page and check the standard
    article:published_time meta tag, then a <time datetime> attribute, then
    fall back to a visible "Month DD, YYYY" near the top of the article.
    """
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
    except requests.RequestException:
        return None

    soup = BeautifulSoup(resp.text, "html.parser")

    meta = soup.find("meta", attrs={"property": "article:published_time"})
    if meta and meta.get("content"):
        try:
            return datetime.strptime(meta["content"][:10], "%Y-%m-%d").strftime("%B %d, %Y")
        except ValueError:
            pass

    time_tag = soup.find("time", attrs={"datetime": True})
    if time_tag:
        try:
            return datetime.strptime(time_tag["datetime"][:10], "%Y-%m-%d").strftime("%B %d, %Y")
        except ValueError:
            pass

    m = DATE_RE.search(soup.get_text(separator=" ")[:3000])
    return m.group(0) if m else None


def _root_domain(url: str) -> str:
    """"openai.com" from "developers.openai.com", "anthropic.com" from "www.anthropic.com"."""
    netloc = urlparse(url).netloc.lower().split(":")[0]
    parts = netloc.split(".")
    return ".".join(parts[-2:]) if len(parts) >= 2 else netloc


def fetch_entries(provider: dict) -> list[dict]:
    """
    Returns a list of dicts: {"url": str, "title": str, "snippet": str, "date": str | None}
    ordered as they appear on the page (newest first, per site convention).
    "date" is the entry's own "Month DD, YYYY" if we could find one
    unambiguously tied to it, else None -- not every provider page exposes one.
    If provider["fetch_article_dates"] is true, entries with no date found on
    the listing page get a second request to their own page to look for one
    (for sites like Google's blog that only show dates on the article itself).
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

        title = clean_text(a.get_text(separator=" "))
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

        snippet = clean_text(parent.get_text(separator=" ")) if parent is not None else ""
        date = _nearby_date(parent)
        if not snippet or snippet == title:
            # Table-row changelogs (e.g. AWS doc-history pages) put the link
            # text, description, and date in separate cells -- if the link's
            # own cell has no extra text, pull the whole row instead.
            row = a.find_parent("tr")
            if row is not None:
                row_text = clean_text(row.get_text(separator=" "))
                if row_text:
                    snippet = row_text
                    date = date or _nearby_date(row)
        if not snippet:
            snippet = title

        if date is None and provider.get("fetch_article_dates"):
            date = _fetch_article_date(href)

        seen_urls.add(href)
        entries.append({"url": href, "title": title, "snippet": snippet[:600], "date": date})

        if len(entries) >= max_items:
            break

    return entries
