# Flight Data Scrapper — Frontend

React 19 + TypeScript + Tailwind CSS dashboard for the Flight Data Scrapper platform.

---

## What this is

The frontend is the visual interface you use to:

- View collected flight prices and trends
- Manage route groups (which airports and dates to track)
- Trigger manual collection runs
- Download Excel exports
- Browse scrape logs

It connects to the **backend API** (FastAPI) — you must have the backend running before starting the frontend.

---

## Prerequisites

- **Node.js 18 or newer** — https://nodejs.org/en/download (choose the LTS version)
- The **backend** must be running at http://localhost:8000 (see the main README)

Check your Node version:
```bash
node --version   # must be v18.0.0 or higher
npm --version    # comes with Node
```

---

## Setup (local development)

### Step 1 — Install dependencies

```bash
cd flight-data-scrapper/frontend
npm install
```

This downloads all required packages into `node_modules/`. It takes about 30 seconds.

### Step 2 — Create the environment file

```bash
cp .env.example .env
```

Open `.env` and set the backend URL:

```dotenv
VITE_API_BASE_URL=http://localhost:8000
```

If your backend is running on a different port or host, update this URL.

### Step 3 — Start the development server

```bash
npm run dev
```

The dashboard opens at **http://localhost:5173**.

Changes to source files are reflected instantly in the browser — no need to restart.

---

## Available commands

| Command | What it does |
|---------|--------------|
| `npm run dev` | Start development server with hot reload |
| `npm run build` | Build production bundle into `dist/` |
| `npm run preview` | Preview the production build locally |
| `npm run lint` | Run ESLint on all TypeScript/React files |

---

## Pages

| Page | URL | Description |
|------|-----|-------------|
| Dashboard | `/` | Overview stats, recent collection run, price charts |
| Route Groups | `/route-groups` | List, create, and manage route groups |
| Route Detail | `/route-groups/:id` | Coverage map and prices for one route group |
| Data Explorer | `/explorer` | Search and filter all collected prices |
| Collection Logs | `/logs` | Every individual scrape attempt with status, duration, price |

---

## Project structure

```
frontend/
├── src/
│   ├── api/                # Typed Axios functions (one file per resource)
│   │   ├── auth.ts         # login, getMe
│   │   ├── collection.ts   # trigger, runs, logs
│   │   ├── prices.ts       # query prices, trend data
│   │   ├── routeGroups.ts  # CRUD + export
│   │   └── stats.ts        # overview stats
│   ├── components/
│   │   ├── PriceTable.tsx  # Sortable price table (Date, Origin, Dest, Airline, Price, Stops, Duration)
│   │   ├── ScrapeLogsTable.tsx
│   │   └── ...
│   ├── context/
│   │   └── AuthContext.tsx  # Login state, JWT storage
│   ├── pages/
│   │   ├── Dashboard.tsx
│   │   ├── RouteGroups.tsx
│   │   ├── RouteGroupDetail.tsx
│   │   ├── DataExplorer.tsx
│   │   └── CollectionLogs.tsx
│   └── types/
│       ├── auth.ts          # User, TokenResponse
│       └── price.ts         # DailyPrice (includes stops, duration_minutes)
├── .env.example             # Copy to .env before first run
├── vite.config.ts
├── tailwind.config.ts
└── package.json
```

---

## Building for production

```bash
npm run build
```

The output goes into `dist/`. This is what Docker and Vercel deploy.

To test the production build locally:

```bash
npm run preview
# Opens at http://localhost:4173
```

---

## Docker

The frontend has its own `Dockerfile` and is included in the root `docker-compose.yml`. When you run `docker compose up --build` from `flight-data-scrapper/`, the frontend is automatically built and served on port 80 via nginx.

You do not need to run `npm install` or `npm run build` manually when using Docker.

---

## Deploying to Vercel

1. Push the repository to GitHub
2. Go to https://vercel.com → **New Project** → import your repository
3. Set **Root Directory** to `flight-data-scrapper/frontend`
4. Add environment variable: `VITE_API_BASE_URL=https://your-backend-url.railway.app`
5. Click Deploy

Vercel runs `npm run build` automatically and serves the `dist/` folder.

> After deploying the frontend, update the `CORS_ORIGINS` variable in your backend to include the Vercel URL (e.g. `https://your-app.vercel.app`).

---

## Environment variables

| Variable | Description | Example |
|----------|-------------|---------|
| `VITE_API_BASE_URL` | Full URL of the backend API (no trailing slash) | `http://localhost:8000` |

All `VITE_` variables are embedded into the build at compile time. If you change `.env`, restart `npm run dev` or rebuild.
