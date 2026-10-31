#!/usr/bin/env bash
# Fails (exit 1) when the committed TypeScript API types differ from what the backend
# currently produces. Run from anywhere; use in CI before the frontend build.
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

cd "$root"
uv run python scripts/export_openapi.py > "$tmp/openapi.json"
(cd frontend && npx --no-install openapi-typescript "$tmp/openapi.json" -o "$tmp/schema.d.ts" >/dev/null)

status=0
diff -u frontend/src/api/openapi.json "$tmp/openapi.json" || status=1
diff -u frontend/src/api/schema.d.ts "$tmp/schema.d.ts" || status=1
if [ "$status" -ne 0 ]; then
  echo "API types are out of date. Run: (cd frontend && npm run api:generate)" >&2
  exit 1
fi
echo "API types are up to date."
