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

USE_VENV=false
if [ -d "$BACKEND/.venv" ] && [ -f "$BACKEND/.venv/bin/activate" ]; then
  USE_VENV=true
else
  echo "-> No venv detected. Trying to create one..."
  if command -v python3 >/dev/null 2>&1; then
    if python3 -m venv "$BACKEND/.venv" 2>/dev/null; then
      USE_VENV=true
    else
      echo "!! Could not create venv (python3 -m venv). Will use system Python with --break-system-packages."
    fi
  else
    echo "ERROR: python3 not found. Install it with: sudo apt update && sudo apt install -y python3 python3-venv python3-pip"
    exit 1
  fi
fi

# Free ports if occupied
if command -v fuser >/dev/null 2>&1; then
  fuser -k "$API_PORT"/tcp || true
  fuser -k "$UI_PORT"/tcp || true
fi

# --- Backend deps + start ---
if $USE_VENV; then
  echo "-> Using venv at backend/.venv"
  # shellcheck disable=SC1091
  source "$BACKEND/.venv/bin/activate"
  pip install --upgrade pip
  pip install -r "$BACKEND/requirements.txt"
  UVICORN="uvicorn"
else
  echo "-> Using system Python (PEP 668 fallback)"
  python3 -m pip install --upgrade pip --break-system-packages
  python3 -m pip install -r "$BACKEND/requirements.txt" --break-system-packages
  UVICORN="python3 -m uvicorn"
fi

echo "-> Starting API http://$API_HOST:$API_PORT"
nohup $UVICORN src.main:app --host "$API_HOST" --port "$API_PORT" --reload > "$BACKEND/api.log" 2>&1 &

# Deactivate venv to avoid leaking env into frontend step
if $USE_VENV; then deactivate || true; fi

# --- Frontend deps + start ---
echo "-> Frontend setup"
cd "$FRONTEND"
if ! command -v npm >/dev/null 2>&1; then
  echo "ERROR: npm not found. Install Node.js 20+ (https://nodejs.org or use nvm)."
  exit 1
fi
npm install
echo "-> Starting UI http://$UI_HOST:$UI_PORT"
nohup npm run dev -- --host "$UI_HOST" --port "$UI_PORT" > "$FRONTEND/ui.log" 2>&1 &

cd "$ROOT_DIR"
echo "API: http://localhost:$API_PORT/docs"
echo "UI : http://localhost:$UI_PORT"
