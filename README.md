# betons (fallback build)

This repository implements a self-contained CRUD dashboard for managing concrete deliveries using only the Python standard library and SQLite (no npm dependencies required).

## Features
- Static frontend (HTML/CSS/JS) styled with Tailwind CDN and custom rules
- REST API built with `wsgiref` and `sqlite3`
- SQLite database with automatic migrations and seed data
- Health endpoint verifying database connectivity
- Dockerfile and docker-compose for deployment

## Getting started
### Prerequisites
- Python 3.11+

### Local development
1. Install dependencies: none required beyond Python stdlib.
2. Start the server:
   ```bash
   python server.py --port 8000
   ```
   The server will create `data.db`, apply the schema, and insert sample rows if the table is empty.
3. Open http://localhost:8000 to view the dashboard.

### Database seeding/migrations
- Schema creation runs automatically on start.
- To skip seed data, pass `--no-seed`.
- To use a custom database path, set `DB_PATH` env or pass `--db path/to/file.db`.

### Health check
```
curl http://localhost:8000/api/health
```

### Manual API smoke test
```
# list
curl -s http://localhost:8000/api/records | jq
# create
curl -s -X POST http://localhost:8000/api/records \
  -H "Content-Type: application/json" \
  -d '{"date":"2024-12-05","site":"Site D","mix":"C35/45","volume":15.5,"status":"Scheduled","notes":"Evening"}'
```

### Running tests
```
python -m unittest
```

## Docker
Build and run locally:
```
docker build -t betons .
docker run -p 8000:8000 betons
```

## Docker Compose
`docker-compose.yml` runs the app with a bind-mounted SQLite database:
```
docker compose up --build
```

## Environment variables
- `PORT` – port for the HTTP server (default `8000`).
- `DB_PATH` – path to the SQLite database file (default `data.db`).

## Notes
The original npm-based stack was not reachable due to registry 403 restrictions. This fallback implementation preserves the required CRUD functionality, health check, and deployability without external package registries.
