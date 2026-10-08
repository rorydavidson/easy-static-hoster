#!/usr/bin/env python3
"""
EasyHoster generator — walks the content directory, renders index.html,
then watches for changes and re-renders on any file event.
Also starts the shortlinks redirect server as a daemon thread.
"""

import os
import json
import time
import logging
import argparse
import threading
import urllib.request
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import quote

from jinja2 import Environment, FileSystemLoader
from watchdog.observers.polling import PollingObserver
from watchdog.events import FileSystemEventHandler

import shortlinks_server

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

TEMPLATE_DIR = Path(__file__).parent / "templates"
INDEX_FILENAME = "index.html"
# Dot-prefixed so nginx refuses to serve it and the index never lists it
INDEX_TMP_FILENAME = ".index.html.tmp"
HTML_SUFFIX = ".html"


# ── HTML title extraction ─────────────────────────────────────────────────────

class _TitleParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._in_title = False
        self.title: str | None = None

    def handle_starttag(self, tag, attrs) -> None:
        if tag.lower() == "title":
            self._in_title = True

    def handle_endtag(self, tag) -> None:
        if tag.lower() == "title":
            self._in_title = False

    def handle_data(self, data) -> None:
        if self._in_title and self.title is None:
            stripped = data.strip()
            if stripped:
                self.title = stripped


def extract_title(path: Path) -> str | None:
    """Return the text content of the first <title> tag, or None."""
    try:
        # Only read the first 4 KB — the <title> is always in <head>
        with path.open("rb") as f:
            content = f.read(4096).decode("utf-8", errors="ignore")
        parser = _TitleParser()
        parser.feed(content)
        return parser.title
    except Exception:
        return None


# ── Helpers ───────────────────────────────────────────────────────────────────

def humanize(stem: str) -> str:
    """'my-report_2025' → 'My Report 2025' (fallback when no <title>)"""
    return stem.replace("-", " ").replace("_", " ").title()


def load_shortlinks(content_dir: Path) -> dict:
    """Return the code → path mapping from shortlinks.json."""
    path = content_dir / "shortlinks.json"
    if not path.exists():
        return {}
    try:
        links = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        log.warning("Could not parse shortlinks.json: %s", exc)
        return {}
    if not isinstance(links, dict):
        return {}
    return {k: v for k, v in links.items() if isinstance(v, str)}


# ── OIDC logout ───────────────────────────────────────────────────────────────

_end_session_endpoints: dict[str, str] = {}


def discover_end_session_endpoint(issuer_url: str) -> str:
    """Return the provider's RP-initiated logout URL, or "" if unavailable.

    Read from the issuer's discovery document because the path differs per
    provider (Keycloak, Azure AD and Google all disagree). Only successes are
    cached, so a provider that was down at startup is retried on later rebuilds.
    """
    if issuer_url in _end_session_endpoints:
        return _end_session_endpoints[issuer_url]
    try:
        with urllib.request.urlopen(
            f"{issuer_url}/.well-known/openid-configuration", timeout=3
        ) as resp:
            endpoint = json.load(resp).get("end_session_endpoint", "")
    except Exception as exc:
        log.warning("OIDC discovery failed, sign-out will be local only: %s", exc)
        return ""
    if not isinstance(endpoint, str) or not endpoint.startswith(("https://", "http://")):
        endpoint = ""
    _end_session_endpoints[issuer_url] = endpoint
    return endpoint


def oidc_logout_url() -> str:
    issuer_url = os.environ.get("OIDC_ISSUER_URL", "").strip().rstrip("/")
    if not issuer_url:
        return ""
    endpoint = discover_end_session_endpoint(issuer_url)
    if not endpoint:
        return ""
    client_id = os.environ.get("OIDC_CLIENT_ID", "").strip()
    separator = "&" if "?" in endpoint else "?"
    return f"{endpoint}{separator}client_id={quote(client_id, safe='')}"


# ── Index builder ─────────────────────────────────────────────────────────────

def build_context(content_dir: Path, site_title: str) -> dict:
    # Build reverse map: file path (relative) → short code
    shortlinks = load_shortlinks(content_dir)
    path_to_code: dict[str, str] = {v.lstrip("/"): k for k, v in shortlinks.items()}

    categories = []

    for folder in sorted(content_dir.iterdir()):
        # Dot-dirs (.git, editor caches) are never served by nginx anyway
        if not folder.is_dir() or folder.name.startswith("."):
            continue

        # Optional per-category metadata
        meta: dict = {}
        meta_path = folder / "meta.json"
        if meta_path.exists():
            try:
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
            except Exception as exc:
                log.warning("Could not parse %s: %s", meta_path, exc)

        if meta.get("hidden", False):
            continue

        pages: list[dict] = []
        example_pages: list[dict] = []
        for f in sorted(folder.iterdir()):
            if f.suffix.lower() != HTML_SUFFIX:
                continue  # skip images, assets, meta.json, etc.

            rel_path = f"{folder.name}/{f.name}"
            stat = f.stat()
            entry = {
                # Prefer <title> tag; fall back to humanized filename.
                # Strip leading underscores from stem before humanizing so
                # that _example.html renders as "Example", not " Example".
                "title": extract_title(f) or humanize(f.stem.lstrip("_")),
                "path": rel_path,
                "modified": datetime.fromtimestamp(stat.st_mtime).strftime(
                    "%Y-%m-%d"
                ),
                "shortlink": path_to_code.get(rel_path),
            }
            if f.name.startswith("_"):
                example_pages.append(entry)
            else:
                pages.append(entry)

        # Files prefixed with _ are "example" placeholders: visible only when
        # the folder has no real pages; hidden the moment real content arrives.
        if not pages:
            pages = example_pages

        categories.append(
            {
                "title": meta.get("title", humanize(folder.name)),
                "folder": folder.name,
                "order": meta.get("order", 999),
                "pages": pages,
            }
        )

    categories.sort(key=lambda c: (c["order"], c["title"]))

    total_pages = sum(len(c["pages"]) for c in categories)

    return {
        "site_title": site_title,
        "categories": categories,
        "total_pages": total_pages,
        "generated": datetime.now().strftime("%Y-%m-%d %H:%M"),
        # Upload button is shown when any auth mechanism is configured.
        "upload_enabled": bool(
            os.environ.get("BASIC_AUTH", "").strip()
            or os.environ.get("OIDC_ISSUER_URL", "").strip()
        ),
        # Auth mode determines UI behaviour (credential modal vs session auth).
        "auth_mode": (
            "oidc" if os.environ.get("OIDC_ISSUER_URL", "").strip()
            else "basic" if os.environ.get("BASIC_AUTH", "").strip()
            else "none"
        ),
        "header_color": os.environ.get("HEADER_COLOR", "").strip(),
        "open_new_tab": os.environ.get("OPEN_NEW_TAB", "true").strip().lower() != "false",
        # Provider logout URL for federated sign-out; "" means local sign-out only
        "oidc_logout_url": oidc_logout_url(),
    }


def render_index(content_dir: Path, site_title: str) -> None:
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATE_DIR)),
        autoescape=True,
    )
    template = env.get_template("index.html.j2")
    context = build_context(content_dir, site_title)
    output = template.render(**context)
    # Write then rename so nginx never serves a half-written index
    tmp_path = content_dir / INDEX_TMP_FILENAME
    tmp_path.write_text(output, encoding="utf-8")
    os.replace(tmp_path, content_dir / INDEX_FILENAME)
    log.info(
        "Index rebuilt — %d categor%s, %d page%s",
        len(context["categories"]),
        "y" if len(context["categories"]) == 1 else "ies",
        context["total_pages"],
        "" if context["total_pages"] == 1 else "s",
    )


# ── File watcher ──────────────────────────────────────────────────────────────

class ContentHandler(FileSystemEventHandler):
    # Rebuild this long after the last event, so a burst of changes (an rsync,
    # an upload plus its rename) produces one rebuild that sees all of them
    debounce_seconds = 1.0

    def __init__(self, content_dir: Path, site_title: str) -> None:
        self.content_dir = content_dir
        self.site_title = site_title
        self._own_outputs = {
            str(content_dir / INDEX_FILENAME),
            str(content_dir / INDEX_TMP_FILENAME),
        }
        self._timer: threading.Timer | None = None
        self._lock = threading.Lock()

    def on_any_event(self, event) -> None:
        # Ignore events triggered by writing index.html itself
        paths = {str(event.src_path), str(getattr(event, "dest_path", "") or "")}
        if paths - {""} <= self._own_outputs:
            return

        with self._lock:
            if self._timer is not None:
                self._timer.cancel()
            self._timer = threading.Timer(self.debounce_seconds, self._rebuild)
            self._timer.daemon = True
            self._timer.start()

    def _rebuild(self) -> None:
        try:
            render_index(self.content_dir, self.site_title)
        except Exception as exc:
            log.error("Rebuild failed: %s", exc)


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="EasyHoster index generator")
    parser.add_argument(
        "--content",
        default=os.environ.get("CONTENT_DIR", "/content"),
        help="Path to content directory",
    )
    parser.add_argument(
        "--title",
        default=os.environ.get("SITE_TITLE", "EasyHoster"),
        help="Site title shown in the index",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Generate index once and exit (no watcher, no server)",
    )
    args = parser.parse_args()

    content_dir = Path(args.content)
    if not content_dir.exists():
        log.error("Content directory not found: %s", content_dir)
        raise SystemExit(1)

    log.info(
        "EasyHoster generator starting — content: %s, title: %s",
        content_dir,
        args.title,
    )

    # Start shortlinks HTTP server as a background daemon thread
    if not args.once:
        t = threading.Thread(
            target=shortlinks_server.start,
            args=(content_dir,),
            daemon=True,
            name="shortlinks-server",
        )
        t.start()

    render_index(content_dir, args.title)

    if args.once:
        return

    handler = ContentHandler(content_dir, args.title)
    # PollingObserver works reliably on Docker bind mounts (macOS + Linux)
    observer = PollingObserver(timeout=2)
    observer.schedule(handler, str(content_dir), recursive=True)
    observer.start()
    log.info("Watching for changes (polling every 2s)...")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        observer.stop()
        observer.join()


if __name__ == "__main__":
    main()
