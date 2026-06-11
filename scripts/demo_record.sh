#!/bin/bash
# Demo script recorded into demo.cast / demo.gif for the README.
# Run scripts/demo_setup.sh first to create demo.db.
set -e
cd "$(dirname "$0")/.."
source .venv/bin/activate
export PYTHONPATH=.

type_cmd() {
  printf '\033[1;32m$\033[0m %s\n' "$1"
  sleep 0.6
}

clear
type_cmd "SQLITE_PATH=./demo.db uvx universal-db-mcp --check"
SQLITE_PATH=./demo.db PYTHONPATH=. python -m src.universal_db_mcp.server --check
sleep 1.5

echo
echo "# Claude: \"What tables do I have and what columns?\""
sleep 1
python scripts/demo_helper.py schema | head -15
sleep 2

echo
echo "# Claude: \"Which customers spent the most in May 2026?\""
sleep 1
python scripts/demo_helper.py query
sleep 2

echo
echo "# Claude: \"Try DROP TABLE customers\""
sleep 1
python scripts/demo_helper.py blocked
sleep 2

echo
echo "# Claude: \"Now show me the plan with DRYRUN=true (don't run it)\""
sleep 1
python scripts/demo_helper.py dry_run | head -8
sleep 3
