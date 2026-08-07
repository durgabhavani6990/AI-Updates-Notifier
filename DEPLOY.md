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

To pick up code changes on PythonAnywhere, see "Updating the code later"
below — the daily run no longer happens through GitHub Actions.

---

## Daily scheduling: PythonAnywhere Scheduled Task (not GitHub Actions)

GitHub's shared Actions runners repeatedly failed to pick up this job at its
scheduled time ("job was not acquired by Runner ... after multiple
attempts"), so the actual daily trigger now lives on
[PythonAnywhere](https://www.pythonanywhere.com) instead. The GitHub Actions
workflow (`.github/workflows/daily-notify.yml`) still exists for manual runs
from the Actions tab, but its `schedule:` trigger has been removed so it
can't double-fire.

PythonAnywhere's **free tier restricts outbound internet access to an
allowlist of sites** — it would block scraping most of the 10 provider
domains this project needs. The paid "Hacker" plan (~$5/month) removes that
restriction and is what this setup assumes.

Unlike the earlier Render-based approach, this needs no GitHub token and no
clone/push-on-every-run workaround: PythonAnywhere gives you a real
persistent filesystem, so `state.json` just lives on disk between runs like
it would on your own machine.

### One-time setup

1. Create a PythonAnywhere account and upgrade to the **Hacker** plan
   (Account → Upgrade).

2. Open a **Bash console** from the PythonAnywhere dashboard and clone the repo:
   ```bash
   git clone https://github.com/<your-username>/AI-Updates-Notifier.git
   cd AI-Updates-Notifier
   ```

3. Create a virtualenv and install dependencies:
   ```bash
   mkvirtualenv --python=/usr/bin/python3.11 ai-updates-env
   pip install -r requirements.txt
   ```

4. Create a real `.env` file with your actual secret values (this file is
   private to your account and never gets pushed to git — pull the values
   from wherever you originally saved them, since GitHub won't show old
   Actions secret values back):
   ```bash
   cp .env.example .env
   nano .env   # fill in real values, then Ctrl+O, Enter, Ctrl+X to save
   ```

5. Test it manually once:
   ```bash
   python main.py
   ```
   Confirm you get the email + WhatsApp digest, same as testing the old
   GitHub Actions workflow used to work.

6. Go to the **Tasks** tab in the PythonAnywhere dashboard and add a new
   scheduled task:
   - **Time:** `17:30` (PythonAnywhere schedules are in UTC — 17:30 UTC = 11:00 PM IST)
   - **Command:**
     ```
     /home/<your-pythonanywhere-username>/.virtualenvs/ai-updates-env/bin/python /home/<your-pythonanywhere-username>/AI-Updates-Notifier/main.py
     ```

7. So future `git pull`s don't conflict with the locally-changing
   `state.json` (see below), tell git to leave your local copy alone:
   ```bash
   git update-index --skip-worktree state.json
   ```

That's it — no secrets to re-enter anywhere else, no push-back step, no
GitHub token.

### Updating the code later

The scheduled task only runs `main.py` — it doesn't pull new code on its
own. When you push changes to GitHub and want PythonAnywhere to pick them
up, open a Bash console and run:

```bash
cd ~/AI-Updates-Notifier && git pull
```

Step 7 above (`--skip-worktree`) means this won't try to overwrite your
locally-persisted `state.json` with the repo's (now-stale) committed copy.
