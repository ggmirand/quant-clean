#!/usr/bin/env bash
set -euo pipefail

API_PORT=${API_PORT:-8000}
UI_PORT=${UI_PORT:-5173}
API_HOST=0.0.0.0
UI_HOST=0.0.0.0

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND="$ROOT_DIR/backend"
FRONTEND="$ROOT_DIR/frontend"

echo "== Quant Clean Launcher (system Python, no venv) =="

# --- Backend (system Python) ---
echo "-> Backend deps (pip --user)"
python3 -m pip install --user --upgrade pip
python3 -m pip install --user -r "$BACKEND/requirements.txt"

# free ports if occupied
if command -v fuser >/dev/null 2>&1; then
  fuser -k "$API_PORT"/tcp || true
  fuser -k "$UI_PORT"/tcp || true
fi

echo "-> Starting API http://$API_HOST:$API_PORT"
nohup python3 -m uvicorn src.main:app --host "$API_HOST" --port "$API_PORT" --reload > "$BACKEND/api.log" 2>&1 &

# --- Frontend ---
echo "-> Frontend deps (npm install)"
cd "$FRONTEND"
if ! command -v npm >/dev/null 2>&1; then
  echo "ERROR: npm not found. Install Node.js 20+ (e.g., https://nodejs.org or nvm)."
  exit 1
fi
npm install
echo "-> Starting UI http://$UI_HOST:$UI_PORT"
nohup npm run dev -- --host "$UI_HOST" --port "$UI_PORT" > "$FRONTEND/ui.log" 2>&1 &

cd "$ROOT_DIR"
echo "API: http://localhost:$API_PORT/docs"
echo "UI : http://localhost:$UI_PORT"
