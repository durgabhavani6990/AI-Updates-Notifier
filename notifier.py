"""
Handles:
  1. (Optional) summarizing a scraped snippet into a clean 2-3 line description
     using the Gemini API (free tier).
  2. Sending the final digest via Gmail SMTP to one or many recipients.
  3. Sending the final digest via Meta's WhatsApp Cloud API to one or many
     recipients.
"""

import os
import re
import smtplib
import textwrap
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import requests

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash").strip()

# Signals of general company news (leadership, funding, philanthropy, policy,
# etc.) rather than an actual product update. Used as the fallback filter
# when Gemini isn't configured or a call fails -- Gemini's own judgment is
# the primary filter otherwise.
GENERAL_NEWS_SIGNALS = [
    "chief executive", "chief financial", "chief technology", "chief operating",
    "board of directors", "joins the board", "appoints", "appointment",
    "named ceo", "named cfo", "named cto", "president of", "hires ", "hiring",
    "funding round", "raises $", "valuation", "ipo", "donation", "philanthrop",
    "nonprofit", "grant program", "grants to", "research fund", "policy paper",
    "position paper", "op-ed", "testimony", "congress", "senate", "lawsuit",
    "settlement", "earnings call", "quarterly results", "economic index",
    "sponsorship",
]


def _looks_like_product_update(title: str, snippet: str) -> bool:
    text = f"{title} {snippet}".lower()
    return not any(signal in text for signal in GENERAL_NEWS_SIGNALS)


def summarize(provider_name: str, title: str, snippet: str) -> str | None:
    """
    Produces a 2-3 line description of an update, or returns None if it
    looks like general company news (leadership changes, funding, grants,
    policy essays, partnerships, etc.) rather than a genuine product update
    (new feature, model, tool, plugin, API, capability, pricing/limit
    change) -- such items should be left out of the digest entirely.

    Uses Gemini (free tier) to judge + summarize if an API key is
    configured; otherwise falls back to a keyword heuristic + naive
    truncation. Never raises -- always returns either a usable string or None.
    """
    if not GEMINI_API_KEY:
        if not _looks_like_product_update(title, snippet):
            return None
        fallback = snippet if len(snippet) > len(title) else title
        return textwrap.shorten(fallback, width=280, placeholder="...")

    prompt = (
        f"This is a scraped entry from {provider_name}'s changelog/news page.\n\n"
        f"Title: {title}\n"
        f"Raw snippet: {snippet}\n\n"
        "First, decide if this is a genuine AI PRODUCT update -- a new "
        "feature, model, tool, plugin, SDK, API, integration, capability "
        "improvement, or a pricing/rate-limit/deprecation change. If instead "
        "it's general company news -- leadership/executive changes, hiring, "
        "funding, grants, donations, philanthropy, policy essays, research "
        "papers not tied to a product release, corporate partnerships, or "
        "PR/brand pieces -- respond with exactly the single word: SKIP\n\n"
        "Otherwise, respond with a plain, factual 2-3 line description (no "
        "more than 3 short sentences, no markdown, no preamble) of what the "
        "update / feature is. If the snippet doesn't contain enough "
        "information to be sure it's a product update, respond SKIP rather "
        "than guessing."
    )

    try:
        resp = requests.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent",
            headers={"Content-Type": "application/json", "x-goog-api-key": GEMINI_API_KEY},
            json={"contents": [{"parts": [{"text": prompt}]}]},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        text = (
            data.get("candidates", [{}])[0]
            .get("content", {})
            .get("parts", [{}])[0]
            .get("text", "")
        ).strip()
        if not text:
            raise ValueError("empty Gemini response")
        if text.strip().upper().startswith("SKIP"):
            return None
        return text
    except Exception:
        if not _looks_like_product_update(title, snippet):
            return None
        return textwrap.shorten(snippet, width=280, placeholder="...")


def _split_recipients(raw: str) -> list[str]:
    return [r.strip() for r in raw.split(",") if r.strip()]


def _derive_name(email: str) -> str:
    """
    Best-effort display name from an email's local part, e.g.
    "raviteja.peetla@gmail.com" -> "Raviteja", "keshavasai2001@gmail.com"
    -> "Keshavasai". Falls back to "there" if nothing usable is left.
    """
    local = email.split("@", 1)[0]
    for sep in (".", "_", "-", "+"):
        if sep in local:
            local = local.split(sep, 1)[0]
            break
    else:
        local = re.sub(r"\d+$", "", local)
    local = local.strip()
    return local.capitalize() if local else "there"


ACCENT = "#4f46e5"
TEXT = "#1f2937"
MUTED = "#6b7280"
BORDER = "#e5e7eb"
CARD_BG = "#ffffff"
PAGE_BG = "#f3f4f6"


def build_email_html(digest: dict, errors: list[str] | None = None, recipient_name: str | None = None) -> str:
    date_str = datetime.now().strftime("%d %b %Y")
    greeting = f'<div style="font-size:15px;font-weight:700;color:{TEXT};margin-bottom:10px;">Hi {recipient_name},</div>' if recipient_name else ""

    if digest:
        sections = []
        for provider_name, items in digest.items():
            rows = []
            for i, item in enumerate(items):
                border = f"border-top:1px solid {BORDER};" if i > 0 else ""
                rows.append(
                    f'<tr><td style="padding:12px 0;{border}">'
                    f'<a href="{item["url"]}" style="color:{ACCENT};font-weight:600;'
                    f'font-size:15px;text-decoration:none;">{item["title"]}</a>'
                    f'<div style="color:{TEXT};font-size:14px;line-height:1.5;margin-top:4px;">'
                    f'{item["description"]}</div></td></tr>'
                )
            sections.append(
                f'<tr><td style="padding:0 0 16px 0;">'
                f'<div style="background:{CARD_BG};border:1px solid {BORDER};'
                f'border-radius:10px;padding:6px 20px;">'
                f'<div style="display:inline-block;background:{ACCENT};color:#ffffff;'
                f'font-size:12px;font-weight:600;padding:3px 10px;border-radius:999px;'
                f'letter-spacing:.3px;margin-top:14px;">{provider_name}</div>'
                f'<table role="presentation" width="100%" style="border-collapse:collapse;">'
                f'{"".join(rows)}</table></div></td></tr>'
            )
        body = "".join(sections)
    else:
        body = (
            f'<tr><td style="padding:8px 0 16px 0;">'
            f'<div style="background:{CARD_BG};border:1px solid {BORDER};'
            f'border-radius:10px;padding:32px;text-align:center;color:{MUTED};'
            f'font-size:15px;">No updates for today.</div></td></tr>'
        )

    error_html = ""
    if errors:
        error_html = (
            f'<tr><td style="padding:0 0 16px 0;">'
            f'<div style="color:{MUTED};font-size:12px;background:#fafafa;'
            f'border:1px dashed {BORDER};border-radius:8px;padding:10px 14px;">'
            f'Couldn\'t check: {"; ".join(errors)}</div></td></tr>'
        )

    return (
        f'<div style="background:{PAGE_BG};padding:24px 0;'
        f'font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;">'
        f'<table role="presentation" width="100%" style="max-width:600px;'
        f'margin:0 auto;border-collapse:collapse;">'
        f'<tr><td style="padding:0 20px 20px 20px;">'
        f'{greeting}'
        f'<div style="font-size:20px;font-weight:700;color:{TEXT};">AI Provider Updates</div>'
        f'<div style="font-size:13px;color:{MUTED};margin-top:2px;">{date_str}</div>'
        f'</td></tr>'
        f'<tr><td style="padding:0 20px;">'
        f'<table role="presentation" width="100%" style="border-collapse:collapse;">'
        f'{body}{error_html}</table></td></tr>'
        f'<tr><td style="padding:12px 20px 24px 20px;text-align:center;">'
        f'<div style="font-size:12px;color:{MUTED};">'
        f'Automated daily digest of official AI provider changelogs.</div>'
        f'</td></tr></table></div>'
    )


def send_email(subject: str, digest: dict, errors: list[str] | None = None):
    """
    RECIPIENT_EMAILS (preferred) or RECIPIENT_EMAIL (back-compat) can hold a
    single address or a comma-separated list, e.g.:
      "alice@example.com,bob@example.com,carol@example.com"
    Sends one individual, personally-greeted email per recipient (same SMTP
    connection, separate messages) so each person's "To" line shows their
    own address and their own name in the greeting, while never revealing
    the rest of the recipient list to anyone.
    """
    gmail_address = os.environ["GMAIL_ADDRESS"]
    gmail_app_password = os.environ["GMAIL_APP_PASSWORD"]
    raw_recipients = os.environ.get("RECIPIENT_EMAILS") or os.environ["RECIPIENT_EMAIL"]
    recipients = _split_recipients(raw_recipients)

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(gmail_address, gmail_app_password)
        for recipient in recipients:
            html_body = build_email_html(digest, errors, recipient_name=_derive_name(recipient))
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = gmail_address
            msg["To"] = recipient
            msg.attach(MIMEText(html_body, "html"))
            server.sendmail(gmail_address, [recipient], msg.as_string())


def build_whatsapp_text(digest: dict) -> str:
    if not digest:
        return "No updates for today."

    lines = ["*AI Provider Updates*", ""]
    for provider_name, items in digest.items():
        lines.append(f"*{provider_name}*")
        for item in items:
            lines.append(f'- {item["title"]}')
            lines.append(f'  {item["description"]}')
            lines.append(f'  {item["url"]}')
        lines.append("")
    return "\n".join(lines).strip()


def send_whatsapp(text: str):
    """
    Sends the digest to every number in RECIPIENT_WHATSAPP_NUMBERS via Meta's
    WhatsApp Cloud API.

    Required env vars:
      META_WA_PHONE_NUMBER_ID   - the Phone Number ID from Meta's WhatsApp
                                  Cloud API setup (not the phone number itself)
      META_WA_ACCESS_TOKEN      - a permanent access token for a System User
                                  with whatsapp_business_messaging permission
      META_WA_TEMPLATE_NAME     - name of your approved message template
                                  (see README for the template to submit)
      RECIPIENT_WHATSAPP_NUMBERS- comma-separated numbers, digits only with
                                  country code, e.g. "919876543210,447700900123"

    Optional:
      META_WA_TEMPLATE_LANG     - defaults to "en"

    Why a template: WhatsApp Cloud API requires an approved template for any
    message you send proactively (i.e. not as a reply within 24h of the user
    messaging you first) -- which is exactly what a scheduled daily digest is.
    Submit a template with a single body variable, e.g.:
        "Your daily AI provider updates:\n\n{{1}}"
    Approval usually takes minutes to ~1 day the first time.
    """
    phone_number_id = os.environ["META_WA_PHONE_NUMBER_ID"]
    access_token = os.environ["META_WA_ACCESS_TOKEN"]
    template_name = os.environ["META_WA_TEMPLATE_NAME"]
    template_lang = os.environ.get("META_WA_TEMPLATE_LANG", "en")
    recipients = _split_recipients(os.environ["RECIPIENT_WHATSAPP_NUMBERS"])

    # Meta template body params have a practical length limit; keep chunks
    # comfortably under it and send multiple template messages if needed.
    chunks = [text[i:i + 1000] for i in range(0, len(text), 1000)] or ["No updates for today."]

    url = f"https://graph.facebook.com/v20.0/{phone_number_id}/messages"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }

    for to_number in recipients:
        for chunk in chunks:
            payload = {
                "messaging_product": "whatsapp",
                "to": to_number,
                "type": "template",
                "template": {
                    "name": template_name,
                    "language": {"code": template_lang},
                    "components": [
                        {"type": "body", "parameters": [{"type": "text", "text": chunk}]}
                    ],
                },
            }
            resp = requests.post(url, headers=headers, json=payload, timeout=30)
            resp.raise_for_status()
