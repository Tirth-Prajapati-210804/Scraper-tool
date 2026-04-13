# Flight Harvester

24/7 automated flight price collection platform. Tracks the cheapest daily flight prices
across multiple origin-destination routes and exports data as formatted Excel spreadsheets.

## Features

- **Automated collection** — APScheduler runs every N minutes, pulling prices from configured providers
- **Multi-provider** — Kiwi Tequila, FlightAPI.io, and Serper.dev; always keeps the cheapest price
- **Route groups** — configurable sets of origins × destinations with custom date ranges and night counts
- **Excel export** — generates client-specified `.xlsx` files with exact sheet names, headers, and integer prices
- **Real-time dashboard** — React frontend showing collection progress, price trends (Recharts), and provider status
- **Telegram alerts** — optional notifications on collection completion and failures
- **Production-ready** — Docker Compose, Railway (backend) + Vercel (frontend) configs included

## Architecture

```
flight-harvester/
├── backend/          # FastAPI + SQLAlchemy 2 async + PostgreSQL
│   ├── app/
│   │   ├── api/      # REST endpoints (auth, route-groups, prices, collection, stats)
│   │   ├── models/   # SQLAlchemy ORM models
│   │   ├── providers/ # Kiwi, FlightAPI, Serper adapters + ProviderRegistry
│   │   ├── services/  # PriceCollector, ExportService, AlertService
│   │   └── tasks/    # APScheduler FlightScheduler
│   └── alembic/      # Database migrations
└── frontend/         # React 19 + TypeScript + Tailwind CSS + React Query
    └── src/
        ├── api/       # Typed Axios wrappers
        ├── components/ # UI primitives + feature components
        └── pages/     # Dashboard, RouteGroupDetail, DataExplorer, CollectionLogs
```

## Quick Start (Docker)

```bash
# Copy and edit the backend environment file
cp backend/.env.example backend/.env
# Edit backend/.env: set JWT_SECRET_KEY, ADMIN_PASSWORD, and any provider keys

docker compose up --build
```

- Backend API: http://localhost:8000
- Frontend: http://localhost:80
- API docs: http://localhost:8000/docs

Default admin credentials (set in `backend/.env`):
- Email: `admin@flightharvester.com`
- Password: `admin12345`

## Local Development

### Backend

```bash
cd backend
pip install -e ".[dev]"

# Start PostgreSQL (or use Docker)
docker compose up db -d

# Copy env and run migrations
cp .env.example .env
python -m alembic upgrade head

# Seed route groups
python -m app.scripts.seed_route_groups

# Start API server
uvicorn app.main:app --reload
```

### Frontend

```bash
cd frontend
npm install
cp .env.example .env       # set VITE_API_BASE_URL=http://localhost:8000
npm run dev                # → http://localhost:5173
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v1/auth/login` | Login, returns JWT |
| `GET`  | `/api/v1/auth/me` | Current user info |
| `GET`  | `/api/v1/route-groups/` | List all route groups |
| `POST` | `/api/v1/route-groups/` | Create route group |
| `GET`  | `/api/v1/route-groups/{id}/progress` | Collection coverage |
| `GET`  | `/api/v1/route-groups/{id}/export` | Download Excel file |
| `GET`  | `/api/v1/prices/` | Query price data |
| `GET`  | `/api/v1/prices/trend` | Price trend for a route |
| `POST` | `/api/v1/collection/trigger` | Trigger full collection cycle |
| `GET`  | `/api/v1/collection/runs` | Collection run history |
| `GET`  | `/api/v1/collection/logs` | Individual scrape logs |
| `GET`  | `/api/v1/stats/overview` | Dashboard stats |
| `GET`  | `/health` | Health check |

Full interactive docs at `/docs` (Swagger UI).

## Configuration

All backend settings are read from environment variables (or `backend/.env`):

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL async URL | — |
| `JWT_SECRET_KEY` | Secret for JWT signing | — |
| `ADMIN_EMAIL` | Initial admin email | — |
| `ADMIN_PASSWORD` | Initial admin password | — |
| `CORS_ORIGINS` | JSON array of allowed origins | `["http://localhost:5173"]` |
| `SCHEDULER_ENABLED` | Enable/disable APScheduler | `true` |
| `SCHEDULER_INTERVAL_MINUTES` | Collection interval | `60` |
| `SCRAPE_BATCH_SIZE` | Dates per concurrent batch | `5` |
| `SCRAPE_DELAY_SECONDS` | Sleep between batches | `1.0` |
| `KIWI_API_KEY` | Kiwi Tequila API key | *(empty = disabled)* |
| `FLIGHTAPI_API_KEY` | FlightAPI.io key | *(empty = disabled)* |
| `SERPER_API_KEY` | Serper.dev key | *(empty = disabled)* |
| `TELEGRAM_BOT_TOKEN` | Telegram bot token | *(empty = disabled)* |
| `TELEGRAM_CHAT_ID` | Telegram chat ID | *(empty = disabled)* |
| `SENTRY_DSN` | Sentry error tracking DSN | *(empty = disabled)* |

## Deployment

### Backend → Railway

1. Push the `backend/` folder to Railway (or connect the GitHub repo)
2. Set all required environment variables in the Railway dashboard
3. Railway uses `backend/railway.toml` — health check at `/health`

### Frontend → Vercel

1. Connect the `frontend/` folder to Vercel
2. Set `VITE_API_BASE_URL` to your Railway backend URL
3. Vercel uses `frontend/vercel.json` for SPA rewrites

## Tests

```bash
cd backend
python -m pytest tests/ -v   # 50 tests
ruff check app/               # lint
```

```bash
cd frontend
npm run build                 # TypeScript + Vite build
npm run lint                  # ESLint
```
