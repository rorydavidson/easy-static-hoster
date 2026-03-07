# Easy Static Hoster

A minimal self-hosted page for serving static HTML files — presentations, reports, notebooks — with an auto-generated index organised by folder.

Drop an HTML file into a folder. It appears on the index within seconds. No CMS, no database, no build step.

I created this after the number of artefacts that get created by different GenAI tools (Claude, Gemini, etc) as HTML files, and realised it would be handy to have a simple way to host them that is secure. Enjoy.

---

## How it works

Two Docker containers share a content directory on your host machine (two more are added in OIDC mode):

- **generator** — watches the content directory and rebuilds `index.html` whenever files change
- **nginx** — serves the index and all static files (HTML, images, CSS, etc.)
- **oauth2-proxy** *(OIDC mode only)* — handles SSO login via Keycloak, Google, Azure AD, etc.
- **redis** *(OIDC mode only)* — stores session data server-side so cookies stay small (required for users with many OIDC groups)

The index groups pages by top-level folder (each folder = one category) and shows the last-modified date beside each page name. Empty categories appear in the index immediately with a placeholder row — no file required.

---

## Requirements

- [Docker](https://docs.docker.com/get-docker/) with Compose (v2)

That's it. No other dependencies needed on the host.

---

## Quick start

Pre-built images are published to Docker Hub

```bash
git clone <this repo>
cd easyhoster
docker compose pull   # pulls rorydavidson/easy-static-hoster-nginx and -generator
docker compose up -d
```

Open [http://localhost:8080](http://localhost:8080). You'll see the example pages included in `content/`.

### Building locally

```bash
docker compose up --build
```

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

**Empty categories** are shown on the index immediately with a *"No pages yet"* placeholder. Upload a file or add one directly to make the placeholder disappear.

**Example / placeholder files** — any HTML file whose name begins with `_` (e.g. `_example.html`, `_getting-started.html`) is treated as a placeholder. It appears in the index only while the folder has no other HTML files. The moment a real page is added the `_` file disappears from the index automatically, though it is still served by nginx if linked to directly.

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

When authentication is configured (`BASIC_AUTH` or OIDC), an **Upload** button appears next to each category heading.

### How it works

1. Click **Upload** next to a category
2. **Basic Auth mode:** a credentials dialog appears — enter your username and password
3. **OIDC mode:** no credentials needed — your SSO session handles auth automatically
4. Choose a file from your computer
5. The file is uploaded into that category folder and the index refreshes automatically

If a file with the same name already exists it is replaced.

### Credentials on every upload (Basic Auth mode)

Credentials are asked for **on every upload**, not cached. The dialog is a custom UI element — the browser never sees a `WWW-Authenticate` challenge, so there is nothing for it to cache or auto-fill. The credentials are held in a short-lived JS closure for the duration of the single request and cleared immediately after, whether the upload succeeds or fails.

In OIDC mode, the oauth2-proxy session cookie handles authentication transparently — no credential prompt is shown.

### Restrictions

- Accepted file types: `.html`, `.png`, `.jpg`, `.jpeg`, `.gif`, `.svg`, `.webp`, `.ico`
- Maximum file size: 10 MB
- Files with non-ASCII characters in their names (e.g. em dashes) are handled correctly

---

## Creating categories

When authentication is configured (`BASIC_AUTH` or OIDC), a **+ New category** button appears in the top-right of the header.

### How it works

1. Click **+ New category**
2. **Basic Auth mode:** enter the category name, your username, and your password in one step
3. **OIDC mode:** enter only the category name — your SSO session handles auth
4. The folder is created and the index refreshes automatically

You can also create folders directly on the filesystem — they appear on the index within ~2 seconds and are immediately ready to accept uploads.

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
| `HEADER_COLOR` | `#16162a`     | Header background colour — any CSS colour value (e.g. `#2e7d32`, `darkslateblue`) |
| `OPEN_NEW_TAB` | `true`        | Open page links in a new tab — set to `false` to open in the same tab |
| `PORT`         | `8080`        | Host port to expose                                |
| `BASIC_AUTH`   | *(unset)*     | Credentials for upload — set to `username:password`. Also enables the upload and new-category buttons. |
| `AUTH_GLOBAL`  | *(unset)*     | Set to `true` to lock the **entire site** with the same credentials (requires `BASIC_AUTH`). |

**OIDC variables** (used with `docker-compose.oidc.yml` — mutually exclusive with `BASIC_AUTH`):

| Variable             | Default     | Description                                                  |
|----------------------|-------------|--------------------------------------------------------------|
| `OIDC_ISSUER_URL`   | *(unset)*   | OIDC provider URL (e.g. Keycloak realm URL)                  |
| `OIDC_CLIENT_ID`    | *(unset)*   | Client ID registered with your OIDC provider                 |
| `OIDC_CLIENT_SECRET` | *(unset)*  | Client secret from your OIDC provider                        |
| `COOKIE_SECRET`      | *(unset)*  | Session cookie encryption key — generate with `openssl rand -base64 24` |
| `OIDC_COOKIE_SECURE` | `false`    | Set to `true` when running behind TLS                        |
| `OIDC_ALLOWED_GROUP` | *(unset)*  | **Required.** OIDC group a user must belong to for access (e.g. `easyhoster-users`) |
| `OIDC_GROUPS_CLAIM`  | `groups`   | JWT claim containing the user's group list (change if your provider uses a different claim name) |

### Auth modes at a glance

| Mode | Env vars | Site | Upload / New category |
|------|----------|------|----------------------|
| No auth | *(none)* | public | hidden |
| Basic Auth | `BASIC_AUTH` | public (or locked with `AUTH_GLOBAL=true`) | credentials on every action |
| OIDC / SSO | `OIDC_ISSUER_URL` + client vars + `OIDC_ALLOWED_GROUP` | SSO login required (must be in allowed group) | session-based (no prompt) |

`BASIC_AUTH` and `OIDC_ISSUER_URL` are mutually exclusive — setting both is an error.

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

Example `.env` for OIDC / SSO (e.g. Keycloak):

```env
CONTENT_DIR=/data/reports
SITE_TITLE=Acme Reports
OIDC_ISSUER_URL=https://keycloak.example.com/realms/myrealm
OIDC_CLIENT_ID=easy-hoster
OIDC_CLIENT_SECRET=your-client-secret
COOKIE_SECRET=<output of: openssl rand -base64 24>
OIDC_COOKIE_SECURE=true
OIDC_ALLOWED_GROUP=easyhoster-users
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
- Both containers run as non-root users
- **Upload auth (Basic Auth)**: credentials validated server-side on every request via `Authorization: Basic` header — the browser never issues a `WWW-Authenticate` challenge so credentials are never cached
- **Global auth (Basic Auth)**: set `AUTH_GLOBAL=true` to lock the entire site behind HTTP Basic Auth (nginx-enforced)
- **OIDC / SSO**: oauth2-proxy handles the login flow via Keycloak, Google, Azure AD, or any OIDC-compatible provider — session-based, no credentials in the browser

EasyHoster is designed for internal or small-team use. If you expose it publicly, use `AUTH_GLOBAL=true`, enable OIDC, or put it behind a reverse proxy that handles TLS.

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

## OIDC / SSO authentication

Use the `docker-compose.oidc.yml` overlay to protect the entire site with an OIDC provider such as [Keycloak](https://www.keycloak.org/), Google, or Azure AD.

### How it works

An [oauth2-proxy](https://oauth2-proxy.github.io/oauth2-proxy/) container sits in front of nginx. Unauthenticated users see a branded sign-in page with the site logo and a **Sign in** button. Clicking it redirects to your OIDC provider to log in. After login, oauth2-proxy checks that the user belongs to the required group (`OIDC_ALLOWED_GROUP`) and proxies requests to nginx with the user's identity in `X-Forwarded-User` / `X-Forwarded-Email` headers. Users who authenticate but are not in the allowed group are denied access. Upload and category creation work without a credential prompt — the SSO session handles auth.

### Provider setup (Keycloak example)

1. Create a realm (or use an existing one)
2. Go to **Clients** → **Create client**:
   - **Client ID:** `easy-hoster` (or any name)
   - **Client type:** `OpenID Connect`
   - **Client authentication:** **ON** (this makes it a confidential client with a secret)
   - **Valid Redirect URIs:** `http(s)://<your-host>/oauth2/callback`
3. Go to the **Credentials** tab and copy the **Client Secret**
4. Create a **group** (e.g. `easyhoster-users`) under **Groups** and add the users who should have access
5. Add a groups mapper to the client's **dedicated scope** (this ensures the `groups` claim is always included in the ID token):
   - Go to **Clients** → your client → **Client Scopes** tab
   - Click on the **dedicated scope** (named `easy-hoster-dedicated` — it matches your client ID)
   - Click **Configure a new mapper** (or **Add mapper** → **By configuration**)
   - Choose **Group Membership**
   - Set **Name** to `groups`, **Token Claim Name** to `groups`
   - Turn **OFF** "Full group path" (so groups appear as `easyhoster-users`, not `/easyhoster-users`)
   - Ensure **Add to ID token** is **ON**
   - Click **Save**

### `.env` additions

```env
OIDC_ISSUER_URL=https://keycloak.example.com/realms/myrealm
OIDC_CLIENT_ID=easy-hoster
OIDC_CLIENT_SECRET=your-client-secret
COOKIE_SECRET=<output of: openssl rand -base64 24>
OIDC_COOKIE_SECURE=true   # set false for local development without TLS
OIDC_ALLOWED_GROUP=easyhoster-users
```

### Start with the overlay

```bash
docker compose -f docker-compose.yml -f docker-compose.oidc.yml up -d --build
```

In OIDC mode, nginx is not exposed to the host — all traffic goes through oauth2-proxy on the configured `PORT` (default `4180`).

### OIDC + nginx-proxy

If you also run behind nginx-proxy, use the additional `docker-compose.oidc-nginx-proxy.yml` overlay. This routes nginx-proxy traffic to oauth2-proxy (not directly to nginx), so the OIDC login flow is enforced.

```bash
docker compose \
  -f docker-compose.yml \
  -f docker-compose.oidc.yml \
  -f docker-compose.oidc-nginx-proxy.yml \
  up -d --build
```

Add `VIRTUAL_HOST` to `.env` as with a normal nginx-proxy deployment:

```env
VIRTUAL_HOST=reports.example.com
```

> **Note:** Do not combine `docker-compose.nginx-proxy.yml` with `docker-compose.oidc.yml` directly — use `docker-compose.oidc-nginx-proxy.yml` instead, which correctly routes nginx-proxy traffic through oauth2-proxy.

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
├── docker-compose.oidc.yml              ← overlay for OIDC / SSO
├── docker-compose.oidc-nginx-proxy.yml  ← overlay for OIDC + nginx-proxy
├── docker-compose.nginx-proxy.yml       ← overlay for nginx-proxy (no OIDC)
├── .env.example
├── content/                        ← your HTML files go here
│   ├── shortlinks.json             ← short link mappings (auto-created)
│   ├── presentations/
│   └── reports/
├── generator/
│   ├── generate.py                 ← index builder + file watcher
│   ├── shortlinks_server.py        ← /s/<code> redirects + upload + mkdir APIs
│   ├── entrypoint.sh               ← fixes volume ownership, drops to non-root
│   ├── templates/
│   │   └── index.html.j2           ← index page template
│   └── Dockerfile
├── nginx/
│   ├── nginx.conf
│   ├── favicon.ico                 ← baked into the image
│   ├── entrypoint.sh               ← writes auth config, starts nginx
│   └── Dockerfile
└── oauth2-proxy/
    └── sign_in.html                ← branded OIDC sign-in page template
```
