# DEPLOY.md — Automated Deployment

This automates everything that *can* be automated from your machine: creating
the GitHub repo, pushing the code, and setting all the secrets. You still have
to manually get the Gmail app password, Meta WhatsApp credentials, and
(optional) Gemini key first — those live on other companies' websites and
need your login, so no script can fetch them for you. Once you have them, the
script below does the rest in one shot.

---

## Prerequisites (one-time, ~20-30 min — Meta setup is the longest part)

Get these values ready before running the script:

1. **Gmail app password**
   - Turn on 2-Step Verification: https://myaccount.google.com/security
   - Create an app password: https://myaccount.google.com/apppasswords
   - You need: `GMAIL_ADDRESS`, `GMAIL_APP_PASSWORD`

2. **Recipient emails** — `RECIPIENT_EMAILS`, comma-separated list (1 to 20+ people, e.g. `a@x.com,b@x.com`)

3. **Meta WhatsApp Cloud API** (see README.md section 3 for full detail)
   - Create app at https://developers.facebook.com/apps → add WhatsApp product
   - Note the **Phone Number ID** → `META_WA_PHONE_NUMBER_ID`
   - Create a System User with `whatsapp_business_messaging` permission,
     generate a permanent token → `META_WA_ACCESS_TOKEN`
   - Create + submit a message template (body: `Your daily AI provider updates:\n\n{{1}}`,
     category Utility) → `META_WA_TEMPLATE_NAME`, `META_WA_TEMPLATE_LANG` (e.g. `en`)
   - Add/verify your recipients so the test number can message them →
     `RECIPIENT_WHATSAPP_NUMBERS`, comma-separated, digits + country code only
     (e.g. `919876543210,447700900123`)

4. **Gemini API key** *(optional, free, for nicer 2-3 line summaries)*
   - https://aistudio.google.com/apikey
   - `GEMINI_API_KEY`

5. **GitHub CLI installed and logged in**
   - Install: https://cli.github.com
   - Run once: `gh auth login`

---

## One-shot deployment script

Save this as `deploy.sh` inside the unzipped `ai-updates-notifier` folder, then run `bash deploy.sh`.

```bash
#!/usr/bin/env bash
set -euo pipefail

echo "=== AI Updates Notifier — automated deployment ==="

# --- 1. Repo details ---
read -rp "GitHub username or org: " GH_OWNER
read -rp "New repo name [ai-updates-notifier]: " REPO_NAME
REPO_NAME="${REPO_NAME:-ai-updates-notifier}"

read -rp "Make repo private? [Y/n]: " PRIVATE_CHOICE
VISIBILITY="--private"
if [[ "${PRIVATE_CHOICE:-Y}" =~ ^[Nn]$ ]]; then
  VISIBILITY="--public"
fi

# --- 2. Collect secrets ---
echo
echo "--- Email (Gmail) ---"
read -rp "GMAIL_ADDRESS: " GMAIL_ADDRESS
read -rsp "GMAIL_APP_PASSWORD (hidden input): " GMAIL_APP_PASSWORD; echo
read -rp "RECIPIENT_EMAILS (comma-separated, e.g. a@x.com,b@x.com): " RECIPIENT_EMAILS

echo
echo "--- WhatsApp (Meta Cloud API) ---"
read -rp "META_WA_PHONE_NUMBER_ID: " META_WA_PHONE_NUMBER_ID
read -rsp "META_WA_ACCESS_TOKEN (hidden input): " META_WA_ACCESS_TOKEN; echo
read -rp "META_WA_TEMPLATE_NAME: " META_WA_TEMPLATE_NAME
read -rp "META_WA_TEMPLATE_LANG [en]: " META_WA_TEMPLATE_LANG
META_WA_TEMPLATE_LANG="${META_WA_TEMPLATE_LANG:-en}"
read -rp "RECIPIENT_WHATSAPP_NUMBERS (comma-separated, digits + country code, e.g. 919876543210,447700900123): " RECIPIENT_WHATSAPP_NUMBERS

echo
echo "--- Optional: Gemini API key for nicer free summaries (leave blank to skip) ---"
read -rsp "GEMINI_API_KEY: " GEMINI_API_KEY; echo

# --- 3. Create + push repo ---
echo
echo "Creating repo ${GH_OWNER}/${REPO_NAME}..."
git init -q
git add .
git commit -q -m "Initial commit" || true
git branch -M main

gh repo create "${GH_OWNER}/${REPO_NAME}" ${VISIBILITY} --source=. --remote=origin --push

# --- 4. Set secrets ---
echo "Setting GitHub Actions secrets..."
gh secret set GMAIL_ADDRESS -b"${GMAIL_ADDRESS}" -R "${GH_OWNER}/${REPO_NAME}"
gh secret set GMAIL_APP_PASSWORD -b"${GMAIL_APP_PASSWORD}" -R "${GH_OWNER}/${REPO_NAME}"
gh secret set RECIPIENT_EMAILS -b"${RECIPIENT_EMAILS}" -R "${GH_OWNER}/${REPO_NAME}"
gh secret set META_WA_PHONE_NUMBER_ID -b"${META_WA_PHONE_NUMBER_ID}" -R "${GH_OWNER}/${REPO_NAME}"
gh secret set META_WA_ACCESS_TOKEN -b"${META_WA_ACCESS_TOKEN}" -R "${GH_OWNER}/${REPO_NAME}"
gh secret set META_WA_TEMPLATE_NAME -b"${META_WA_TEMPLATE_NAME}" -R "${GH_OWNER}/${REPO_NAME}"
gh secret set META_WA_TEMPLATE_LANG -b"${META_WA_TEMPLATE_LANG}" -R "${GH_OWNER}/${REPO_NAME}"
gh secret set RECIPIENT_WHATSAPP_NUMBERS -b"${RECIPIENT_WHATSAPP_NUMBERS}" -R "${GH_OWNER}/${REPO_NAME}"

if [[ -n "${GEMINI_API_KEY}" ]]; then
  gh secret set GEMINI_API_KEY -b"${GEMINI_API_KEY}" -R "${GH_OWNER}/${REPO_NAME}"
fi

echo
echo "✅ Repo created, code pushed, secrets set."

# --- 5. Trigger a test run ---
read -rp "Trigger a test run right now? [Y/n]: " RUN_NOW
if [[ ! "${RUN_NOW:-Y}" =~ ^[Nn]$ ]]; then
  gh workflow run "Daily AI Updates Notifier" -R "${GH_OWNER}/${REPO_NAME}"
  echo "Triggered. Watch it here:"
  echo "  https://github.com/${GH_OWNER}/${REPO_NAME}/actions"
fi

echo
echo "Done. The workflow will now also run automatically every day at 11:00 PM IST."
```

### Run it

```bash
cd ai-updates-notifier
bash deploy.sh
```

You'll be prompted for each value once; nothing is stored on disk except inside your new private GitHub repo's encrypted secrets store.

---

## What this script does NOT automate

- **Getting the credentials themselves** (Gmail app password, Meta phone number ID/access token, Gemini key) — these require logging into each provider's dashboard yourself, since they're tied to your accounts.
- **Meta's template approval** — the first time you submit a WhatsApp message template, Meta reviews it (usually minutes to ~1 day). No script can skip that review.
- **Adding/verifying WhatsApp recipients** on a test number — this is a manual step in Meta's WhatsApp Manager the first time you add each person, unless you've completed Meta's number verification to lift that cap (see README.md).

---

## Re-running / updating later

If you change `providers.py` or any code and want to redeploy:

```bash
git add .
git commit -m "Update config"
git push
```

To rotate a secret (e.g. new Meta access token):

```bash
gh secret set META_WA_ACCESS_TOKEN -b"new-value-here" -R <owner>/<repo>
```

To change the schedule, edit the cron field in your Render Cron Job's
settings (see below) — the daily run no longer happens through GitHub
Actions.

---

## Daily scheduling: Render Cron Job (not GitHub Actions)

GitHub's shared Actions runners repeatedly failed to pick up this job at its
scheduled time ("job was not acquired by Runner ... after multiple
attempts"), so the actual daily trigger now lives on
[Render](https://render.com) instead. The GitHub Actions workflow
(`.github/workflows/daily-notify.yml`) still exists for manual runs from the
Actions tab, but its `schedule:` trigger has been removed so it can't
double-fire alongside Render.

`scripts/render_run.sh` is the entry point Render calls. Since Render Cron
Jobs don't guarantee the filesystem persists between runs, the script is
self-contained: on every run it clones a fresh copy of this repo with a
GitHub token, runs `main.py`, then commits and pushes the updated
`state.json` back — the same "commit updated state" step the old GitHub
Actions job used to do.

### One-time setup

1. **Generate a GitHub Personal Access Token** the script can use to push
   `state.json` back to this repo:
   - GitHub → Settings → Developer settings → Fine-grained tokens → Generate new token
   - Repository access: only this repo (`AI-Updates-Notifier`)
   - Permissions: **Contents: Read and write**
   - Copy the token — you won't be able to see it again.

2. **Create a Render account** at [render.com](https://render.com) (a GitHub
   login works fine) and connect it to this repository.

3. **New → Cron Job**, pointing at this repo, with:
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `bash scripts/render_run.sh`
   - **Schedule:** `30 17 * * *` (UTC — same as before: 17:30 UTC = 11:00 PM IST)

4. **Add environment variables** in the Cron Job's settings — copy the same
   values you originally set as GitHub Actions secrets (GitHub won't show you
   the old values back, so pull them from wherever you first saved them:
   password manager, Meta/Gemini dashboards, etc.):
   - `GMAIL_ADDRESS`
   - `GMAIL_APP_PASSWORD`
   - `RECIPIENT_EMAILS`
   - `META_WA_PHONE_NUMBER_ID`
   - `META_WA_ACCESS_TOKEN`
   - `META_WA_TEMPLATE_NAME`
   - `META_WA_TEMPLATE_LANG`
   - `RECIPIENT_WHATSAPP_NUMBERS`
   - `GEMINI_API_KEY`
   - `GITHUB_TOKEN` — the token from step 1
   - `GITHUB_REPO` — `<your-username>/AI-Updates-Notifier`

5. Trigger a manual run from Render's dashboard once to confirm it emails
   you and pushes a `state.json` commit, same as testing the GitHub Actions
   workflow used to work.

Render bills Cron Jobs by the second of actual run time, with a $1/month
minimum per cron service — there's no free tier for this service type, but a
job that runs a minute or two once a day will sit right around that floor.
