# Easy Static Hoster

A minimal self-hosted page for serving static HTML files — presentations, reports, notebooks — with an auto-generated index organised by folder.

Drop an HTML file into a folder. It appears on the index within seconds. No CMS, no database, no build step.

---

## How it works

Two Docker containers share a content directory on your host machine:

- **generator** — watches the content directory and rebuilds `index.html` whenever files change
- **nginx** — serves the index and all static files (HTML, images, CSS, etc.)

The index groups pages by top-level folder (each folder = one category) and shows the last-modified date beside each page name.

---

## Requirements

- [Docker](https://docs.docker.com/get-docker/) with Compose (v2)

That's it. No other dependencies needed on the host.

---

## Quick start

```bash
git clone <this repo>
cd easyhoster
docker compose up --build
```

Open [http://localhost:8080](http://localhost:8080). You'll see the example pages included in `content/`.

---

## Adding your own pages

Create a folder inside the content directory for each category, then drop HTML files into it:

```
content/
  presentations/
    q1-review.html
    product-demo.html
    logo.png          ← images and assets are fine here
  reports/
    annual-2025.html
```

The index updates automatically within ~2 seconds. No restart needed.

**Filename → title:** `my-report-2025.html` becomes **My Report 2025** on the index (hyphens and underscores become spaces, title-cased).

---

## Configuration

Copy `.env.example` to `.env` and edit as needed:

```bash
cp .env.example .env
```

| Variable       | Default       | Description                                        |
|----------------|---------------|----------------------------------------------------|
| `CONTENT_DIR`  | `./content`   | Path to your content directory on the host         |
| `SITE_TITLE`   | `EasyHoster`  | Title shown in the index header                    |
| `PORT`         | `8080`        | Host port to expose                                |
| `BASIC_AUTH`   | *(unset)*     | Enable HTTP Basic Auth — set to `username:password`|

Example `.env` for a team reports site:

```env
CONTENT_DIR=/data/reports
SITE_TITLE=Acme Reports
PORT=8080
BASIC_AUTH=admin:correct-horse-battery-staple
```

---

## Pointing at an existing directory

If your HTML files already live somewhere on disk, just point `CONTENT_DIR` at that path:

```bash
CONTENT_DIR=/Users/alice/presentations docker compose up -d
```

EasyHoster will read from that directory and write `index.html` into it. Everything else in the directory is left untouched.

---

## Optional: category display names and ordering

Add a `meta.json` file to any folder to control how it appears on the index:

```json
{
  "title": "Q1 2025 Reports",
  "order": 1,
  "hidden": false
}
```

| Field    | Default              | Description                                  |
|----------|----------------------|----------------------------------------------|
| `title`  | humanized folder name| Display name shown on the index              |
| `order`  | `999`                | Sort order (lower numbers appear first)      |
| `hidden` | `false`              | Set to `true` to hide the category entirely  |

---

## Security

- Security headers on all responses (`X-Frame-Options`, `X-Content-Type-Options`, `Referrer-Policy`)
- Rate limiting (20 req/s per IP, burst 40)
- No directory listing — the generated index is the only navigation
- `meta.json` files are blocked from being served directly
- Optional HTTP Basic Auth via `BASIC_AUTH` env var
- Nginx version not disclosed in headers or error pages

EasyHoster is designed for internal or small-team use. If you expose it publicly, use `BASIC_AUTH` or put it behind a reverse proxy that handles TLS.

---

## Common commands

```bash
# Start (foreground)
docker compose up --build

# Start (background)
docker compose up -d --build

# Stop
docker compose down

# View logs
docker compose logs -f

# Rebuild after code changes
docker compose build && docker compose up -d
```

---

## Project structure

```
easyhoster/
├── docker-compose.yml
├── .env.example
├── content/                  ← your HTML files go here
│   ├── presentations/
│   └── reports/
├── generator/
│   ├── generate.py           ← index builder + file watcher
│   ├── templates/
│   │   └── index.html.j2     ← index page template
│   └── Dockerfile
└── nginx/
    ├── nginx.conf
    ├── entrypoint.sh
    └── Dockerfile
```
