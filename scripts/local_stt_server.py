#!/usr/bin/env python3
"""Local Whisper HTTP server for hermes-webui dictation.

The WebUI process is too small to load faster-whisper itself. This service
shares ./data with Hermes and transcribes browser recordings on the LAN
Docker network only (no published port).
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

os.environ.setdefault("HERMES_HOME", "/opt/data")
os.environ.setdefault("HOME", "/opt/data")
os.environ.setdefault("HF_HOME", "/opt/data/.cache/huggingface")
os.environ.setdefault("HERMES_LAZY_INSTALL_TARGET", "/opt/data/lazy-packages")

sys.path.insert(0, "/opt/hermes")
lazy = Path("/opt/data/lazy-packages")
if lazy.is_dir() and str(lazy) not in sys.path:
    sys.path.append(str(lazy))

try:
    from tools.lazy_deps import activate_durable_lazy_target

    activate_durable_lazy_target()
except Exception:
    pass

from tools.transcription_tools import transcribe_audio  # noqa: E402

HOST = os.environ.get("HERMES_STT_HOST", "0.0.0.0")
PORT = int(os.environ.get("HERMES_STT_PORT", "8765"))
MAX_BYTES = 32 * 1024 * 1024


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt: str, *args) -> None:
        sys.stderr.write("[stt] " + (fmt % args) + "\n")

    def _json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if self.path.split("?", 1)[0] in ("/health", "/"):
            self._json(200, {"ok": True, "provider": "local"})
            return
        self._json(404, {"error": "not found"})

    def do_POST(self) -> None:
        if self.path.split("?", 1)[0] != "/transcribe":
            self._json(404, {"error": "not found"})
            return
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            length = 0
        if length <= 0 or length > MAX_BYTES:
            self._json(413, {"error": "audio too large or empty"})
            return
        data = self.rfile.read(length)
        name = self.headers.get("X-Filename") or "voice.webm"
        suffix = Path(name).suffix or ".webm"
        if suffix.lower() not in {".webm", ".ogg", ".wav", ".mp3", ".m4a", ".mp4", ".flac"}:
            suffix = ".webm"
        tmp = None
        try:
            with tempfile.NamedTemporaryFile(prefix="webui-stt-", suffix=suffix, delete=False) as fh:
                tmp = fh.name
                fh.write(data)
            result = transcribe_audio(tmp)
        except Exception:
            traceback.print_exc()
            self._json(500, {"error": "Transcription failed"})
            return
        finally:
            if tmp:
                Path(tmp).unlink(missing_ok=True)
        if not result.get("success"):
            msg = str(result.get("error") or "Transcription failed")
            self._json(400, {"error": msg})
            return
        self._json(200, {"ok": True, "transcript": str(result.get("transcript") or "").strip()})


def main() -> None:
    httpd = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"[stt] local whisper on {HOST}:{PORT}", flush=True)
    httpd.serve_forever()


if __name__ == "__main__":
    main()
