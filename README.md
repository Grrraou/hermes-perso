# Isolated Hermes Agent (Docker)

Run [Hermes Agent](https://hermes-agent.nousresearch.com/) in a locked-down container so it can chat, use tools, and browse **only inside the container**. It does not see your home folder, SSH keys, browser cookies, or the rest of the host disk.

This machine is the **host**. Any other phone, laptop, or PC on the same Wi‑Fi / Ethernet is a **client**.

---

## What the container can and cannot see

| Visible to Hermes | Hidden from Hermes |
| --- | --- |
| `./data` in this project (config, API keys, sessions, memory, skills) | Your home directory, Documents, Downloads, Photos |
| Outbound internet (LLM APIs, websites the agent fetches) | Host SSH keys, password stores, other Docker containers |
| Optional: a model server on the host via `host.docker.internal` | The Docker engine (`/var/run/docker.sock` is **not** mounted) |

The official image can drive the host Docker daemon **if** you mount the socket. This project never does that. Do not add `$HOME`, `~/.ssh`, or `/var/run/docker.sock` to `docker-compose.yml`.

Hermes state lives only in `./data` (mapped to `/opt/data` in the container). Delete that folder and the agent’s memory is gone. The host OS is otherwise untouched.

---

## Host this computer

You need Docker Engine and Compose (`docker compose version`, or the older `docker-compose` binary). On Debian/Ubuntu: `sudo apt install docker-compose-v2` (or `docker-compose-plugin` from Docker’s repo). The Makefile uses whichever of those is available.

### 1. Create secrets and the data folder

```bash
make init
```

That writes a private `.env` (dashboard password + API key) and creates `./data`. Copy the printed password somewhere you can type on the other computer.

Manual alternative: `cp .env.example .env`, then replace every `change-me` value. Set `HERMES_UID` / `HERMES_GID` to `id -u` and `id -g` so `./data` stays readable on the host.

### 2. First-time Hermes setup (once)

```bash
make setup
```

The wizard asks for provider keys (Nous Portal, OpenRouter, Anthropic, OpenAI, …) and writes them into `./data/.env` — **inside this project**, not into `~/.hermes` on the host.

### 3. Open it on this PC

`make setup` only writes config, then exits. Nothing is listening until you start the stack:

```bash
make up
```

Wait until `make ps` shows the container healthy (or `make logs` stops repeating startup). Then on **this same computer**:

| What | URL |
| --- | --- |
| Chat (hermes-webui, phone-friendly) | [http://127.0.0.1:8787](http://127.0.0.1:8787) |
| Official dashboard | [http://127.0.0.1:9119](http://127.0.0.1:9119) |
| API health check | [http://127.0.0.1:8642/health](http://127.0.0.1:8642/health) |

WebUI password is the dashboard password from `.env` (`HERMES_DASHBOARD_BASIC_AUTH_PASSWORD`, printed once by `make init`). Official dashboard also needs the username `hermes`. Use `127.0.0.1`, not the LAN IP and not the WSL `172.*` address.

Terminal chat against the same data (stack must already be up):

```bash
make chat
```

`127.0.0.1` works in the Windows browser on WSL2 when Docker published the ports to localhost. Phone / other PCs are a later step (LAN or Tailscale below).

Do not start a second Hermes container against `./data` at the same time.

### Local voice (STT + TTS)

No cloud speech APIs. Packages live in `./data/lazy-packages`; models in `./data/cache`.

| Role | Engine | Default |
| --- | --- | --- |
| Speech-to-text | faster-whisper, on CPU | `small` (~500MB), language auto |
| Text-to-speech | Piper | `en_US-lessac-medium` |

French TTS is already downloaded: set `tts.piper.voice` to `fr_FR-siwis-medium` in `./data/config.yaml`. If CPU is tight, switch `stt.local.model` to `base`. After a fresh image pull, `make voice` reinstalls the Python packages.

WebUI mic (local Whisper): open [http://127.0.0.1:8787](http://127.0.0.1:8787) — not a LAN/`192.168` URL (browsers block the mic on plain HTTP). Click the mic, speak, **click the mic again to stop**. Text is transcribed after you stop; it is not live captions. First stop after startup can take ~15s while Whisper loads.

In the CLI: `/voice on`, `/voice tts`, `/voice off`. The Hermes container has no host microphone, so CLI push-to-talk may say there is no audio device. Voice-note files and the `text_to_speech` tool still work.

---

## Use it from another computer on the same LAN

Both devices must be on the same local network (same Wi‑Fi, or Ethernet into the same router). Do **not** port-forward 9119 or 8642 on the router — that would expose the agent to the internet.

### 1. Find the host’s LAN IP

On the **host** (the machine running Docker):

```bash
# Linux
ip -4 route get 1.1.1.1 | awk '{print $7; exit}'

# macOS
ipconfig getifaddr en0

# Windows (PowerShell)
Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.IPAddress -notlike '127.*' }
```

You want a private address such as `192.168.1.42` or `10.0.0.15`. That is `HOST_IP` below.

From the **client**, check that the host answers:

```bash
ping HOST_IP
curl -s http://HOST_IP:8642/health
```

`{"status":"ok",...}` means the API is reachable. If ping works but ports do not, open the firewall on the host (next section).

### 2. Browser dashboard (easiest)

On the client, open:

```
http://HOST_IP:8787
```

That is [hermes-webui](https://github.com/nesquena/hermes-webui). Password is `HERMES_DASHBOARD_BASIC_AUTH_PASSWORD` (or `HERMES_WEBUI_PASSWORD` if you set one). The official dashboard is still at `http://HOST_IP:9119` with the same user/password.

You can do this from a phone, a tablet, or another PC. No Hermes install is needed on the client.

### 3. Hermes Desktop on the client

1. Install [Hermes Desktop](https://hermes-agent.nousresearch.com/) on the **client** only.
2. Open **Settings → Gateway → Remote gateway**.
3. URL:

   ```
   http://HOST_IP:9119
   ```

4. Sign in with the same dashboard user/password, then save and reconnect.

Desktop talks to port **9119** (dashboard backend), not 8642. One connection serves every profile on that host.

### 4. OpenAI-compatible API on the client

Anything that speaks the OpenAI API (Open WebUI, LobeChat, a script) can point at the host:

| Setting | Value |
| --- | --- |
| Base URL | `http://HOST_IP:8642/v1` |
| API key | `API_SERVER_KEY` from `.env` |

Example from the client:

```bash
curl -s http://HOST_IP:8642/v1/models \
  -H "Authorization: Bearer YOUR_API_SERVER_KEY"
```

### 5. Open the two ports on the host firewall (LAN only)

**Linux (ufw)**

```bash
sudo ufw allow from 192.168.0.0/16 to any port 8787 proto tcp
sudo ufw allow from 192.168.0.0/16 to any port 9119 proto tcp
sudo ufw allow from 192.168.0.0/16 to any port 8642 proto tcp
# also allow 10.0.0.0/8 if your LAN uses that range
```

**Windows** (run in PowerShell as Administrator) — needed if Docker Desktop / WSL publishes the ports on Windows:

```powershell
New-NetFirewallRule -DisplayName "Hermes webui LAN" -Direction Inbound -Protocol TCP -LocalPort 8787 -Action Allow -Profile Private
New-NetFirewallRule -DisplayName "Hermes dashboard LAN" -Direction Inbound -Protocol TCP -LocalPort 9119 -Action Allow -Profile Private
New-NetFirewallRule -DisplayName "Hermes API LAN" -Direction Inbound -Protocol TCP -LocalPort 8642 -Action Allow -Profile Private
```

**macOS**: System Settings → Network → Firewall → Options, allow incoming for Docker.

Keep the host’s Wi‑Fi / Ethernet profile **Private**. Do not allow these ports on a Public / Guest network.

### 6. WSL2 host (Windows) — extra step

WSL2 has its own IP. A laptop on Wi‑Fi often cannot reach ports that only listen inside WSL.

Pick one:

**A. Mirrored networking (simplest)** — on Windows, create or edit `%UserProfile%\.wslconfig`:

```ini
[wsl2]
networkingMode=mirrored
```

Then `wsl --shutdown` and reopen the distro. Restart Hermes. Clients use the **Windows** LAN IP (`192.168.x.x`), not the WSL IP.

**B. Port proxy** — if you stay on the default NAT mode, on Windows (Admin PowerShell):

```powershell
$wsl = (wsl hostname -I).Trim().Split(" ")[0]
netsh interface portproxy add v4tov4 listenport=8787 listenaddress=0.0.0.0 connectport=8787 connectaddress=$wsl
netsh interface portproxy add v4tov4 listenport=9119 listenaddress=0.0.0.0 connectport=9119 connectaddress=$wsl
netsh interface portproxy add v4tov4 listenport=8642 listenaddress=0.0.0.0 connectport=8642 connectaddress=$wsl
```

Then use the **Windows** LAN IP on the client. Re-run this after WSL gets a new IP.

### 7. Bind only the LAN NIC (optional)

To avoid listening on VPNs or extra interfaces, set the host’s LAN IP in `.env`:

```env
HERMES_BIND_IP=192.168.1.42
```

```bash
docker compose up -d
```

---

## Daily commands

```bash
make up         # start
make logs       # follow logs
make chat       # CLI chat inside the sandbox
make voice      # reinstall local Whisper + Piper into ./data
make restart    # bounce gateway + dashboard
make down       # stop — ./data is kept
make build      # pull a new image and recreate — ./data is kept
make destroy    # the only command that deletes ./data (type destroy)
```

`make down`, `make build`, and `make restart` never pass `--volumes`. Hermes config, sessions, memories, and keys stay in `./data` until you run `make destroy` and confirm.

---

## Using a local model on the host (Ollama, vLLM)

The container cannot use `localhost` for something running on the host — that is the container itself. In `./data/config.yaml` use:

```yaml
base_url: http://host.docker.internal:11434/v1
```

The host model server must listen on `0.0.0.0`, not only `127.0.0.1`. This still does **not** give Hermes your files; it only opens an HTTP path to that API.

---

## Isolation checklist

- [x] Hermes home is `./data`, not `~` or `~/.hermes` on the host
- [x] No Docker socket — the agent cannot start host containers
- [x] No host networking — only published 8642 and 9119
- [x] Capability drop + `no-new-privileges`
- [x] Memory / CPU / PID caps
- [x] Dashboard login required on a LAN bind
- [x] API requires `API_SERVER_KEY` (8+ characters)

Still true: Hermes can use the network (that is how LLM APIs work) and can write anything under `./data`. Treat `./data` like a secrets folder (`chmod 700`, do not commit `.env` or `data/`).

---

## Troubleshooting

| Symptom | What to try |
| --- | --- |
| Dashboard exits: “no auth providers” | `.env` must set `HERMES_DASHBOARD_BASIC_AUTH_USERNAME` and `_PASSWORD`. Recreate: `docker compose up -d --force-recreate` |
| Client cannot open `http://HOST_IP:9119` | Ping `HOST_IP`. Check `docker compose ps`. Open the firewall. On WSL2, use mirrored networking or a port proxy |
| `/health` fails | Wait for the healthcheck `start_period`, then `docker compose logs --tail 80` |
| Permission denied on `./data` | `HERMES_UID` / `HERMES_GID` must match `id -u` / `id -g` |
| Browser tools crash | `shm_size` is already `1gb`; raise `HERMES_MEM_LIMIT` if Chromium is OOM |
| Two gateways fighting | Only one container may mount `./data` |
| `unknown flag: --rm` or `unknown command: docker compose` | Compose plugin is missing. Install: `sudo apt install docker-compose-v2` |
| `client version 1.52 is too new` | Ubuntu’s `docker` CLI is newer than Docker Desktop. The Makefile sets `DOCKER_API_VERSION=1.43`. |
| `make ps` empty but :9119 still answers | Leftover on Ubuntu’s `dockerd`, not Desktop. Stop that engine’s Hermes (`sudo ctr -n moby tasks kill --signal SIGKILL <container-id>`), then `make up`. |

Official image notes: [Hermes Docker setup](https://hermes-agent.nousresearch.com/docs/user-guide/docker).
