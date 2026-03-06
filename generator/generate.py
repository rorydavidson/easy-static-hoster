#!/usr/bin/env python3
"""
EasyHoster generator — walks the content directory, renders index.html,
then watches for changes and re-renders on any file event.
"""

import os
import json
import time
import logging
import argparse
from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader
from watchdog.observers.polling import PollingObserver
from watchdog.events import FileSystemEventHandler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

TEMPLATE_DIR = Path(__file__).parent / "templates"
INDEX_FILENAME = "index.html"
HTML_SUFFIX = ".html"


def humanize(stem: str) -> str:
    """'my-report_2025' → 'My Report 2025'"""
    return stem.replace("-", " ").replace("_", " ").title()


def build_context(content_dir: Path, site_title: str) -> dict:
    categories = []

    for folder in sorted(content_dir.iterdir()):
        if not folder.is_dir():
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

        pages = []
        for f in sorted(folder.iterdir()):
            if f.suffix.lower() != HTML_SUFFIX:
                continue  # skip images, meta.json, etc.
            stat = f.stat()
            pages.append(
                {
                    "title": humanize(f.stem),
                    "path": f"{folder.name}/{f.name}",
                    "modified": datetime.fromtimestamp(stat.st_mtime).strftime(
                        "%Y-%m-%d"
                    ),
                }
            )

        if not pages:
            continue

        categories.append(
            {
                "title": meta.get("title", humanize(folder.name)),
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
    }


def render_index(content_dir: Path, site_title: str) -> None:
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATE_DIR)),
        autoescape=True,
    )
    template = env.get_template("index.html.j2")
    context = build_context(content_dir, site_title)
    output = template.render(**context)
    index_path = content_dir / INDEX_FILENAME
    index_path.write_text(output, encoding="utf-8")
    log.info(
        "Index rebuilt — %d categor%s, %d page%s",
        len(context["categories"]),
        "y" if len(context["categories"]) == 1 else "ies",
        context["total_pages"],
        "" if context["total_pages"] == 1 else "s",
    )


class ContentHandler(FileSystemEventHandler):
    def __init__(self, content_dir: Path, site_title: str) -> None:
        self.content_dir = content_dir
        self.site_title = site_title
        self._last_rebuild = 0.0

    def on_any_event(self, event) -> None:
        # Ignore events triggered by writing index.html itself
        if INDEX_FILENAME in str(event.src_path):
            return

        # Debounce: at most one rebuild per second
        now = time.monotonic()
        if now - self._last_rebuild < 1.0:
            return
        self._last_rebuild = now

        try:
            render_index(self.content_dir, self.site_title)
        except Exception as exc:
            log.error("Rebuild failed: %s", exc)


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
        help="Generate index once and exit (no watcher)",
    )
    args = parser.parse_args()

    content_dir = Path(args.content)
    if not content_dir.exists():
        log.error("Content directory not found: %s", content_dir)
        raise SystemExit(1)

    log.info("EasyHoster generator starting — content: %s, title: %s", content_dir, args.title)

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
