# Flight Harvester

A flight price tracking platform.

## Quick Start

```bash
docker compose up --build
```

## Development

```bash
cd backend
pip install -e ".[dev]"
alembic upgrade head
uvicorn app.main:app --reload
```

## Tests

```bash
cd backend && python -m pytest tests/ -v
```
