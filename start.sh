#!/usr/bin/env bash
# Start Aurora in native dev mode: Postgres+Redis via Docker, backend
# (uvicorn) and frontend (Vite) as background jobs. Ctrl+C stops both.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ ! -f "$REPO_ROOT/.env" ]; then
    echo "No .env found -- copying .env.example. Edit it (AI provider keys, etc.) before continuing."
    cp "$REPO_ROOT/.env.example" "$REPO_ROOT/.env"
fi

if [ ! -d "$REPO_ROOT/backend/.venv" ]; then
    echo "backend/.venv not found. Run this first:"
    echo "  cd backend && python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt"
    exit 1
fi

if [ ! -d "$REPO_ROOT/frontend/node_modules" ]; then
    echo "frontend/node_modules not found. Run this first:"
    echo "  cd frontend && npm install"
    exit 1
fi

if command -v docker >/dev/null 2>&1; then
    echo "Starting Postgres + Redis via Docker Compose..."
    (cd "$REPO_ROOT" && docker compose up -d postgres redis)
else
    echo "Docker not found -- make sure Postgres (with pgvector) and Redis are running natively (see README.md)."
fi

cleanup() {
    echo ""
    echo "Stopping Aurora..."
    kill "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

echo "Starting backend (uvicorn) on http://localhost:8000 ..."
(
    cd "$REPO_ROOT/backend"
    source .venv/bin/activate
    exec uvicorn app.main:app --reload
) &
BACKEND_PID=$!

echo "Starting frontend (Vite) on http://localhost:5173 ..."
(
    cd "$REPO_ROOT/frontend"
    exec npm run dev
) &
FRONTEND_PID=$!

echo ""
echo "Aurora is running. Press Ctrl+C to stop both services."
wait
