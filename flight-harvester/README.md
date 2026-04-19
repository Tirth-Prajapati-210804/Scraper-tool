# Flight Price Tracker

Automated flight price collection platform for Viva Vista Vacations. Tracks the cheapest daily flight prices across configurable routes and exports them as formatted Excel spreadsheets — replacing the manual Skyscanner / Kayak process previously done by hand.

---

## Table of Contents

1. [What does it do?](#what-does-it-do)
2. [How it works](#how-it-works)
3. [Prerequisites](#prerequisites)
4. [Option A — Run with Docker (recommended)](#option-a--run-with-docker-recommended)
5. [Option B — Run locally without Docker](#option-b--run-locally-without-docker)
6. [Logging in](#logging-in)
7. [Running your first collection](#running-your-first-collection)
8. [Downloading the Excel file](#downloading-the-excel-file)
9. [Configuration reference](#configuration-reference)
10. [Deployment to the cloud](#deployment-to-the-cloud)
11. [Troubleshooting](#troubleshooting)
12. [Developer reference](#developer-reference)

---

## What does it do?

Flight Price Tracker replaces the manual process of:

1. Opening Skyscanner or Kayak
2. Searching each origin → destination for every future date
3. Copying the cheapest price into an Excel spreadsheet

The tool does all of that automatically, every hour, and saves the results to a database. You can download a formatted Excel file at any time with one click.

**Example output** (one row per day, one sheet per origin airport):

| Date       | Dep Airport | Arrivel Airport | Night | Airline | Flight Price |
|------------|-------------|-----------------|-------|---------|--------------|
| 2026-05-01 | YYZ         | TYO/SHA         | 12    | AC      | 1850         |
| 2026-05-02 | YYZ         | TYO/SHA         | 12    | CX      | 1620         |

Prices are in **CAD**. Airline codes are standard IATA codes (e.g. `AC` = Air Canada, `CX` = Cathay Pacific).

---

## How it works

```
Every 60 minutes (automatic):
  1. Check which route groups are active (e.g. "Canada → Tokyo/Shanghai")
  2. For each origin (YYZ, YVR, YEG, …) and each future date up to days_ahead:
       → Ask SerpAPI Google Flights for the cheapest price
       → Skip dates where ALL destinations are already collected
       → Save the cheapest result to the database
  3. Log every search attempt (success / error / no results)

On demand (manual):
  → Click "Trigger collection" on the dashboard to run immediately
  → Click "Download Excel" to download the current data as a spreadsheet
```

The only flight data provider is **SerpAPI Google Flights** — it mirrors the prices shown on google.com/flights in real time.

---

## Prerequisites

### Option A — Docker (easiest)

- **Docker Desktop** — https://www.docker.com/products/docker-desktop/
  - Windows / Mac: install and make sure it is running (whale icon in the taskbar/menu bar)
  - Linux: `sudo apt-get install docker.io docker-compose-plugin`
- A **SerpAPI key** — sign up at https://serpapi.com (free plan: ~100 searches/month)

### Option B — Local development

- **Python 3.11+** — https://www.python.org/downloads/
- **Node.js 20+** — https://nodejs.org/en/download (choose LTS)
- **PostgreSQL 15+** — https://www.postgresql.org/download/
- A **SerpAPI key** — https://serpapi.com

---

## Option A — Run with Docker (recommended)

> You do not need to install Python, Node, or PostgreSQL. Docker handles everything.

### Step 1 — Clone the repository

```bash
git clone https://github.com/tirth-prajapati-210804/scraper-tool.git
cd scraper-tool/flight-harvester
```

### Step 2 — Create the environment file

```bash
cp backend/.env.example backend/.env
```

Open `backend/.env` in any text editor and fill in these values:

```dotenv
JWT_SECRET_KEY=any-long-random-string-here      # e.g. run: openssl rand -hex 32
ADMIN_EMAIL=admin@example.com
ADMIN_PASSWORD=choose-a-strong-password-12-chars-min

SERPAPI_KEY=your-serpapi-key-here
```

### Step 3 — Start everything

```bash
docker compose up --build
```

The first run downloads images and builds containers — takes 3–5 minutes. When you see:

```
backend-1  | INFO: Application startup complete.
frontend-1 | Configuration complete; ready for start up
```

the system is ready.

### Step 4 — Seed the route groups

Open a new terminal (leave `docker compose up` running) and run:

```bash
docker compose exec backend python -m app.scripts.seed_route_groups
```

Output:
```
  CREATE CAD-Tokyo-Shanghai-CAD
  CREATE CAN-DPS

Done — 2 created, 0 skipped.
```

This creates the two pre-configured routes:
- **CAD-Tokyo-Shanghai-CAD** — 7 Canadian cities → Tokyo/Shanghai, 12 nights, 365 days ahead
- **CAN-DPS** — 7 Canadian cities → Bali (DPS), 11 nights, 306 days ahead

### Step 5 — Open the dashboard

- **Dashboard:** http://localhost:80
- **API docs (Swagger):** http://localhost:8000/docs

Log in with the email and password from your `.env`.

### Stopping

```bash
docker compose down          # stop containers, keep data
docker compose down -v       # stop and delete all data (database wiped)
```

---

## Option B — Run locally without Docker

### Step 1 — Clone the repository

```bash
git clone https://github.com/tirth-prajapati-210804/scraper-tool.git
cd scraper-tool/flight-harvester
```

### Step 2 — Create the PostgreSQL database

```bash
# Linux / Mac:
psql -U postgres -c "CREATE DATABASE flight_price_tracker;"

# Windows — open "SQL Shell (psql)" from the Start menu and run:
CREATE DATABASE flight_price_tracker;
```

### Step 3 — Set up the backend

```bash
cd backend

# Install Python dependencies
pip install -e ".[dev]"

# Create environment file
cp .env.example .env
```

Edit `.env` with at minimum:

```dotenv
DATABASE_URL=postgresql+asyncpg://postgres:YOUR_PASSWORD@localhost:5432/flight_price_tracker
JWT_SECRET_KEY=any-long-random-string-here
ADMIN_EMAIL=admin@example.com
ADMIN_PASSWORD=choose-a-strong-password-12-chars-min

SERPAPI_KEY=your-serpapi-key-here
```

### Step 4 — Run database migrations

```bash
python -m alembic upgrade head
```

### Step 5 — Seed the route groups

```bash
python -m app.scripts.seed_route_groups
```

### Step 6 — Start the backend

```bash
uvicorn app.main:app --reload
```

API is running at http://localhost:8000. Keep this terminal open.

### Step 7 — Set up the frontend

Open a **new terminal**:

```bash
cd scraper-tool/flight-harvester/frontend

npm install
npm run dev
```

Dashboard is at http://localhost:5173.

---

## Logging in

1. Open http://localhost:80 (Docker) or http://localhost:5173 (local dev)
2. Enter the `ADMIN_EMAIL` and `ADMIN_PASSWORD` from your `.env`
3. You land on the dashboard

---

## Running your first collection

### Manual trigger (immediate)

1. Go to **Dashboard**
2. Click **"Trigger collection"** in the top-right, or click the refresh icon on a specific route group card
3. Watch the progress — each origin/date is scraped one by one
4. Check **Collection Logs** for per-route results

### Automatic collection

The scheduler runs automatically every **60 minutes** in the background. It collects prices for all active route groups and skips dates where all destinations are already collected today. No action needed — just leave the server running.

You can see every run in **Collection Logs**.

---

## Downloading the Excel file

1. Go to **Dashboard** (or the route group detail page)
2. Click **"Download Excel"**
3. The file downloads immediately

**Excel format:**
- One sheet per origin airport (e.g. `YYZ`, `YVR`)
- Columns: `Date | Dep Airport | Arrivel Airport | Night | Airline | Flight Price`
- One row per departure date, sorted by date
- Prices in whole numbers (CAD)
- Empty cells for dates with no data yet

Special sheets (e.g. a combined view) use 4 columns: `Date | Dep Airport | Arrivel Airport | Flight Price`.

---

## Configuration reference

All settings go in `backend/.env`:

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DATABASE_URL` | Yes | — | PostgreSQL async connection string (`postgresql+asyncpg://...`) |
| `JWT_SECRET_KEY` | Yes | — | Secret for auth tokens — min 32 chars. Use `openssl rand -hex 32`. |
| `ADMIN_EMAIL` | Yes | — | Login email for the admin account |
| `ADMIN_PASSWORD` | Yes | — | Login password — min 12 chars |
| `ADMIN_FULL_NAME` | No | `System Admin` | Display name in the sidebar |
| `SERPAPI_KEY` | Yes* | — | SerpAPI key from serpapi.com |
| `DEMO_MODE` | No | `false` | Generate fake prices locally without any API key. For demos/testing only. |
| `DEBUG` | No | `false` | Show detailed error messages in API responses |
| `CORS_ORIGINS` | No | `["http://localhost:5173"]` | Frontend URLs allowed to call the API |
| `SCHEDULER_ENABLED` | No | `true` | Enable automatic hourly collection |
| `SCHEDULER_INTERVAL_MINUTES` | No | `60` | How often the scheduler runs |
| `SCRAPE_BATCH_SIZE` | No | `10` | Dates scraped per batch |
| `SCRAPE_DELAY_SECONDS` | No | `1.0` | Pause between batches to avoid rate limiting |
| `SERPAPI_DEEP_SEARCH` | No | `true` | Mirror exact Google Flights browser prices (slower, ~20s/search). Set `false` for faster collection. |
| `TELEGRAM_BOT_TOKEN` | No | — | Telegram bot token for run notifications |
| `TELEGRAM_CHAT_ID` | No | — | Telegram chat/channel ID |
| `SENTRY_DSN` | No | — | Sentry error tracking DSN |

*`SERPAPI_KEY` is technically optional (the server starts without it) but without it no prices will be collected. Use `DEMO_MODE=true` to generate fake data for testing.

### Telegram notifications (optional)

To receive a Telegram message after each collection cycle:

1. Message `@BotFather` on Telegram → `/newbot` → get a token
2. Add the bot to your channel/group and get the chat ID
3. Add to `.env`:
   ```dotenv
   TELEGRAM_BOT_TOKEN=123456789:AAF...
   TELEGRAM_CHAT_ID=-1001234567890
   ```

---

## Deployment to the cloud

### Backend → Railway

1. Go to https://railway.app → **New Project → Deploy from GitHub repo**
2. Select this repository, set **Root Directory** to `flight-harvester/backend`
3. Add a **PostgreSQL** plugin to the project
4. Set all required environment variables in the **Variables** tab
5. Railway auto-starts the server — note your public URL

### Frontend → Vercel

1. Go to https://vercel.com → **New Project → Import Git Repository**
2. Select this repository, set **Root Directory** to `flight-harvester/frontend`
3. Add environment variable: `VITE_API_BASE_URL=https://your-backend.up.railway.app`
4. Click Deploy
5. Update `CORS_ORIGINS` in your Railway backend to include your Vercel URL

---

## Troubleshooting

### "Cannot connect to PostgreSQL" / "Connection refused"

```bash
pg_isready                          # check if postgres is running
sudo service postgresql start       # start it (Linux)
brew services start postgresql      # start it (Mac)
```

If using Docker, make sure `docker compose up` is still running in another terminal.

---

### "No active route groups" in the logs

The seed script was not run. Fix:

```bash
# Docker:
docker compose exec backend python -m app.scripts.seed_route_groups

# Local dev (inside backend/):
python -m app.scripts.seed_route_groups
```

---

### "No providers enabled" in the logs

`SERPAPI_KEY` is empty in `.env`. Add your key and restart. Alternatively, set `DEMO_MODE=true` to use locally-generated fake prices for testing.

```bash
docker compose down && docker compose up
```

---

### "Invalid credentials" on login

The admin account is created once on first startup using `ADMIN_EMAIL` and `ADMIN_PASSWORD`. If you change the password in `.env` after the first run, the stored hash will not update automatically.

Fix — wipe and recreate the database:

```bash
# Docker:
docker compose down -v
docker compose up --build
docker compose exec backend python -m app.scripts.seed_route_groups

# Local dev:
psql -U postgres -c "DROP DATABASE flight_price_tracker;"
psql -U postgres -c "CREATE DATABASE flight_price_tracker;"
cd backend && python -m alembic upgrade head && python -m app.scripts.seed_route_groups
```

---

### "0 prices collected" after a collection run

Check **Collection Logs** — each row shows the exact error. Common causes:

- **`SERPAPI_KEY` invalid or missing** — check your key at serpapi.com, or set `DEMO_MODE=true`
- **Rate limited (429)** — increase `SCRAPE_DELAY_SECONDS` in `.env`
- **SerpAPI quota exhausted** — free plan is ~100 searches/month; upgrade or wait for reset

---

### Docker build fails / "no space left on device"

```bash
docker system prune -f
docker compose up --build
```

---

### Port 80 or 8000 already in use

Edit `docker-compose.yml` and change the host port:

```yaml
# Change "80:80" to "8080:80" to use port 8080 instead
ports: ["8080:80"]
```

---

## Developer reference

### Project structure

```
flight-harvester/
├── backend/                         # FastAPI + SQLAlchemy + PostgreSQL
│   ├── app/
│   │   ├── api/v1/routes/           # auth, route_groups, prices, collection, stats
│   │   ├── core/                    # config, security, logging
│   │   ├── db/                      # session factory, base model
│   │   ├── models/                  # SQLAlchemy ORM models
│   │   ├── providers/
│   │   │   ├── base.py              # ProviderResult dataclass
│   │   │   ├── serpapi.py           # SerpAPI Google Flights scraper
│   │   │   └── registry.py          # Builds provider list from settings
│   │   ├── schemas/                 # Pydantic request/response models
│   │   ├── scripts/
│   │   │   └── seed_route_groups.py # Seeds default Canada routes
│   │   ├── services/
│   │   │   ├── price_collector.py   # Orchestrates scraping per route/date
│   │   │   ├── export_service.py    # Generates Excel files with openpyxl
│   │   │   └── alert_service.py     # Telegram / Sentry notifications
│   │   └── tasks/
│   │       └── scheduler.py         # APScheduler — runs collection every N minutes
│   ├── alembic/                     # Database migrations
│   ├── tests/
│   │   ├── test_config.py           # Settings validator unit tests
│   │   ├── test_airline_codes.py    # Airline normalization unit tests
│   │   ├── test_auth_schema.py      # Auth schema unit tests
│   │   ├── test_providers/          # Provider unit tests (mock HTTP)
│   │   ├── test_services/           # Service unit tests (mock DB)
│   │   └── integration/             # HTTP integration tests (real PostgreSQL)
│   ├── .env.example                 # Environment variable template
│   └── pyproject.toml               # Python dependencies + pytest config
└── frontend/                        # React 19 + TypeScript + Tailwind CSS
    ├── src/
    │   ├── api/                     # Typed Axios wrappers
    │   ├── components/              # Reusable UI components
    │   ├── context/                 # AuthContext, ToastContext
    │   ├── pages/                   # Dashboard, RouteGroupDetail, DataExplorer, Logs
    │   └── types/                   # TypeScript interfaces
    ├── e2e/                         # Playwright end-to-end tests
    └── src/**/*.test.{ts,tsx}       # Vitest unit tests
```

### CI/CD

GitHub Actions runs three jobs on every push:

| Job | What it checks |
|-----|---------------|
| **Backend Tests** | `pytest tests/` (unit) + `pytest tests/integration/` (against real PostgreSQL service) |
| **Frontend Checks** | `tsc --noEmit` + `eslint` + `vitest run` |
| **E2E Tests** | Playwright — login, dashboard, collection trigger, Excel download (all APIs mocked) |

### API endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v1/auth/login` | Login, returns JWT token |
| `GET`  | `/api/v1/auth/me` | Current user info |
| `GET`  | `/api/v1/route-groups/` | List all route groups |
| `POST` | `/api/v1/route-groups/` | Create a route group |
| `GET`  | `/api/v1/route-groups/{id}` | Get a single route group |
| `PUT`  | `/api/v1/route-groups/{id}` | Update a route group |
| `DELETE` | `/api/v1/route-groups/{id}` | Delete a route group |
| `GET`  | `/api/v1/route-groups/{id}/progress` | Coverage % and date calendar data |
| `GET`  | `/api/v1/route-groups/{id}/export` | Download Excel file |
| `POST` | `/api/v1/collection/trigger` | Trigger a full collection immediately |
| `POST` | `/api/v1/collection/trigger/{group_id}` | Trigger collection for one route group |
| `POST` | `/api/v1/collection/stop` | Stop a running collection |
| `GET`  | `/api/v1/collection/runs` | Collection run history |
| `GET`  | `/api/v1/collection/logs` | Individual scrape log entries |
| `GET`  | `/api/v1/prices/` | Query collected prices |
| `GET`  | `/api/v1/prices/trend` | Cheapest-per-date trend for a route |
| `GET`  | `/api/v1/stats/overview` | Dashboard summary stats |
| `GET`  | `/health` | Health check + provider status |

Full interactive docs: http://localhost:8000/docs

### Running tests

```bash
# Backend — unit tests only (no DB needed)
cd backend
pytest tests/ --ignore=tests/integration -v

# Backend — all tests including integration (requires PostgreSQL)
createdb flight_test   # one-time setup
pytest tests/ -v

# Frontend — unit tests
cd frontend
npm run test:run

# Frontend — E2E tests (starts dev server automatically)
npm run e2e
```

### Makefile shortcuts

```bash
make dev        # docker compose up --build
make down       # docker compose down
make test       # run pytest (unit tests)
make lint       # ruff check app/
make migrate    # alembic upgrade head
make revision msg="describe change"   # create new migration
```

### Adding a new route group via the seed script

Edit `backend/app/scripts/seed_route_groups.py` and add a new group dict:

```python
GROUP_3 = {
    "name": "CAN-LHR",
    "destination_label": "LHR",
    "destinations": ["LHR"],
    "origins": ["YYZ", "YVR"],
    "nights": 10,
    "days_ahead": 180,
    "sheet_name_map": {
        "YYZ": "YYZ-LHR",
        "YVR": "YVR-LHR",
    },
    "special_sheets": [],
}
```

Then run `python -m app.scripts.seed_route_groups` again (existing groups are skipped).

### Creating a database migration

After changing a SQLAlchemy model:

```bash
cd backend
python -m alembic revision --autogenerate -m "describe your change"
python -m alembic upgrade head
```
