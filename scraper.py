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
import xml.etree.ElementTree as ET
from datetime import datetime
from email.utils import parsedate_to_datetime
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

# Some providers (e.g. DeepSeek) date entries as plain "2026/04/24" instead
# of a month name -- normalized to "Month DD, YYYY" when matched so it's
# still usable by notifier.py's date parsing.
SLASH_DATE_RE = re.compile(r"\b(\d{4})/(\d{1,2})/(\d{1,2})\b")


def clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def _extract_date(text: str) -> str | None:
    m = DATE_RE.search(text)
    if m:
        return m.group(0)
    m = SLASH_DATE_RE.search(text)
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3))).strftime("%B %d, %Y")
        except ValueError:
            return None
    return None


def _nearby_date(parent) -> str | None:
    """
    Best-effort: only returns a date when the entry's own containing element
    (the same one used for its snippet) has an unambiguous date in it. Many
    provider pages put the date in a separate group heading we can't
    reliably associate with a specific entry -- those just get None rather
    than a guessed date.
    """
    if parent is None:
        return None
    return _extract_date(parent.get_text(separator=" "))


# Some changelogs (e.g. DeepSeek's newer entries) link out with generic
# connector text like "For more details, see this documentation" instead of
# a real headline -- the actual title only exists on the article page itself.
_GENERIC_TITLES = {"this documentation", "the documentation", "documentation", "here", "learn more", "read more", "click here", "featured", "blog"}


def _looks_generic(title: str) -> bool:
    return title.strip().lower() in _GENERIC_TITLES


def _fetch_article_meta(url: str) -> tuple[str | None, str | None]:
    """
    Best-effort single request to an entry's own page for whatever the
    listing didn't expose: a proper date (article:published_time meta tag,
    then a <time datetime> attribute, then a visible date near the top) and,
    when the listing's link text was just generic connector phrasing, a real
    title from the article's own <h1> or <title> tag.
    """
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
    except requests.RequestException:
        return None, None

    soup = BeautifulSoup(resp.text, "html.parser")
    # Scoped to <main>/<article>, not the whole page -- otherwise a sidebar
    # like "recent updates" can leak a different entry's date/title in.
    root = soup.find("main") or soup.find("article") or soup

    date = None
    meta = soup.find("meta", attrs={"property": "article:published_time"})
    if meta and meta.get("content"):
        try:
            date = datetime.strptime(meta["content"][:10], "%Y-%m-%d").strftime("%B %d, %Y")
        except ValueError:
            pass
    if date is None:
        time_tag = soup.find("time", attrs={"datetime": True})
        if time_tag and time_tag.get("datetime"):
            try:
                date = datetime.strptime(time_tag["datetime"][:10], "%Y-%m-%d").strftime("%B %d, %Y")
            except ValueError:
                pass
    if date is None:
        date = _extract_date(root.get_text(separator=" ")[:3000])

    title = None
    h1 = root.find("h1")
    if h1:
        title = clean_text(h1.get_text(separator=" "))
    if not title and soup.title:
        # Strip a trailing " | Site Name" / " - Site Name" suffix.
        title = re.split(r"\s+[|–-]\s+", clean_text(soup.title.get_text()))[0].strip()

    return date, title


def _fetch_rss_entries(provider: dict) -> list[dict]:
    """
    RSS-feed variant of fetch_entries, for providers whose only reliable
    dated source is a feed rather than an HTML page -- e.g. AWS's per-service
    "What's New" pages are JavaScript-rendered (unusable for a plain HTTP
    scrape) but AWS's overall "What's New" RSS feed is static XML with a
    real pubDate per item. provider["rss_filter"] keeps only items whose
    title mentions it (case-insensitive), since the feed isn't scoped to one
    service.
    """
    url = provider["url"]
    rss_filter = (provider.get("rss_filter") or "").lower()
    max_items = provider.get("max_items", 15)

    resp = requests.get(url, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    root = ET.fromstring(resp.text)

    entries = []
    for item in root.findall(".//item"):
        title = clean_text(item.findtext("title") or "")
        link = (item.findtext("link") or "").strip()
        if not title or not link:
            continue
        if rss_filter and rss_filter not in title.lower():
            continue

        description = clean_text(item.findtext("description") or "")

        date = None
        pub_date = item.findtext("pubDate")
        if pub_date:
            try:
                date = parsedate_to_datetime(pub_date).strftime("%B %d, %Y")
            except (ValueError, TypeError):
                pass

        entries.append({
            "url": link,
            "title": title,
            "snippet": (description or title)[:600],
            "date": date,
        })
        if len(entries) >= max_items:
            break

    return entries


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
    If provider["type"] == "rss", delegates to the RSS feed variant instead.
    """
    if provider.get("type") == "rss":
        return _fetch_rss_entries(provider)

    url = provider["url"]
    link_filter = provider.get("link_filter")
    exclude_filters = provider.get("exclude_filter") or []
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

        if any(x in href for x in exclude_filters):
            continue

        # A link back to the listing page itself (e.g. a "Blog home" crumb)
        # is never a real entry.
        if href.rstrip("/") == url.rstrip("/"):
            continue

        if href in seen_urls:
            continue

        title = clean_text(a.get_text(separator=" "))
        if not title or len(title) < 4:
            continue

        # Generic connector text ("Learn More", "here", ...) isn't a real
        # entry -- skip it unless fetch_article_dates can recover a real
        # title from the linked page itself.
        if _looks_generic(title) and not provider.get("fetch_article_dates"):
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

        if provider.get("fetch_article_dates") and (date is None or _looks_generic(title)):
            fetched_date, fetched_title = _fetch_article_meta(href)
            date = date or fetched_date
            if _looks_generic(title) and fetched_title:
                title = fetched_title

        seen_urls.add(href)
        entries.append({"url": href, "title": title, "snippet": snippet[:600], "date": date})

        if len(entries) >= max_items:
            break

    return entries
