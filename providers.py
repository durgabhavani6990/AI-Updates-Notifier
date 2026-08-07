"""
Configuration for the AI providers we monitor.

Each provider has:
  - name: display name
  - url: official changelog / release-notes / blog page to scrape
  - link_filter: optional substring that a URL must contain to be treated as
                 a genuine "entry" link (helps filter out nav/footer links).
                 Leave as None to accept any link found in the main content area.
  - max_items: how many of the most recent entries on the page to consider
               each run (we then diff against what we've already notified on).

NOTE: These are official documentation / changelog / blog pages as of Aug 2026.
Pages occasionally get redesigned, which can break scraping. If a provider
stops showing updates, open the URL below in a browser, confirm it still
loads a list of dated entries, and adjust link_filter / max_items as needed.
"""

PROVIDERS = [
    {
        "name": "OpenAI",
        "url": "https://openai.com/news/product-releases/",
        # Real articles live under /index/ -- everything else in the main
        # content area is category nav (Company, Research, Safety, ...).
        "link_filter": "/index/",
        "max_items": 15,
    },
    {
        "name": "Anthropic",
        "url": "https://www.anthropic.com/news",
        "link_filter": "/news/",
        "max_items": 15,
    },
    {
        "name": "Google (Gemini API)",
        "url": "https://blog.google/products/gemini/",
        # Keeps only genuine model/API announcements -- this page also lists
        # consumer Gemini-app, Pixel, and Android posts under other URL paths.
        "link_filter": "/models-and-research/gemini-models/",
        "max_items": 15,
        # This listing page doesn't show dates itself; fetch each new
        # article's own page for its article:published_time meta tag.
        "fetch_article_dates": True,
    },
    {
        "name": "Meta AI",
        "url": "https://ai.meta.com/blog/",
        "link_filter": "/blog/",
        "max_items": 15,
    },
    {
        "name": "Microsoft Azure AI",
        "url": "https://azure.microsoft.com/en-us/blog/product/azure-ai/",
        "link_filter": None,
        # The rest of the main content area is sort/filter controls and
        # content-type tag links (Thought leadership, Announcements, ...),
        # not real posts.
        "exclude_filter": ["?", "/blog/product/", "/blog/content-type/", "blogs.microsoft.com"],
        "max_items": 15,
        # Listing shows "July 2" with no year; fetch each new article's own
        # page for its article:published_time meta tag.
        "fetch_article_dates": True,
    },
    {
        "name": "Mistral AI",
        "url": "https://mistral.ai/news",
        "link_filter": None,
        "max_items": 15,
    },
    {
        "name": "xAI (Grok)",
        "url": "https://x.ai/news",
        "link_filter": "/news/",
        "max_items": 15,
    },
    {
        "name": "Amazon Bedrock",
        # AWS has no single Bedrock-only news page, and its HTML "What's New"
        # hub is JavaScript-rendered (unusable for a plain HTTP scrape) --
        # but the site-wide "What's New" RSS feed is static XML with a real
        # pubDate per item, filtered here to just the Bedrock-mentioning ones.
        "url": "https://aws.amazon.com/new/feed/",
        "type": "rss",
        "rss_filter": "bedrock",
        "max_items": 15,
    },
    {
        "name": "Cohere",
        "url": "https://docs.cohere.com/changelog",
        "link_filter": "/changelog/",
        "max_items": 15,
    },
    {
        "name": "DeepSeek",
        "url": "https://api-docs.deepseek.com/news/",
        "link_filter": None,
        "max_items": 15,
    },
]
