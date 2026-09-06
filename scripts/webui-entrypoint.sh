#!/bin/bash
# Install the local-STT hook into the WebUI venv once it exists, then run
# the official image entrypoint. Do not bind-mount into /app/venv — that
# makes uv refuse to create the environment.
set -euo pipefail

inject_stt_hook() {
  local dest
  local i
  for i in $(seq 1 180); do
    for dest in \
      /app/venv/lib/python3.12/site-packages \
      /apptoo/venv/lib/python3.12/site-packages
    do
      if [[ -d "$dest" ]]; then
        cp -f /hooks/hermes_webui_stt.py "$dest/hermes_webui_stt.py"
        printf 'import hermes_webui_stt\n' >"$dest/hermes_webui_stt.pth"
        return 0
      fi
    done
    sleep 1
  done
  echo "hermes-webui: timed out waiting for venv to install STT hook" >&2
}

inject_stt_hook &
exec /hermeswebui_init.bash
