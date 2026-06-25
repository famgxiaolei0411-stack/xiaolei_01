#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

echo "This will delete local database, uploaded files, exported files, and generated test projects."
read -r -p "Type RESET to continue: " CONFIRM
if [ "$CONFIRM" != "RESET" ]; then
  echo "Canceled."
  exit 0
fi

rm -f aitest.db aitest.db-shm aitest.db-wal

clean_dir() {
  local dir="$1"
  [ -d "$dir" ] || return 0
  find "$dir" -mindepth 1 ! -name ".gitkeep" -exec rm -rf {} +
}

clean_dir uploads
clean_dir outputs
clean_dir generated_tests
clean_dir allure-results
clean_dir allure-report
clean_dir .pytest_tmp
clean_dir .run_logs

echo "Local data has been reset."
