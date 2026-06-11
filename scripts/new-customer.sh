#!/usr/bin/env bash
# Scaffold a new paying customer (Option C — one Render worker each).
# Usage: ./scripts/new-customer.sh customer-slug "Display Name"

set -euo pipefail

SLUG="${1:-}"
DISPLAY_NAME="${2:-$SLUG}"
REPO="${RENDER_REPO:-https://github.com/okwujiaku/scraper-stevo}"
ROOT_DIR="bot"

if [[ -z "$SLUG" ]]; then
  echo "Usage: ./scripts/new-customer.sh <customer-slug> [Display Name]"
  echo "Example: ./scripts/new-customer.sh stevo Stevo"
  exit 1
fi

SERVICE_NAME="scraper-${SLUG}"

echo "=== New customer: ${DISPLAY_NAME} (${SERVICE_NAME}) ==="
echo ""
echo "Render Background Worker:"
echo "  Name:           ${SERVICE_NAME}"
echo "  Root Directory: ${ROOT_DIR}"
echo "  Build:          pip install -r requirements.txt"
echo "  Start:          python bot.py"
echo "  Repo:           ${REPO}"
echo ""
echo "Environment (required):"
echo "  USER_TOKEN=         customer's Discord USER token (not a bot token)"
echo "  CHAT_ID=            customer's private group chat ID for alerts"
echo "  PYTHON_VERSION=3.11.9"
echo ""
echo "Discord setup (required for captures):"
echo "  1. Customer account must JOIN every server they want monitored."
echo "  2. Account must READ the channel where the log/welcome bot posts joins."
echo "  3. Do NOT run two workers with the same token at once."
echo ""

if command -v render >/dev/null 2>&1; then
  echo "  render env set USER_TOKEN --service ${SERVICE_NAME}"
  echo "  render env set CHAT_ID --service ${SERVICE_NAME}"
else
  echo "Add env vars in Render Dashboard → Environment → Deploy."
fi
