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
        "url": "https://developers.openai.com/api/docs/changelog",
        "link_filter": None,
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
        "url": "https://ai.google.dev/gemini-api/docs/changelog",
        "link_filter": None,
        "max_items": 15,
    },
    {
        "name": "Meta AI",
        "url": "https://ai.meta.com/blog/",
        "link_filter": "/blog/",
        "max_items": 15,
    },
    {
        "name": "Microsoft Azure AI",
        "url": "https://learn.microsoft.com/en-us/azure/ai-services/openai/whats-new",
        "link_filter": None,
        "max_items": 20,
    },
    {
        "name": "Mistral AI",
        "url": "https://docs.mistral.ai/getting-started/changelog/",
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
        "url": "https://docs.aws.amazon.com/bedrock/latest/userguide/doc-history.html",
        "link_filter": None,
        "max_items": 20,
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
