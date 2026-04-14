# Flight Harvester

Automated flight price collection platform. Tracks the cheapest daily flight prices across multiple origin-destination routes and exports them as formatted Excel spreadsheets — the same format you used to fill in by hand on Skyscanner and Kayak.

---

## Table of Contents

1. [What does it do?](#what-does-it-do)
2. [How it works (plain English)](#how-it-works-plain-english)
3. [What you need before starting](#what-you-need-before-starting)
4. [Option A — Run with Docker (recommended, easiest)](#option-a--run-with-docker-recommended-easiest)
5. [Option B — Run locally without Docker](#option-b--run-locally-without-docker)
6. [Logging in to the dashboard](#logging-in-to-the-dashboard)
7. [Running your first collection](#running-your-first-collection)
8. [Downloading the Excel file](#downloading-the-excel-file)
9. [Adding real API keys (paid providers)](#adding-real-api-keys-paid-providers)
10. [Configuration reference](#configuration-reference)
11. [Deployment to the cloud](#deployment-to-the-cloud)
12. [Troubleshooting](#troubleshooting)
13. [Developer reference](#developer-reference)

---

## What does it do?

Flight Harvester replaces the manual process of:

1. Opening Skyscanner or Kayak
2. Searching each origin → destination for every date
3. Copying the cheapest price into an Excel spreadsheet

The tool does all of that automatically, every hour, and saves the results into a database. You can then download a formatted Excel file at any time with one click.

**Example output** (one row per day, one sheet per origin airport):

| Date       | Dep Airport | Arrivel Airport | Night | Airline | Flight Price |
|------------|-------------|-----------------|-------|---------|-------------|
| 2026-05-01 | YYZ         | TYO/SHA         | 12    | AC      | 850         |
| 2026-05-02 | YYZ         | TYO/SHA         | 12    | CX      | 920         |

---

## How it works (plain English)

```
Every 60 minutes:
  1. Check which route groups are active (e.g. "Canada → Tokyo/Shanghai")
  2. For each origin airport (YYZ, YVR, YEG, …) and each future date:
       → Ask the flight APIs for the cheapest price
       → Save only the single cheapest result to the database
  3. Keep a log of every search attempt (success, error, no results)

On demand:
  → Download an Excel file with all collected prices, formatted to spec
```

---

## What you need before starting

### Option A — Docker (easiest)

- **Docker Desktop** — download from https://www.docker.com/products/docker-desktop/
  - On Windows: install Docker Desktop, then make sure it is running (whale icon in the taskbar)
  - On Mac: install Docker Desktop, then make sure it is running (whale icon in the menu bar)
  - On Linux: install Docker Engine (`sudo apt-get install docker.io docker-compose-plugin`)
- That's it. Docker handles Python, Node, and PostgreSQL automatically.

### Option B — Local development

- **Python 3.11 or newer** — https://www.python.org/downloads/
  - On Windows: run the installer, tick "Add Python to PATH"
  - On Mac: `brew install python@3.11` or use the installer from python.org
- **Node.js 18 or newer** — https://nodejs.org/en/download (choose LTS)
- **PostgreSQL 15 or newer** — https://www.postgresql.org/download/
  - Remember the username and password you set during installation
- **Git** — https://git-scm.com/downloads (to clone the repository)

---

## Option A — Run with Docker (recommended, easiest)

> This is the recommended way. You do not need to install Python, Node, or PostgreSQL separately.

### Step 1 — Get the code

```bash
git clone https://github.com/tirth-prajapati-210804/scraper-tool.git
cd scraper-tool/flight-harvester
```

### Step 2 — Create the environment file

```bash
cp backend/.env.example backend/.env
```

Open `backend/.env` in any text editor (Notepad, VS Code, TextEdit) and set these three values:

```dotenv
JWT_SECRET_KEY=any-long-random-string-change-this     # e.g. "my-super-secret-key-12345"
ADMIN_EMAIL=admin@yourdomain.com
ADMIN_PASSWORD=choose-a-strong-password
```

> **Trial run without paid API keys?** Add this line to enable fake flight data:
> ```dotenv
> MOCK_PROVIDER_KEY=mock-trial-run
> ```
> This lets you verify the full pipeline — collection → database → Excel export — without spending anything.

### Step 3 — Start everything

```bash
docker compose up --build
```

The first time this runs it will download images and build the containers. This takes 2–5 minutes. You will see a lot of output — that is normal.

When you see lines like:
```
backend-1   | INFO: Application startup complete.
frontend-1  | /docker-entrypoint.sh: Configuration complete; ready for start up
```
...the system is ready.

### Step 4 — Open the dashboard

- **Dashboard:** http://localhost:80
- **API documentation:** http://localhost:8000/docs

Log in with the email and password you set in `.env`.

### Stopping

```bash
docker compose down
```

To also delete all collected data (the database):

```bash
docker compose down -v
```

---

## Option B — Run locally without Docker

### Step 1 — Get the code

```bash
git clone https://github.com/tirth-prajapati-210804/scraper-tool.git
cd scraper-tool/flight-harvester
```

### Step 2 — Set up PostgreSQL

Create a database for the app. Open a terminal and run:

```bash
# On Linux/Mac:
psql -U postgres -c "CREATE DATABASE flight_harvester;"

# On Windows (open "SQL Shell (psql)" from the Start menu):
CREATE DATABASE flight_harvester;
```

### Step 3 — Set up the backend

```bash
cd backend

# Install Python dependencies
pip install -e ".[dev]"

# Create the environment file
cp .env.example .env
```

Edit `.env` and fill in all required values (see [Configuration reference](#configuration-reference) below). At minimum:

```dotenv
DATABASE_URL=postgresql+asyncpg://postgres:YOUR_PASSWORD@localhost:5432/flight_harvester
JWT_SECRET_KEY=any-long-random-string-change-this
ADMIN_EMAIL=admin@yourdomain.com
ADMIN_PASSWORD=choose-a-strong-password
ADMIN_FULL_NAME=System Admin

# Enable mock data for testing (remove in production):
MOCK_PROVIDER_KEY=mock-trial-run
```

### Step 4 — Run database migrations

This creates all the tables in PostgreSQL:

```bash
# Still inside the backend/ folder:
python -m alembic upgrade head
```

You should see output ending with something like:
```
INFO  [alembic.runtime.migration] Running upgrade ... -> e8f3a1b2c4d5, add stops and duration columns
```

### Step 5 — Seed the route groups

This adds the pre-configured routes (Canada → Tokyo/Shanghai, Canada → Bali):

```bash
python -m app.scripts.seed_route_groups
```

Output:
```
  CREATE CAD-Tokyo-Shanghai-CAD
  CREATE CAN-DPS

Done — 2 created, 0 skipped.
```

### Step 6 — Start the backend server

```bash
uvicorn app.main:app --reload
```

The API is now running at http://localhost:8000. Keep this terminal open.

### Step 7 — Set up and start the frontend

Open a **new terminal**:

```bash
cd scraper-tool/flight-harvester/frontend

# Install Node.js dependencies
npm install

# Create the frontend environment file
cp .env.example .env
```

Edit `frontend/.env` and set:

```dotenv
VITE_API_BASE_URL=http://localhost:8000
```

Start the development server:

```bash
npm run dev
```

The dashboard is now at http://localhost:5173.

---

## Logging in to the dashboard

1. Open the dashboard URL (http://localhost:80 for Docker, http://localhost:5173 for local dev)
2. Enter the email and password you set in `backend/.env`
3. You will land on the main dashboard showing collection stats and route groups

---

## Running your first collection

### Automatic collection

The scheduler runs automatically every 60 minutes (configurable). Once running, you do not need to do anything — prices will be collected in the background.

### Manual trigger (immediate)

To collect prices right now without waiting:

1. Open the dashboard
2. Go to **Route Groups**
3. Click the **"Collect Now"** button next to any route group

Or use the API directly:

```bash
curl -X POST http://localhost:8000/api/v1/collection/trigger \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

### Watching the progress

- **Dashboard → Collection Logs** — shows every individual search attempt (origin, destination, date, provider, price found, duration)
- **Dashboard → Overview** — shows total prices collected, last run time, error count

---

## Downloading the Excel file

1. Go to **Dashboard → Route Groups**
2. Click the **"Export Excel"** button next to a route group
3. The file downloads immediately

The Excel file contains:
- One sheet per origin airport (e.g. "YYZ", "YVR", "YEG")
- Columns: `Date | Dep Airport | Arrivel Airport | Night | Airline | Flight Price`
- One row per departure date (up to 365 days ahead)
- Prices are whole numbers (integer CAD)
- Empty cells for dates where no price was found yet

Special sheets (e.g. "Osaka to Beijing") have 4 columns: `Date | Dep Airport | Arrivel Airport | Flight Price`.

---

## Adding real API keys (paid providers)

The system supports three real flight data sources. Add their keys to `backend/.env`:

### Kiwi Tequila (recommended first choice)

1. Sign up at https://tequila.kiwi.com
2. Create an API key in your dashboard
3. Add to `.env`:
   ```dotenv
   KIWI_API_KEY=your-key-here
   ```

### FlightAPI.io

1. Sign up at https://flightapi.io
2. Copy your API key
3. Add to `.env`:
   ```dotenv
   FLIGHTAPI_API_KEY=your-key-here
   ```

### Serper.dev (Google Search)

1. Sign up at https://serper.dev
2. Copy your API key
3. Add to `.env`:
   ```dotenv
   SERPER_API_KEY=your-key-here
   ```

> **Important:** After adding real keys, remove `MOCK_PROVIDER_KEY` (or leave it empty) so mock data does not mix with real prices.

You can enable multiple providers at the same time. The system always keeps only the cheapest price across all providers.

Each provider has automatic retry logic: if a request fails due to a network error or timeout, it retries up to 3 times with exponential backoff (waits 2s, then 4s, then 8s).

### Checking provider status

```bash
curl http://localhost:8000/health
```

Response shows which providers are active:

```json
{
  "status": "healthy",
  "providers": {
    "kiwi": "active",
    "flightapi": "disabled",
    "serper": "disabled",
    "mock": "disabled"
  }
}
```

---

## Configuration reference

All settings go in `backend/.env`. The table below explains every option:

| Variable | Required | Description | Default |
|----------|----------|-------------|---------|
| `DATABASE_URL` | Yes | PostgreSQL connection string | — |
| `JWT_SECRET_KEY` | Yes | Secret key for login tokens. Use any long random string. | — |
| `ADMIN_EMAIL` | Yes | Email address for the admin account | — |
| `ADMIN_PASSWORD` | Yes | Password for the admin account | — |
| `ADMIN_FULL_NAME` | No | Display name for the admin | `System Admin` |
| `DEBUG` | No | Show detailed error messages | `true` |
| `CORS_ORIGINS` | No | Frontend URLs allowed to connect to the API | `["http://localhost:5173"]` |
| `SCHEDULER_ENABLED` | No | Turn the automatic scheduler on or off | `true` |
| `SCHEDULER_INTERVAL_MINUTES` | No | How often to collect prices (in minutes) | `60` |
| `SCRAPE_BATCH_SIZE` | No | How many dates to search at once per provider call | `3` |
| `SCRAPE_DELAY_SECONDS` | No | Seconds to wait between batches (reduces API rate limiting) | `2.0` |
| `KIWI_API_KEY` | No | Kiwi Tequila API key — leave empty to disable | *(empty)* |
| `FLIGHTAPI_API_KEY` | No | FlightAPI.io key — leave empty to disable | *(empty)* |
| `SERPER_API_KEY` | No | Serper.dev key — leave empty to disable | *(empty)* |
| `MOCK_PROVIDER_KEY` | No | Set any non-empty value to enable fake data for testing. **Never set in production.** | *(empty)* |
| `TELEGRAM_BOT_TOKEN` | No | Telegram bot token for notifications | *(empty)* |
| `TELEGRAM_CHAT_ID` | No | Telegram chat or channel ID | *(empty)* |
| `SENTRY_DSN` | No | Sentry error tracking DSN | *(empty)* |

### Telegram notifications (optional)

To receive a message after each collection cycle and on failures:

1. Open Telegram and message `@BotFather`
2. Send `/newbot` and follow the prompts — you will get a token
3. Add the bot to your channel/group and get the chat ID
4. Add to `.env`:
   ```dotenv
   TELEGRAM_BOT_TOKEN=123456789:AAF...
   TELEGRAM_CHAT_ID=-1001234567890
   ```

---

## Deployment to the cloud

### Backend → Railway

Railway is the easiest way to host the backend for free (small tier).

1. Go to https://railway.app and create an account
2. Click **New Project → Deploy from GitHub repo**
3. Select this repository and set the **Root Directory** to `flight-harvester/backend`
4. Add a **PostgreSQL** plugin to the project
5. Set all required environment variables in the **Variables** tab (same as `.env`)
6. Railway auto-detects the `railway.toml` config and starts the server
7. Note your public URL (e.g. `https://your-app.up.railway.app`)

### Frontend → Vercel

1. Go to https://vercel.com and create an account
2. Click **Add New → Project → Import Git Repository**
3. Select this repository and set the **Root Directory** to `flight-harvester/frontend`
4. Add environment variable: `VITE_API_BASE_URL=https://your-app.up.railway.app`
5. Click Deploy — Vercel handles the build automatically
6. Update `CORS_ORIGINS` in your Railway backend variables to include your Vercel URL

---

## Troubleshooting

### "Cannot connect to PostgreSQL" / "Connection refused"

The database is not running. Fix:

```bash
# Check if PostgreSQL is running:
pg_isready

# Start it (Linux):
sudo service postgresql start

# Start it (Mac with Homebrew):
brew services start postgresql
```

If using Docker, make sure `docker compose up` is still running.

---

### "No active route groups" in the logs

The seed script was not run. Fix:

```bash
cd backend
python -m app.scripts.seed_route_groups
```

---

### "No providers enabled" in the logs

No API keys are set and the mock provider is not enabled. Fix:

Either add a real API key, or add this to `backend/.env`:

```dotenv
MOCK_PROVIDER_KEY=mock-trial-run
```

Then restart the server.

---

### Dashboard shows login errors / "Invalid credentials"

The admin account is created once on first startup. If you changed `ADMIN_PASSWORD` in `.env` after the first run, the stored password will not update automatically. Fix:

```bash
# Using Docker:
docker compose down -v    # this deletes the database
docker compose up --build # recreates everything fresh

# Using local dev:
psql -U postgres -c "DROP DATABASE flight_harvester;"
psql -U postgres -c "CREATE DATABASE flight_harvester;"
cd backend && python -m alembic upgrade head
python -m app.scripts.seed_route_groups
```

---

### "0 prices collected" after a collection cycle

Check the Collection Logs in the dashboard — each row shows the exact error. Common causes:

- **API key invalid or expired** — check the key in `.env`
- **Rate limited (429)** — increase `SCRAPE_DELAY_SECONDS` in `.env`
- **All providers disabled** — see "No providers enabled" above

---

### Docker build fails with "no space left on device"

Clean up unused Docker images:

```bash
docker system prune -f
```

---

### Port 8000 or 80 already in use

Another program is using that port. Stop it, or change the port in `docker-compose.yml`:

```yaml
# Change 8000:8000 to 8001:8000 to use port 8001 on your machine
ports: ["8001:8000"]
```

---

## Developer reference

### Project structure

```
flight-harvester/
├── backend/                        # FastAPI + SQLAlchemy + PostgreSQL
│   ├── app/
│   │   ├── api/                    # REST endpoints
│   │   │   └── v1/routes/          # auth, route_groups, prices, collection, stats
│   │   ├── core/                   # config, logging, security
│   │   ├── db/                     # session factory, init
│   │   ├── models/                 # SQLAlchemy ORM models
│   │   ├── providers/              # Flight data adapters
│   │   │   ├── base.py             # ProviderResult dataclass + FlightProvider protocol
│   │   │   ├── kiwi.py             # Kiwi Tequila
│   │   │   ├── flightapi.py        # FlightAPI.io
│   │   │   ├── serper.py           # Serper.dev (Google Search)
│   │   │   ├── mock.py             # Fake data for testing
│   │   │   └── registry.py         # Builds provider list from settings
│   │   ├── schemas/                # Pydantic request/response models
│   │   ├── scripts/                # seed_route_groups.py
│   │   ├── services/               # PriceCollector, ExportService, AlertService
│   │   └── tasks/                  # FlightScheduler (APScheduler)
│   ├── alembic/                    # Database migrations
│   ├── tests/                      # pytest test suite (50 tests)
│   ├── .env.example                # Environment variable template
│   └── pyproject.toml              # Python dependencies
└── frontend/                       # React 19 + TypeScript + Tailwind CSS
    └── src/
        ├── api/                    # Typed Axios wrappers
        ├── components/             # UI components (PriceTable, ScrapeLogsTable, …)
        ├── context/                # AuthContext
        ├── pages/                  # Dashboard, RouteGroups, DataExplorer, CollectionLogs
        └── types/                  # TypeScript interfaces
```

### Available API endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v1/auth/login` | Login, returns JWT token |
| `GET`  | `/api/v1/auth/me` | Current user info |
| `GET`  | `/api/v1/route-groups/` | List all route groups |
| `POST` | `/api/v1/route-groups/` | Create a route group |
| `GET`  | `/api/v1/route-groups/{id}/progress` | Collection coverage for a group |
| `GET`  | `/api/v1/route-groups/{id}/export` | Download Excel file |
| `POST` | `/api/v1/collection/trigger` | Trigger a full collection cycle now |
| `GET`  | `/api/v1/collection/runs` | Collection run history |
| `GET`  | `/api/v1/collection/logs` | Individual scrape log entries |
| `GET`  | `/api/v1/prices/` | Query collected price data |
| `GET`  | `/api/v1/prices/trend` | Price trend chart data for a route |
| `GET`  | `/api/v1/stats/overview` | Dashboard summary stats |
| `GET`  | `/health` | Health check (includes provider status) |

Full interactive API docs (Swagger UI): http://localhost:8000/docs

### Running the test suite

```bash
cd backend
python -m pytest tests/ -v
```

All 50 tests should pass. Tests use mocked sessions and providers — no real database or API keys needed.

### Linting

```bash
cd backend
ruff check app/

cd ../frontend
npm run lint
```

### Adding a new route group

Edit `backend/app/scripts/seed_route_groups.py` and add a new dictionary with:

```python
GROUP_3 = {
    "name": "YYZ-LHR",                        # unique name
    "destination_label": "LHR",               # shown in Excel header
    "destinations": ["LHR"],                  # IATA codes
    "origins": ["YYZ", "YVR"],                # IATA codes
    "nights": 7,                              # nights at destination
    "days_ahead": 180,                        # how far ahead to search
    "sheet_name_map": {
        "YYZ": "Toronto",
        "YVR": "Vancouver",
    },
    "special_sheets": [],
}
```

Then run `python -m app.scripts.seed_route_groups` again.

### Creating a database migration

When you change a SQLAlchemy model:

```bash
cd backend
python -m alembic revision --autogenerate -m "describe your change"
python -m alembic upgrade head
```

### Makefile shortcuts

```bash
make dev        # docker compose up --build
make down       # docker compose down
make test       # run the pytest suite
make lint       # run ruff
make migrate    # alembic upgrade head
```
