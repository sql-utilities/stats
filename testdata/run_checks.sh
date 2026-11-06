#!/usr/bin/env bash
set -euo pipefail
: "${PG_URL:=postgresql://postgres:postgres@localhost:5432/postgres}"
HERE="$(dirname "$0")"

psql "$PG_URL" -v ON_ERROR_STOP=1 -f "$HERE/seed_postgres.sql"
stats --url "$PG_URL" --schema dbstat_demo --table users --format table >/dev/null
stats --url "$PG_URL" --schema dbstat_demo --format json | python -m json.tool >/dev/null

# every non-comment line of expected_users.txt is a regex that must match a line of the report
REPORT="$(stats --url "$PG_URL" --schema dbstat_demo --table users --format table)"
while IFS= read -r pattern; do
    [[ -z "$pattern" || "$pattern" == \#* ]] && continue
    if ! grep -Eq -- "$pattern" <<< "$REPORT"; then
        echo "FAIL: no line matches: $pattern" >&2
        exit 1
    fi
done < "$HERE/expected_users.txt"

echo OK
