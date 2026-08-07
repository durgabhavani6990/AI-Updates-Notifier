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

To change the schedule, edit the time on your external cron job (see below)
— GitHub Actions' own `schedule:` trigger is intentionally not used.

---

## Daily scheduling: external trigger for workflow_dispatch (not `schedule:`)

Everything still runs on GitHub Actions, using the exact same secrets and
the exact same workflow — only the *trigger* changed.

GitHub's shared Actions runners repeatedly failed to pick up this job when
triggered by a `schedule:` cron entry ("job was not acquired by Runner ...
after multiple attempts"). GitHub explicitly gives schedule-triggered runs
lower priority in its shared runner queue than manually- or
API-triggered (`workflow_dispatch`) runs. So instead of paying for a whole
separate hosting platform, a free external cron service calls this
workflow's `workflow_dispatch` API endpoint once a day — same execution
environment, same secrets, just a different (and better-prioritized)
trigger path.

### One-time setup

1. **Generate a GitHub Personal Access Token** the external cron service will
   use to call the API:
   - GitHub → Settings → Developer settings → Fine-grained tokens → Generate new token
   - Repository access: only this repo (`AI-Updates-Notifier`)
   - Permissions: **Actions: Read and write**
   - Copy the token — you won't be able to see it again.

2. **Create a free account** at [cron-job.org](https://cron-job.org) (or any
   similar free HTTP-cron service — EasyCron and others work the same way).

3. **Create a new cron job** with:
   - **URL:** `https://api.github.com/repos/<your-username>/AI-Updates-Notifier/actions/workflows/daily-notify.yml/dispatches`
   - **Method:** `POST`
   - **Headers:**
     ```
     Authorization: Bearer <the token from step 1>
     Accept: application/vnd.github+json
     Content-Type: application/json
     ```
   - **Body:** `{"ref":"main"}`
   - **Schedule:** daily at `17:30` UTC (= 11:00 PM IST)

4. Use the service's "test run" / "execute now" feature once to confirm it
   returns a `204 No Content` and a new run actually starts on the
   **Actions** tab of this repo.

Nothing else changes — no new secrets, no new place your Gmail/WhatsApp/Gemini
credentials need to live, no change to how `state.json` gets committed back.
If this still proves unreliable after a couple of weeks of real use, that's
the point to reconsider a paid platform (Render or PythonAnywhere, both
covered in git history of this file) with actual evidence instead of a
single data point.
