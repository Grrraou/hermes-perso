#!/usr/bin/env bash
# Create ./data and a .env with random dashboard / API secrets.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

mkdir -p data

if [[ -f .env ]]; then
  echo "data/ is ready. .env already exists — not overwriting."
  echo "Next: make setup && make up"
  exit 0
fi

if [[ ! -f .env.example ]]; then
  echo "Missing .env.example" >&2
  exit 1
fi

uid="$(id -u)"
gid="$(id -g)"
password="$(openssl rand -base64 18 | tr -d '/+=' | head -c 24)"
session="$(openssl rand -hex 32)"
api_key="$(openssl rand -hex 32)"

umask 077
sed \
  -e "s/^HERMES_UID=.*/HERMES_UID=${uid}/" \
  -e "s/^HERMES_GID=.*/HERMES_GID=${gid}/" \
  -e "s/^HERMES_DASHBOARD_BASIC_AUTH_PASSWORD=.*/HERMES_DASHBOARD_BASIC_AUTH_PASSWORD=${password}/" \
  -e "s/^HERMES_DASHBOARD_BASIC_AUTH_SECRET=.*/HERMES_DASHBOARD_BASIC_AUTH_SECRET=${session}/" \
  -e "s/^API_SERVER_KEY=.*/API_SERVER_KEY=${api_key}/" \
  .env.example > .env

echo "Wrote .env (mode 600) and created data/"
echo
echo "Dashboard user:     hermes"
echo "Dashboard password: ${password}"
echo "API key:            ${api_key}"
echo
echo "Save those values. Then run:"
echo "  make setup"
echo "  make up"
