"""Route hermes-webui /api/transcribe to the local Whisper sidecar.

WebUI's own Python cannot load faster-whisper in the 1g container (it OOMs).
Capability probes then leave Chrome SpeechRecognition as the mic path, which
often records with no error and inserts no text.
"""
from __future__ import annotations

import builtins
import json
import os
import sys
import urllib.error
import urllib.request

STT_URL = os.environ.get("HERMES_WEBUI_STT_URL", "http://hermes-stt:8765").rstrip("/")
_PATCHED = False
_orig_import = builtins.__import__


def _json_response(mod, handler, payload, status=200):
    return mod.j(handler, payload, status=status)


def _capability(_handler_mod=None):
    try:
        with urllib.request.urlopen(f"{STT_URL}/health", timeout=2) as resp:
            data = json.loads(resp.read().decode("utf-8") or "{}")
        if data.get("ok"):
            return True, str(data.get("provider") or "local")
    except Exception:
        pass
    return False, "none"


def _patch(mod) -> None:
    global _PATCHED
    if _PATCHED:
        return
    _PATCHED = True

    def handle_transcribe_capability(handler):
        available, provider = _capability()
        return _json_response(mod, handler, {"ok": True, "available": bool(available), "provider": provider})

    def handle_transcribe(handler):
        content_type = handler.headers.get("Content-Type", "")
        content_length = int(handler.headers.get("Content-Length", 0) or 0)
        if content_length > getattr(mod, "MAX_UPLOAD_BYTES", 32 * 1024 * 1024):
            return _json_response(
                mod, handler, {"error": "File too large"}, status=413
            )
        fields, files = mod.parse_multipart(handler.rfile, content_type, content_length)
        if "file" not in files:
            return _json_response(mod, handler, {"error": "No file field in request"}, status=400)
        filename, file_bytes = files["file"]
        if not filename:
            return _json_response(mod, handler, {"error": "No filename in upload"}, status=400)
        req = urllib.request.Request(
            f"{STT_URL}/transcribe",
            data=file_bytes,
            method="POST",
            headers={
                "Content-Type": "application/octet-stream",
                "X-Filename": filename,
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=180) as resp:
                data = json.loads(resp.read().decode("utf-8") or "{}")
        except urllib.error.HTTPError as exc:
            try:
                data = json.loads(exc.read().decode("utf-8") or "{}")
            except Exception:
                data = {"error": "Transcription failed"}
            return _json_response(
                mod, handler, {"error": data.get("error") or "Transcription failed"}, status=exc.code
            )
        except Exception as exc:
            return _json_response(mod, handler, {"error": str(exc) or "Transcription failed"}, status=503)
        if not data.get("ok"):
            return _json_response(
                mod, handler, {"error": data.get("error") or "Transcription failed"}, status=400
            )
        return _json_response(
            mod, handler, {"ok": True, "transcript": str(data.get("transcript") or "").strip()}
        )

    mod.handle_transcribe = handle_transcribe
    mod.handle_transcribe_capability = handle_transcribe_capability
    mod._stt_provider_capability = _capability


def _import(name, globals=None, locals=None, fromlist=(), level=0):
    module = _orig_import(name, globals, locals, fromlist, level)
    upload = sys.modules.get("api.upload")
    if upload is not None:
        _patch(upload)
    return module


builtins.__import__ = _import
