#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-8501}"
export BACKEND_URL="http://127.0.0.1:${BACKEND_PORT}"
VENV_PY=".venv/bin/python"
PIP_MIRROR="${PIP_MIRROR:-https://pypi.tuna.tsinghua.edu.cn/simple}"
PIP_TIMEOUT="${PIP_TIMEOUT:-60}"
PIP_RETRIES="${PIP_RETRIES:-5}"

if [ ! -f "requirements.txt" ]; then
  echo "requirements.txt not found. Please run this script from the project root."
  exit 1
fi

if [ ! -f ".env" ]; then
  cp ".env.example" ".env"
  echo "Created .env from .env.example"
  echo "Please edit .env and set your API key before generating test cases."
  echo
fi

if [ ! -x "${VENV_PY}" ]; then
  echo "Creating local Python virtual environment..."
  if command -v python3 >/dev/null 2>&1; then
    python3 -m venv .venv
  elif command -v python >/dev/null 2>&1; then
    python -m venv .venv
  else
    echo "Python was not found. Please install Python 3.11+ first."
    exit 1
  fi
fi

echo "Installing or checking dependencies..."
"${VENV_PY}" -m pip install --upgrade pip setuptools wheel -i "${PIP_MIRROR}" --timeout "${PIP_TIMEOUT}" --retries "${PIP_RETRIES}"
if ! "${VENV_PY}" -m pip install -r requirements.txt -i "${PIP_MIRROR}" --timeout "${PIP_TIMEOUT}" --retries "${PIP_RETRIES}"; then
  echo
  echo "Mirror install failed. Retrying with default PyPI..."
  "${VENV_PY}" -m pip install -r requirements.txt --timeout "${PIP_TIMEOUT}" --retries "${PIP_RETRIES}"
fi

check_port() {
  local port="$1"
  if command -v lsof >/dev/null 2>&1; then
    lsof -iTCP:"${port}" -sTCP:LISTEN >/dev/null 2>&1
  elif command -v nc >/dev/null 2>&1; then
    nc -z 127.0.0.1 "${port}" >/dev/null 2>&1
  else
    "${VENV_PY}" -c "import socket,sys; s=socket.socket(); sys.exit(0 if s.connect_ex(('127.0.0.1', int(sys.argv[1]))) == 0 else 1)" "${port}"
  fi
}

if check_port "${BACKEND_PORT}"; then
  echo "Port ${BACKEND_PORT} is already in use. Set BACKEND_PORT to another value or stop the existing backend."
  exit 1
fi

if check_port "${FRONTEND_PORT}"; then
  echo "Port ${FRONTEND_PORT} is already in use. Set FRONTEND_PORT to another value or stop the existing frontend."
  exit 1
fi

echo "Starting backend on ${BACKEND_URL}..."
"${VENV_PY}" -m uvicorn backend.main:app --host 127.0.0.1 --port "${BACKEND_PORT}" --reload &
BACKEND_PID=$!

sleep 3

echo "Starting frontend on http://127.0.0.1:${FRONTEND_PORT}..."
"${VENV_PY}" -m streamlit run frontend/app.py --server.address 127.0.0.1 --server.port "${FRONTEND_PORT}" &
FRONTEND_PID=$!

echo
echo "Backend PID:  ${BACKEND_PID}"
echo "Frontend PID: ${FRONTEND_PID}"
echo "Open: http://127.0.0.1:${FRONTEND_PORT}"
echo
echo "Press Ctrl+C to stop both services."

trap 'kill ${BACKEND_PID} ${FRONTEND_PID} 2>/dev/null || true' INT TERM EXIT
wait
