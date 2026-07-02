#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

if command -v python3 >/dev/null 2>&1; then
  python3 start.py
elif command -v python >/dev/null 2>&1; then
  python start.py
else
  echo "Python was not found. Please install Python 3.11+ first."
  exit 1
fi
