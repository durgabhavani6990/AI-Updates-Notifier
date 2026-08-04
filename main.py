import json
import os
import sys
from datetime import datetime

# Loads variables from a local .env file if one exists (for testing on your
# own machine). Does nothing on GitHub Actions -- there's no .env file there,
# so this is a safe no-op in production; real secrets come from Actions
# secrets via the workflow's `env:` block instead.
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from providers import PROVIDERS
from scraper import fetch_entries
from notifier import (
    summarize,
    build_email_html,
    build_whatsapp_text,
    send_email,
    send_whatsapp,
)

STATE_PATH = os.path.join(os.path.dirname(__file__), "state.json")
MAX_SEEN_PER_PROVIDER = 200  # cap so state.json doesn't grow forever


def load_state() -> dict:
    if os.path.exists(STATE_PATH):
        with open(STATE_PATH, "r") as f:
            return json.load(f)
    return {}


def save_state(state: dict):
    with open(STATE_PATH, "w") as f:
        json.dump(state, f, indent=2)


def main():
    state = load_state()
    digest = {}
    errors = []

    for provider in PROVIDERS:
        name = provider["name"]
        seen = set(state.get(name, []))

        try:
            entries = fetch_entries(provider)
        except Exception as e:
            errors.append(f"{name}: failed to fetch ({e})")
            continue

        new_entries = [e for e in entries if e["url"] not in seen]

        included = []
        for e in new_entries:
            description = summarize(name, e["title"], e["snippet"])
            if description is None:
                continue  # general company news, not a product update -- skip
            included.append({
                "url": e["url"],
                "title": e["title"],
                "description": description,
            })
        if included:
            digest[name] = included

        # Update seen set with everything currently on the page (newest first)
        all_urls_today = [e["url"] for e in entries]
        merged = list(dict.fromkeys(all_urls_today + list(seen)))[:MAX_SEEN_PER_PROVIDER]
        state[name] = merged

    save_state(state)

    today_str = datetime.now().strftime("%d %b %Y")
    subject = f"AI Provider Updates - {today_str}"

    email_html = build_email_html(digest)
    whatsapp_text = build_whatsapp_text(digest)

    if errors:
        error_note = "\n\n---\nCouldn't check: " + "; ".join(errors)
        email_html += "<p style='color:#999'>" + error_note.replace("\n", "<br>") + "</p>"
        whatsapp_text += "\n\n(Note: " + "; ".join(errors) + ")"

    send_email(subject, email_html)
    send_whatsapp(whatsapp_text)

    print(f"Done. {sum(len(v) for v in digest.values())} new update(s) across {len(digest)} provider(s).")
    if errors:
        print("Errors:", errors, file=sys.stderr)


if __name__ == "__main__":
    main()
