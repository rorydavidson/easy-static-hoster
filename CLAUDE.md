# EasyHoster

A minimal static HTML hosting solution with auto-generated index, folder-based categories, and Docker-based deployment.

## Purpose

Host self-contained HTML files (presentations, reports, notebooks) behind a clean index page. No CMS, no database, no build step — drop an HTML file in a folder and it appears on the index.

## Architecture

Two containers managed by Docker Compose:

| Container   | Role                                                          |
|-------------|---------------------------------------------------------------|
| `nginx`     | Serves static files and the generated index                   |
| `generator` | Watches content volume, rebuilds `index.html` on file changes |

Shared volume (`content/`) is the only data store. Generator writes `index.html` to the root of that volume; Nginx serves everything from it.

```
content/
  index.html              ← auto-generated, do not edit manually
  presentations/
    q1-review.html
    product-demo.html
  reports/
    annual-2025.html
  category/
    meta.json             ← optional: { "title": "Display Name", "order": 1 }
```

## Key Files

- `docker-compose.yml` — orchestration, env vars, volume mounts
- `nginx/nginx.conf` — security headers, rate limiting, file serving rules
- `nginx/Dockerfile` — minimal nginx:alpine image, non-root user
- `generator/generate.py` — directory walker + Jinja2 renderer + watchdog watcher
- `generator/templates/index.html.j2` — index page template (no external deps)
- `generator/requirements.txt` — watchdog, jinja2 (keep minimal)

## Content Rules

- **Folders = categories.** Only top-level folders are shown as categories. Empty folders appear in the index with a placeholder row.
- **`.html` files only** are linked in the index. All other file types are silently ignored by the generator.
- **Images and assets** (`.png`, `.jpg`, `.gif`, `.svg`, `.webp`, `.ico`, `.css`, `.js`, etc.) can be placed freely inside category folders. They are served by Nginx and can be referenced from HTML files using relative paths (e.g. `<img src="logo.png">`), but they never appear as index entries.
- **Filename humanization:** `my-report-2025.html` → "My Report 2025". Hyphens and underscores become spaces, title-cased.
- **`_`-prefixed HTML files** (e.g. `_example.html`) are "example" placeholders: shown in the index only while no regular HTML files exist in the folder. Hidden automatically once real content is added. Still served by Nginx if linked directly.
- **`meta.json` in a folder** (optional): `{ "title": "Custom Name", "order": 1, "hidden": false }`
- Files at the content root (other than `index.html`) are not shown in the index.
- Subdirectories deeper than one level are ignored.

## Running

```bash
# Development (local content dir)
CONTENT_DIR=./content SITE_TITLE="My Reports" docker compose up

# Production (external content dir, detached)
CONTENT_DIR=/data/reports SITE_TITLE="Reports" docker compose up -d

# Rebuild after code changes
docker compose build && docker compose up -d
```

## Environment Variables

| Variable       | Default         | Description                        |
|----------------|-----------------|------------------------------------|
| `CONTENT_DIR`  | `./content`     | Host path to the content directory |
| `SITE_TITLE`   | `EasyHoster`    | Displayed in the index page title  |
| `BASIC_AUTH`   | (unset)         | Set to `user:password` to enable HTTP Basic Auth |

## Security Posture

- Nginx runs as non-root (`nginx` user, uid 101)
- Generator runs as non-root (`appuser`, uid 1000)
- `server_tokens off` — no version disclosure
- Security headers on all responses: `X-Frame-Options`, `X-Content-Type-Options`, `Referrer-Policy`, `Content-Security-Policy`
- Rate limiting: 20 req/s per IP, burst 40
- No directory listing — only the generated `index.html` serves as navigation
- Only `.html` files are linked from the index; Nginx still serves any valid file path (for assets referenced by HTML files)
- Optional Basic Auth gates the entire site with a single env var

## Development Notes

- The generator uses **watchdog** for cross-platform file watching (works on macOS and Linux)
- Polling fallback is enabled for Docker volume compatibility (`ObservedWatch` with polling)
- The index template is **self-contained** — no CDN calls, no external fonts; the site works fully offline
- Generator regenerates immediately at startup, then on any `created`/`deleted`/`modified` event in the content dir
- To test the generator independently: `python generator/generate.py --content ./content --output ./content/index.html --title "Test"`

## Adding Content

1. Create a folder inside `CONTENT_DIR` for a new category (if needed)
2. Drop a `.html` file into the folder
3. The index updates within ~1 second automatically (no restart needed)

## What This Is Not

- Not a CMS — no editing interface
- Not a web app framework — no server-side rendering of content files
- Not a CDN — designed for internal/team use, not public traffic at scale
- Not a file manager — no upload UI; files are managed via filesystem/scp/rsync
