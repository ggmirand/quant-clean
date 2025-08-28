#!/usr/bin/env bash
set -euo pipefail

API_PORT=${API_PORT:-8000}
UI_PORT=${UI_PORT:-5173}

echo "Stopping servers..."
fuser -k "$API_PORT"/tcp || true
fuser -k "$UI_PORT"/tcp || true
pkill -f "uvicorn src.main:app" || true
pkill -f "vite" || true
echo "Done."
