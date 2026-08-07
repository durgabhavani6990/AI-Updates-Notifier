# AI Provider Daily Updates Notifier

Checks the official changelog/release-notes/blog pages of 10 major AI providers
every day at **11:00 PM IST**, and emails + WhatsApps you a digest of anything
new, with each item linking straight to the source. If nothing changed that
day, you get a "No updates for today" message instead.

Providers monitored (edit `providers.py` to change this list):
OpenAI, Anthropic, Google (Gemini API), Meta AI, Microsoft Azure AI, Mistral AI,
xAI (Grok), Amazon Bedrock, Cohere, DeepSeek.

---

## How it works

- A [PythonAnywhere](https://www.pythonanywhere.com) Scheduled Task runs
  `main.py` daily (17:30 UTC = 11:00 PM IST) — see DEPLOY.md for setup. This
  moved off GitHub Actions' own `schedule:` trigger after it repeatedly
  failed to fire; the GitHub Actions workflow
  (`.github/workflows/daily-notify.yml`) still exists for manual runs from
  the Actions tab.
- `main.py` scrapes each provider's page, compares the links it finds against
  `state.json` (what it already told you about), and treats anything new as
  "today's update."
- New items get a short 2-3 line description, either written by Gemini
  (if you add a free Gemini API key) or a simple auto-shortened version of the
  scraped text (if you don't).
- It emails you via Gmail SMTP and WhatsApps you via Meta's WhatsApp Cloud
  API, then commits the updated `state.json` back to the repo so tomorrow's
  run knows what's already been sent.

---

## One-time setup (about 15–20 minutes)

### 1. Create the repo
Create a **private** GitHub repo and push these files to it (instructions at
the bottom of this file).

### 2. Gmail — for sending email
1. Turn on 2-Step Verification on the Gmail account you want to send *from*:
   https://myaccount.google.com/security
2. Create an "App Password": https://myaccount.google.com/apppasswords
   (choose app = "Mail", device = "Other", name it anything). Copy the 16-character password.
3. You'll use this Gmail address + app password as secrets below. You can send
   to any list of email addresses — they don't have to be Gmail addresses,
   and there's no extra setup to send to 10-20 people; just list them all
   (see step 5).

### 3. Meta WhatsApp Cloud API — for sending WhatsApp to 10-20 people
This takes more one-time setup than a quick sandbox trial would, but scales
cleanly to many recipients with no per-person join step and no expiry to
babysit.

1. Create a Meta developer account and app: https://developers.facebook.com/apps
   → **Create App** → choose **Business** type.
2. In the app dashboard, add the **WhatsApp** product.
3. Meta gives you a **test phone number** automatically. Note its **Phone
   Number ID** (shown in the WhatsApp → API Setup page — this is a long
   numeric ID, not the phone number itself).
4. Generate a **permanent access token**:
   - Business Settings → Users → System Users → create a system user
   - Assign it the WhatsApp app with `whatsapp_business_messaging` permission
   - Generate a token for it (choose "never expires" if offered)
5. **Create and submit a message template** (required — WhatsApp requires an
   approved template for any message you send proactively, which a scheduled
   daily digest always is):
   - WhatsApp Manager → Account Tools → Message Templates → Create Template
   - Category: **Utility**
   - Body text: `Your daily AI provider updates:\n\n{{1}}`
   - Submit for review (usually approved within minutes to ~1 day)
   - Note the exact **template name** you gave it
6. Add each recipient's WhatsApp number to your test number's allowed
   recipient list (WhatsApp → API Setup → "To" field has an "Manage phone
   number list" option) **while using the free test number** — the test
   number can only message a limited number of verified recipients. If you
   need all 10-20 people to receive it without this limitation, apply to
   have your test number (or a real business number) go through Meta's
   **display name/number verification** to lift the recipient cap — this is
   a one-time review, free of charge.

### 4. Gemini API key (optional, recommended for nicer summaries — free)
1. Go to https://aistudio.google.com/apikey and create a free API key (no
   credit card needed).
2. This uses Gemini 2.5 Flash's free tier. Skip this and the script will just
   auto-shorten the scraped text instead.

### 5. Add GitHub secrets
In your repo: **Settings → Secrets and variables → Actions → New repository secret**.
Add each of these:

| Secret name | Value |
|---|---|
| `GMAIL_ADDRESS` | the Gmail address you set the app password on |
| `GMAIL_APP_PASSWORD` | the 16-character app password |
| `RECIPIENT_EMAILS` | comma-separated list, e.g. `alice@example.com,bob@example.com,carol@example.com` (works fine for 1 person or 20) |
| `META_WA_PHONE_NUMBER_ID` | the Phone Number ID from WhatsApp → API Setup |
| `META_WA_ACCESS_TOKEN` | the permanent system-user access token |
| `META_WA_TEMPLATE_NAME` | the exact name of your approved template |
| `META_WA_TEMPLATE_LANG` | `en` (or whatever language you submitted the template in) |
| `RECIPIENT_WHATSAPP_NUMBERS` | comma-separated numbers, digits only with country code, e.g. `919876543210,447700900123,14155551234` |
| `GEMINI_API_KEY` | *(optional)* your free Gemini API key |

### 6. Test it
Go to the **Actions** tab → "Daily AI Updates Notifier" → **Run workflow** to
trigger it manually and confirm you get an email + WhatsApp message. The
first run will likely report a lot of "new" items for every provider (since
nothing has been seen yet) — that's expected; from the second run onward
you'll only get genuinely new items.

Daily scheduling itself runs on a PythonAnywhere Scheduled Task, not GitHub
Actions — see the "Daily scheduling" section in DEPLOY.md to set that up.

---

## Optional: test locally before deploying

You can run the whole thing on your own machine first, using a `.env` file
instead of GitHub secrets:

```bash
cp .env.example .env
# edit .env and fill in your real values
pip install -r requirements.txt
python main.py
```

`.env` is already in `.gitignore` so it never gets committed. GitHub Actions
doesn't read it (it uses its own Secrets store instead) — but PythonAnywhere
*does* use this same `.env` mechanism in production, just with its own
separate `.env` file living directly on your PythonAnywhere account (see
DEPLOY.md). Delete your local `.env` once you're confident the script works
and you've set up the real one on PythonAnywhere.

---

## Pushing this to GitHub

```bash
cd ai-updates-notifier
git init
git add .
git commit -m "Initial commit"
git branch -M main
git remote add origin https://github.com/<your-username>/<your-repo>.git
git push -u origin main
```

---

## Customizing

- **Change providers / URLs**: edit `providers.py`.
- **Change schedule**: edit the time on your PythonAnywhere Scheduled Task
  (uses UTC — IST is UTC+5:30).
- **Tune scraping**: if a provider's page redesigns and stops finding entries,
  open `scraper.py` — you can tighten `link_filter` per provider in
  `providers.py` to only match real article links (e.g. `/blog/2026/...`).

## Known limitations
- Scraping breaks if a site redesigns its page or requires JavaScript to
  render its content list (this project uses plain HTML fetching, not a
  headless browser). If a provider's page is JS-heavy, first run may not
  see any entries — check that provider's `link_filter` and page structure.
- Meta's WhatsApp **test number** can only message a limited, manually-added
  list of recipients. To message all 10-20 people without adding each one
  individually, go through Meta's one-time number/display-name verification
  (see step 3.6). This is a Meta requirement, not something the code can
  route around.
- Message templates must be re-submitted for approval if you ever change
  their wording — the `{{1}}` placeholder approach here means you generally
  won't need to, since only the *content* inside `{{1}}` changes daily, not
  the template itself.
- Daily scheduling runs on a PythonAnywhere Scheduled Task rather than
  GitHub Actions, after GitHub's shared runners repeatedly failed to pick up
  this job at its scheduled time ("job was not acquired by Runner ... after
  multiple attempts"). See DEPLOY.md's "Daily scheduling" section.
- PythonAnywhere's free tier restricts outbound internet access to an
  allowlist of sites, which would block scraping most of these 10 providers
  — the paid "Hacker" plan (~$5/month) is required.
