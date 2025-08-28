#!/usr/bin/env bash
set -euo pipefail

API_PORT=${API_PORT:-8000}
UI_PORT=${UI_PORT:-5173}
API_HOST=0.0.0.0
UI_HOST=0.0.0.0

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND="$ROOT_DIR/backend"
FRONTEND="$ROOT_DIR/frontend"

echo "== Quant Clean Launcher =="

# --- Backend ---
echo "-> Backend setup"
python3 -m venv "$BACKEND/.venv" || true
source "$BACKEND/.venv/bin/activate" || true
python -m pip install --upgrade pip
python -m pip install -r "$BACKEND/requirements.txt"
nohup uvicorn src.main:app --reload --host "$API_HOST" --port "$API_PORT" > "$BACKEND/api.log" 2>&1 &
deactivate || true

# --- Frontend ---
echo "-> Frontend setup"
cd "$FRONTEND"
npm install
nohup npm run dev -- --host "$UI_HOST" --port "$UI_PORT" > "$FRONTEND/ui.log" 2>&1 &

cd "$ROOT_DIR"
echo "API: http://localhost:$API_PORT/docs"
echo "UI : http://localhost:$UI_PORT"
