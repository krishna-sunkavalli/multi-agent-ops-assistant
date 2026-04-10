#!/bin/bash
# test-local.sh — Start the Ops Assistant locally for development/testing
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Load environment
if [ ! -f "$PROJECT_ROOT/.env" ]; then
  echo "❌ .env file not found. Run deploy-all.sh first."
  exit 1
fi

set -a
source "$PROJECT_ROOT/.env"
set +a

# Create venv if needed
if [ ! -d "$PROJECT_ROOT/.venv" ]; then
  echo "Creating virtual environment..."
  python -m venv "$PROJECT_ROOT/.venv"
fi

# Activate venv (cross-platform: Scripts on Windows, bin on Linux/Mac)
if [ -f "$PROJECT_ROOT/.venv/Scripts/activate" ]; then
  source "$PROJECT_ROOT/.venv/Scripts/activate"
else
  source "$PROJECT_ROOT/.venv/bin/activate"
fi

pip install -q --pre -r "$PROJECT_ROOT/requirements.txt"

echo ""
echo "========================================="
echo "  Ops Assistant — Local Dev Server"
echo "========================================="
echo "  Open: http://localhost:8000"
echo "  Quit: Ctrl+C"
echo "========================================="
echo ""

cd "$PROJECT_ROOT"
uvicorn src.api:app --reload --port 8000
