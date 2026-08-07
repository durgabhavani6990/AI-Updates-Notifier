#!/usr/bin/env bash
# Entry point for Render's Cron Job. Render's build environment isn't
# guaranteed to keep a working .git checkout or to persist filesystem
# changes between scheduled runs, so this script is self-contained: it
# clones a fresh copy of the repo on every run, runs the notifier, then
# commits+pushes the updated state.json back -- the same "commit updated
# state" step the old GitHub Actions workflow used to do.
set -euo pipefail

: "${GITHUB_TOKEN:?GITHUB_TOKEN env var is required (a GitHub PAT with Contents: read/write on this repo)}"
: "${GITHUB_REPO:?GITHUB_REPO env var is required, e.g. durgabhavani6990/AI-Updates-Notifier}"

WORKDIR="$(mktemp -d)"
trap 'rm -rf "$WORKDIR"' EXIT

git clone --depth 1 "https://x-access-token:${GITHUB_TOKEN}@github.com/${GITHUB_REPO}.git" "$WORKDIR"
cd "$WORKDIR"

pip install --quiet -r requirements.txt

python main.py

git config user.name "render-cron-bot"
git config user.email "actions@github.com"
git add state.json
if ! git diff --cached --quiet; then
  git commit -m "Update seen-updates state [skip ci]"
  git push origin main
else
  echo "state.json unchanged, nothing to push"
fi
