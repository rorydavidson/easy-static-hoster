"""
EasyHoster shortlinks server — runs as a daemon thread inside the generator
container, now using Flask for better security and production readiness.

GET  /s/<code>         → 302 redirect to the mapped page
POST /api/shortlinks   → set or remove a short link (JSON body)
POST /api/upload       → upload an HTML file to an existing category folder
                         (only active when BASIC_AUTH env var is set)
"""

import base64
import json
import logging
import os
import re
from pathlib import Path
from urllib.parse import quote, unquote

from flask import Flask, request, jsonify, redirect, Response

log = logging.getLogger(__name__)

CONTENT_DIR = Path(os.environ.get("CONTENT_DIR", "/content"))
PORT = 5000

UPLOAD_MAX_BYTES = 10 * 1024 * 1024  # 10 MB

# Upload is only active when HTTP Basic Auth is configured (BASIC_AUTH env var).
_UPLOAD_ENABLED = bool(os.environ.get("BASIC_AUTH", "").strip())

# Allowed short codes: lowercase letters, digits, hyphens, underscores. 1–50 chars.
_CODE_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,49}$")

# File types accepted by the upload endpoint
_ALLOWED_SUFFIXES = {
    ".html",
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".ico",
}

app = Flask(__name__)

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


def _check_upload_auth() -> bool:
    """Return True if the Authorization header matches BASIC_AUTH exactly."""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Basic "):
        return False
    try:
        decoded = base64.b64decode(auth_header[6:]).decode("utf-8")
    except Exception:
        return False
    return decoded == os.environ.get("BASIC_AUTH", "")


@app.route('/s/<code>', methods=['GET'])
def redirect_shortlink(code):
    links = load_shortlinks()
    target = links.get(code)

    if not target:
        return f"Short link '{code}' not found", 404

    # URL-encode so non-ASCII chars are safe to send in a Latin-1 HTTP header.
    location = target if target.startswith("/") else f"/{target}"
    location = quote(location, safe="/:@!$&'()*+,;=")
    
    response = redirect(location, code=302)
    response.headers["Cache-Control"] = "no-cache"
    return response


@app.route('/api/shortlinks', methods=['POST'])
def handle_shortlink():
    # As requested, #1 (auth for shortlinks) is ignored.
    data = request.get_json(silent=True)
    if data is None:
        return jsonify({"error": "invalid JSON"}), 400

    page_path = str(data.get("path", "")).strip().lstrip("/")
    code = str(data.get("code", "")).strip().lower()

    if not page_path:
        return jsonify({"error": "path is required"}), 400

    if code and not _CODE_RE.match(code):
        return jsonify({"error": "code must be lowercase letters, digits, hyphens or underscores"}), 400

    links = load_shortlinks()

    # Remove any existing code that points to this page
    links = {k: v for k, v in links.items() if v.lstrip("/") != page_path}

    if code:
        if code in links:
            return jsonify({"error": f"'{code}' is already used by another page"}), 409
        links[code] = page_path

    try:
        save_shortlinks(links)
    except Exception as exc:
        log.error("Failed to write shortlinks.json: %s", exc)
        return jsonify({"error": "failed to save"}), 500

    action = f"set to '{code}'" if code else "removed"
    log.info("Shortlink for %s %s", page_path, action)
    return jsonify({"ok": True})


@app.route('/api/upload', methods=['POST'])
def handle_upload():
    if not _UPLOAD_ENABLED:
        return jsonify({"error": "upload not available"}), 403

    if not _check_upload_auth():
        return jsonify({"error": "invalid credentials"}), 401

    # ── Validate folder ───────────────────────────────────────────────────
    folder = request.headers.get("X-Folder", "").strip()
    if not folder or "/" in folder or "\\" in folder or folder in (".", ".."):
        return jsonify({"error": "invalid folder"}), 400

    folder_path = CONTENT_DIR / folder
    # Ensure it resolves inside CONTENT_DIR (no path traversal)
    try:
        if not folder_path.resolve().as_posix().startswith(CONTENT_DIR.resolve().as_posix()):
            return jsonify({"error": "invalid folder"}), 400
    except Exception:
        return jsonify({"error": "invalid folder"}), 400

    if not folder_path.is_dir():
        return jsonify({"error": f"folder '{folder}' not found"}), 400

    # ── Validate filename ─────────────────────────────────────────────────
    raw_name = unquote(request.headers.get("X-Filename", "").strip())
    filename = os.path.basename(raw_name)   # strip any path components
    if not filename or filename.startswith("."):
        return jsonify({"error": "invalid filename"}), 400
    if Path(filename).suffix.lower() not in _ALLOWED_SUFFIXES:
        return jsonify({"error": "only HTML and image files are allowed"}), 400

    # ── Read body ─────────────────────────────────────────────────────────
    if request.content_length is None or request.content_length == 0:
        return jsonify({"error": "empty file"}), 400
    if request.content_length > UPLOAD_MAX_BYTES:
        mb = UPLOAD_MAX_BYTES // 1024 // 1024
        return jsonify({"error": f"file too large (max {mb} MB)"}), 400

    data = request.get_data()

    # ── Write atomically ──────────────────────────────────────────────────
    dest = folder_path / filename
    existed = dest.exists()
    tmp = dest.with_suffix(".upload_tmp")
    try:
        tmp.write_bytes(data)
        tmp.rename(dest)
    except Exception as exc:
        log.error("Upload write failed: %s", exc)
        return jsonify({"error": "failed to save file"}), 500

    verb = "Replaced" if existed else "Uploaded"
    log.info("%s %s in %s/", verb, filename, folder)
    return jsonify({"ok": True, "filename": filename, "folder": folder})


@app.route('/api/mkdir', methods=['POST'])
def handle_mkdir():
    if not _UPLOAD_ENABLED:
        return jsonify({"error": "not available"}), 403

    if not _check_upload_auth():
        return jsonify({"error": "invalid credentials"}), 401

    raw_name = unquote(request.headers.get("X-Folder", "").strip())
    folder_name = os.path.basename(raw_name)   # strip any path components
    if not folder_name or folder_name.startswith(".") or len(folder_name) > 100:
        return jsonify({"error": "invalid category name"}), 400

    folder_path = CONTENT_DIR / folder_name
    try:
        if not folder_path.resolve().as_posix().startswith(CONTENT_DIR.resolve().as_posix()):
            return jsonify({"error": "invalid category name"}), 400
    except Exception:
        return jsonify({"error": "invalid category name"}), 400

    if folder_path.exists():
        return jsonify({"error": f"'{folder_name}' already exists"}), 409

    try:
        folder_path.mkdir(parents=False, exist_ok=False)
    except Exception as exc:
        log.error("mkdir failed: %s", exc)
        return jsonify({"error": "failed to create category"}), 500

    log.info("Created category: %s/", folder_name)
    return jsonify({"ok": True, "folder": folder_name})


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

    log.info("Shortlinks server starting on port %d", PORT)
    app.run(host="0.0.0.0", port=PORT)
