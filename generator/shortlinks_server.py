"""
EasyHoster shortlinks server — runs as a daemon thread inside the generator
container.

GET  /s/<code>         → 302 redirect to the mapped page
POST /api/shortlinks   → set or remove a short link (JSON body)
"""

import json
import logging
import os
import re
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import quote

log = logging.getLogger(__name__)

CONTENT_DIR = Path(os.environ.get("CONTENT_DIR", "/content"))
PORT = 5000

# Allowed short codes: lowercase letters, digits, hyphens, underscores. 1–50 chars.
_CODE_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,49}$")


def load_shortlinks() -> dict:
    path = CONTENT_DIR / "shortlinks.json"
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        log.warning("shortlinks.json parse error: %s", exc)
        return {}


def save_shortlinks(links: dict) -> None:
    """Atomically write shortlinks.json."""
    links_file = CONTENT_DIR / "shortlinks.json"
    tmp = links_file.with_suffix(".tmp")
    tmp.write_text(json.dumps(links, indent=2) + "\n", encoding="utf-8")
    tmp.rename(links_file)


class ShortlinkHandler(BaseHTTPRequestHandler):

    # ── GET /s/<code> ─────────────────────────────────────────────────────────

    def do_GET(self) -> None:
        parts = self.path.strip("/").split("/", 1)
        if len(parts) != 2 or parts[0] != "s" or not parts[1]:
            self._respond(400, "Bad request")
            return

        code = parts[1]
        links = load_shortlinks()
        target = links.get(code)

        if not target:
            self._respond(404, f"Short link '{code}' not found")
            return

        # URL-encode so non-ASCII chars (em dashes, accents, spaces, etc.)
        # are safe to send in a Latin-1 HTTP header.
        location = target if target.startswith("/") else f"/{target}"
        location = quote(location, safe="/:@!$&'()*+,;=")
        self.send_response(302)
        self.send_header("Location", location)
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()

    # ── POST /api/shortlinks ──────────────────────────────────────────────────

    def do_POST(self) -> None:
        if self.path != "/api/shortlinks":
            self._json(404, {"error": "not found"})
            return

        length = int(self.headers.get("Content-Length", 0))
        if length > 4096:
            self._json(400, {"error": "request too large"})
            return

        try:
            data = json.loads(self.rfile.read(length))
        except (json.JSONDecodeError, ValueError):
            self._json(400, {"error": "invalid JSON"})
            return

        page_path = str(data.get("path", "")).strip().lstrip("/")
        code = str(data.get("code", "")).strip().lower()

        if not page_path:
            self._json(400, {"error": "path is required"})
            return

        if code and not _CODE_RE.match(code):
            self._json(400, {"error": "code must be lowercase letters, digits, hyphens or underscores"})
            return

        links = load_shortlinks()

        # Remove any existing code that points to this page
        links = {k: v for k, v in links.items() if v.lstrip("/") != page_path}

        if code:
            if code in links:
                self._json(409, {"error": f"'{code}' is already used by another page"})
                return
            links[code] = page_path

        try:
            save_shortlinks(links)
        except Exception as exc:
            log.error("Failed to write shortlinks.json: %s", exc)
            self._json(500, {"error": "failed to save"})
            return

        action = f"set to '{code}'" if code else "removed"
        log.info("Shortlink for %s %s", page_path, action)
        self._json(200, {"ok": True})

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _respond(self, status: int, body: str, content_type: str = "text/plain") -> None:
        encoded = body.encode()
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def _json(self, status: int, data: dict) -> None:
        self._respond(status, json.dumps(data), "application/json")

    def log_message(self, fmt, *args) -> None:
        log.debug("shortlinks: " + fmt, *args)


def start(content_dir: Path | None = None) -> None:
    global CONTENT_DIR
    if content_dir is not None:
        CONTENT_DIR = content_dir

    links_file = CONTENT_DIR / "shortlinks.json"
    if not links_file.exists():
        try:
            links_file.write_text("{}\n", encoding="utf-8")
            log.info("Created empty shortlinks.json")
        except Exception as exc:
            log.warning("Could not create shortlinks.json: %s", exc)

    server = HTTPServer(("0.0.0.0", PORT), ShortlinkHandler)
    log.info("Shortlinks server listening on port %d", PORT)
    server.serve_forever()
