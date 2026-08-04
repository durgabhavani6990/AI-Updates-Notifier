"""
Handles:
  1. (Optional) summarizing a scraped snippet into a clean 2-3 line description
     using the Gemini API (free tier).
  2. Sending the final digest via Gmail SMTP to one or many recipients.
  3. Sending the final digest via Meta's WhatsApp Cloud API to one or many
     recipients.
"""

import os
import smtplib
import textwrap
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import requests

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash").strip()


def summarize(provider_name: str, title: str, snippet: str) -> str:
    """
    Produces a 2-3 line description of an update. Uses Gemini (free tier) if
    an API key is configured; otherwise falls back to a naive truncation of
    the scraped snippet. Never raises -- always returns something usable.
    """
    if not GEMINI_API_KEY:
        fallback = snippet if len(snippet) > len(title) else title
        return textwrap.shorten(fallback, width=280, placeholder="...")

    prompt = (
        f"This is a scraped snippet from {provider_name}'s changelog page.\n\n"
        f"Title: {title}\n"
        f"Raw snippet: {snippet}\n\n"
        "Write a plain, factual 2-3 line description (no more than 3 short "
        "sentences, no markdown, no preamble) of what this update / feature "
        "is. If the snippet doesn't contain enough information to be sure, "
        "just clean up and shorten the title/snippet instead of guessing."
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
        return text or textwrap.shorten(snippet, width=280, placeholder="...")
    except Exception:
        return textwrap.shorten(snippet, width=280, placeholder="...")


def _split_recipients(raw: str) -> list[str]:
    return [r.strip() for r in raw.split(",") if r.strip()]


def build_email_html(digest: dict) -> str:
    if not digest:
        return "<p>No updates for today.</p>"

    parts = ["<h2>AI Provider Updates</h2>"]
    for provider_name, items in digest.items():
        parts.append(f"<h3>{provider_name}</h3><ul>")
        for item in items:
            parts.append(
                f'<li><a href="{item["url"]}">{item["title"]}</a><br>'
                f'{item["description"]}</li>'
            )
        parts.append("</ul>")
    return "\n".join(parts)


def send_email(subject: str, html_body: str):
    """
    RECIPIENT_EMAILS (preferred) or RECIPIENT_EMAIL (back-compat) can hold a
    single address or a comma-separated list, e.g.:
      "alice@example.com,bob@example.com,carol@example.com"
    All recipients are put on the "To" line (everyone can see who else got
    it). Switch to BCC-per-recipient below if you'd rather keep the list private.
    """
    gmail_address = os.environ["GMAIL_ADDRESS"]
    gmail_app_password = os.environ["GMAIL_APP_PASSWORD"]
    raw_recipients = os.environ.get("RECIPIENT_EMAILS") or os.environ["RECIPIENT_EMAIL"]
    recipients = _split_recipients(raw_recipients)

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = gmail_address
    msg["To"] = ", ".join(recipients)
    msg.attach(MIMEText(html_body, "html"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(gmail_address, gmail_app_password)
        server.sendmail(gmail_address, recipients, msg.as_string())


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
