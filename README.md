# Snip: URL Shortener

A URL shortener built with **Django**, **SQL** (SQLite by default, PostgreSQL-ready), and a vanilla **JavaScript / HTML / CSS** frontend.

## Features
- Shorten any http(s) URL to a 6-character code, or pick your own alias
- Optional link expiry (1 to 365 days); expired links return `410 Gone`
- Click analytics: total clicks, last opened, and a 7-day chart per link
- Input validation and proper status codes (201, 400, 404, 409, 410, 429)
- Per-IP rate limiting on link creation (20 per minute, configurable)
- CSRF-protected JSON API, admin panel, 13 automated tests
- Dockerfile for deployment

## Run it locally
```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```
Open http://127.0.0.1:8000

Optional: `python manage.py createsuperuser`, then visit `/admin/` to browse links and clicks.

## Tests
```bash
python manage.py test
```

## API
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/shorten` | Body: `{"url": "...", "alias": "optional", "expires_in_days": 7}`. Returns `201` with the short URL. |
| GET | `/<code>` | Redirects (302) to the original URL and records the click. |
| GET | `/api/stats/<code>` | Click count, last accessed, expiry, and clicks for the last 7 days. |

The POST endpoint requires a CSRF token (`X-CSRFToken` header), which the bundled frontend sends automatically.

## Project layout
```
config/                 settings, root URLs, WSGI
shortener/
  models.py             Link and Click tables
  views.py              shorten, redirect, stats endpoints
  utils.py              code generation, validation, rate limiting
  tests.py              test suite
templates/shortener/    index.html, notice.html (404 / expired)
static/shortener/       style.css, app.js
```

## Deploy (Render, Railway, Fly.io)
Use the included Dockerfile and set these environment variables:
```
DJANGO_SECRET_KEY=<long random string>
DJANGO_DEBUG=0
DJANGO_ALLOWED_HOSTS=your-app.onrender.com
DJANGO_CSRF_TRUSTED_ORIGINS=https://your-app.onrender.com
```
SQLite data is lost when a container redeploys. For a real deployment, attach a persistent disk or switch `DATABASES` in `config/settings.py` to PostgreSQL (`pip install psycopg[binary]`). The rate limiter uses in-process memory; use Redis as the cache backend if you run several workers.

## Design notes
- Codes are generated with `secrets.choice` over 62 characters (about 56 billion combinations), with retries on the unique-constraint collision.
- Click counts use an `F()` expression, so concurrent visits update the counter atomically in SQL.
- Redirects use 302 rather than 301 so browsers don't cache them and skip the click counter.
