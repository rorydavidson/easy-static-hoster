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

**Page titles** are read from the HTML `<title>` tag inside each file. If no `<title>` is found, the filename is humanised as a fallback: `my-report-2025.html` → **My Report 2025**.

---

## Short links

Every page on the index can have a short, memorable URL — e.g. `/s/q1` instead of `/presentations/Q1 2025 Review.html`.

### Creating or editing a short link

Click the **chain-link icon** (🔗) that appears on the right of any row when you hover over it. A small popover opens:

1. Type a code — lowercase letters, digits, hyphens, and underscores only (e.g. `q1`, `annual-report`, `demo_2025`)
2. Click **Save** — the badge `/s/your-code` appears on the row immediately

The change is written to `shortlinks.json` in your content directory with no restart needed.

### Copying a short link

Click the `/s/code` badge on any row to copy the full URL to your clipboard. The badge flashes green to confirm.

### Removing a short link

Open the popover with the chain-link icon and click **Remove**.

### Short link rules

| Rule | Detail |
|------|--------|
| Starts with a letter or digit | No leading hyphens/underscores |
| Lowercase only | Uppercase is auto-lowercased in the popover |
| 1–50 characters | Letters `a–z`, digits `0–9`, `-`, `_` |
| One code per page | Saving a new code replaces the old one |
| Codes are unique | A code already used by another page is rejected |

### Direct URL

```
https://your-host/s/my-code  →  302  →  the full page URL
```

Short link mappings are stored in `content/shortlinks.json` and survive container restarts.

---

## Uploading files

When `BASIC_AUTH` is set, an **Upload** button appears next to each category heading.

### How it works

1. Click **Upload** next to a category
2. A credentials dialog appears — enter your username and password
3. Choose an `.html` file from your computer
4. The file is uploaded into that category folder and the index refreshes automatically

If a file with the same name already exists it is replaced.

### Credentials on every upload

Credentials are asked for **on every upload**, not cached. The dialog is a custom UI element — the browser never sees a `WWW-Authenticate` challenge, so there is nothing for it to cache or auto-fill. The credentials are held in a short-lived JS variable for the duration of the single request and cleared immediately after, whether the upload succeeds or fails.

### Restrictions

- Only `.html` files are accepted
- Maximum file size: 10 MB
- Files can only be uploaded into existing category folders — new folders must be created on the filesystem

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
| `BASIC_AUTH`   | *(unset)*     | Credentials for upload — set to `username:password`. Also enables the upload button. |
| `AUTH_GLOBAL`  | *(unset)*     | Set to `true` to lock the **entire site** with the same credentials (requires `BASIC_AUTH`). |

### Auth modes at a glance

| `BASIC_AUTH` | `AUTH_GLOBAL` | Site | Upload button | Upload auth |
|---|---|---|---|---|
| unset | — | public | hidden | — |
| set | unset | public | shown | required on every upload |
| set | `true` | 🔒 login required | shown | required on every upload |

Example `.env` for a team reports site (public browsing, upload protected):

```env
CONTENT_DIR=/data/reports
SITE_TITLE=Acme Reports
PORT=8080
BASIC_AUTH=admin:correct-horse-battery-staple
```

Example `.env` for a fully locked-down site:

```env
CONTENT_DIR=/data/reports
SITE_TITLE=Acme Reports
BASIC_AUTH=admin:correct-horse-battery-staple
AUTH_GLOBAL=true
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
- Rate limiting (20 req/s per real client IP, burst 40)
- No directory listing — the generated index is the only navigation
- `meta.json` files are blocked from being served directly
- Nginx version not disclosed in headers or error pages
- **Upload auth**: credentials validated server-side on every request via `Authorization: Basic` header — the browser never issues a `WWW-Authenticate` challenge so credentials are never cached
- **Global auth**: set `AUTH_GLOBAL=true` to lock the entire site behind HTTP Basic Auth (nginx-enforced)

EasyHoster is designed for internal or small-team use. If you expose it publicly, use `AUTH_GLOBAL=true` or put it behind a reverse proxy that handles TLS.

---

## Running behind a reverse proxy (nginx-proxy)

Use the included `docker-compose.nginx-proxy.yml` override when running behind [nginx-proxy](https://github.com/nginx-proxy/nginx-proxy).

### One-time setup

```bash
# Create the shared network that nginx-proxy uses (once per host)
docker network create nginx-proxy
```

### `.env` additions

```env
VIRTUAL_HOST=reports.example.com

# Optional — auto-TLS with acme-companion
# LETSENCRYPT_HOST=reports.example.com
# LETSENCRYPT_EMAIL=you@example.com
```

### Start with the overlay

```bash
docker compose -f docker-compose.yml -f docker-compose.nginx-proxy.yml up -d --build
```

### What the overlay does

| Change | Why |
|--------|-----|
| Adds `VIRTUAL_HOST` / `VIRTUAL_PORT` env vars to the nginx service | nginx-proxy reads these to know which hostname maps to which container |
| Attaches the nginx container to the shared `nginx-proxy` Docker network | nginx-proxy can only route to containers it can reach on its network |

### What's already handled for you

- **Short link redirects** issue relative `Location` headers (`/presentations/file.html`), so the browser resolves them against the public URL — no changes needed.
- **The copy-to-clipboard button** uses `window.location.origin` (browser-side), which already knows the public scheme and hostname — no changes needed.
- **Rate limiting** uses the real client IP via `X-Forwarded-For` (configured in `nginx.conf`) — not the proxy's container IP.

> **Note:** The `PORT` host-port mapping stays active even when behind nginx-proxy (nginx-proxy routes via the Docker network, not the published port). You can set `PORT=127.0.0.1:8080` in `.env` to restrict direct access to localhost only.

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
├── docker-compose.nginx-proxy.yml  ← overlay for nginx-proxy deployments
├── .env.example
├── content/                        ← your HTML files go here
│   ├── shortlinks.json             ← short link mappings (auto-created)
│   ├── presentations/
│   └── reports/
├── generator/
│   ├── generate.py                 ← index builder + file watcher
│   ├── shortlinks_server.py        ← /s/<code> redirect + /api/shortlinks API
│   ├── templates/
│   │   └── index.html.j2           ← index page template
│   └── Dockerfile
└── nginx/
    ├── nginx.conf
    ├── entrypoint.sh
    └── Dockerfile
```
