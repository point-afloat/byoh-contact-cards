#!/usr/bin/env bash
# Smoke test for the production image: builds it and checks the deployment contract in real
# containers (health, SPA, non-root, one process, no secrets in the image, data volume,
# PORT, misconfiguration, clean shutdown).
#
#   bash scripts/smoke-container.sh                 # build, then test
#   SKIP_BUILD=1 IMAGE=my:tag bash scripts/smoke-container.sh   # test an existing image
#
# Needs Docker and curl. Uses dummy credentials only. Removes everything it creates.
set -uo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
project="$(cd "$here/.." && pwd)"
image="${IMAGE:-contact-card-importer:smoke}"
suffix="$$"
volume="smoke-data-$suffix"
mock_volume="smoke-mock-$suffix"
empty_volume="smoke-empty-$suffix"
jar="$(mktemp)"
jar2="$(mktemp)" # the invited colleague's own browser

SECRET_LLM="dummy-llm-key-for-smoke-test"
SECRET_FB="dummy-fb-token-for-smoke-test"
SECRET_ADMIN="dummy-admin-password-for-smoke-test"
MEMBER_PASSWORD="dummy-member-password-for-smoke-test"
# AUTH_COOKIE_SECURE=false only because this script talks plain http through curl.
app_env=(-e LLM_MODEL=smoke-model -e "LLM_API_KEY=$SECRET_LLM" -e "FUNDRAISINGBOX_APITOKEN=$SECRET_FB" -e AUTH_COOKIE_SECURE=false)
good_env=("${app_env[@]}" -e INITIAL_ADMIN_EMAIL=admin@example.org -e "INITIAL_ADMIN_PASSWORD=$SECRET_ADMIN")

# Containers are labelled, so cleanup finds them even though start() runs in a subshell.
stub_pid=""
cleanup() {
  [ -n "$stub_pid" ] && kill "$stub_pid" 2>/dev/null
  docker ps -aq --filter "label=smoke-run=$suffix" | xargs -r docker rm -f >/dev/null 2>&1
  docker volume rm -f "$volume" "$empty_volume" "$mock_volume" >/dev/null 2>&1
  rm -f "$jar" "$jar2"
}
trap cleanup EXIT

failures=0
pass() { echo "ok   - $1"; }
fail() { echo "FAIL - $1"; failures=$((failures + 1)); }
check() { # description, command...
  local description="$1"
  shift
  if "$@"; then pass "$description"; else fail "$description"; fi
}

if [ -z "${SKIP_BUILD:-}" ]; then
  echo "building $image ..."
  docker build -q -t "$image" "$project" >/dev/null || { echo "FAIL - docker build"; exit 1; }
fi

# start <name> <container-port> <docker args...>  -> prints the container name
start() {
  local name="smoke-$1-$suffix" port="$2"
  shift 2
  docker run -d --name "$name" --label "smoke-run=$suffix" -p "127.0.0.1::$port" "$@" "$image" >/dev/null || return 1
  echo "$name"
}
host_port() { docker port "$1" "$2/tcp" | head -1 | sed 's/.*://'; }
# api <curl args...>: JSON request as a browser would send it, keeping the sign-in cookie.
api() { curl -s -b "$jar" -c "$jar" -H 'X-Requested-With: smoke' -H 'Content-Type: application/json' "$@"; }
status_of() { curl -s -o /dev/null -w '%{http_code}' --max-time 3 "$1" 2>/dev/null || true; }
wait_for_status() { # url, expected, seconds
  local i
  for ((i = 0; i < $3; i++)); do
    [ "$(status_of "$1")" == "$2" ] && return 0
    sleep 1
  done
  return 1
}

# --- 1. A correctly configured container -----------------------------------------------------
c1="$(start main 8080 "${good_env[@]}" -v "$volume:/data")"
base="http://127.0.0.1:$(host_port "$c1" 8080)"

check "health is 200 once configured (default port 8080)" wait_for_status "$base/api/health" 200 30
body="$(curl -s "$base/api/health")"
check "health body has no secrets" bash -c '! grep -q -e "$1" -e "$2" <<<"$3"' _ "$SECRET_LLM" "$SECRET_FB" "$body"
check "/ serves the web app" bash -c 'curl -s "$1/" | grep -q "<div id=\"root\">"' _ "$base"
check "a deep link falls back to the web app" bash -c 'curl -s "$1/review/anything" | grep -q "<div id=\"root\">"' _ "$base"
check "unknown API paths return the JSON error, not the app" bash -c 'curl -s "$1/api/nope" | grep -q "\"code\":\"http_404\""' _ "$base"

# --- accounts: sign-in is required, the first admin works, an invited colleague can join ----
check "anonymous callers get 401 on a protected route" \
  test "$(status_of "$base/api/auth/me")" = 401
check "anonymous callers cannot list users" test "$(status_of "$base/api/admin/users")" = 401
login_code="$(api -o /dev/null -w '%{http_code}' -X POST \
  -d "{\"email\":\"admin@example.org\",\"password\":\"$SECRET_ADMIN\"}" "$base/api/auth/login")"
check "the first administrator from the settings can sign in" test "$login_code" = 200
check "that account is an administrator" grep -q '"role":"admin"' <<<"$(api "$base/api/auth/me")"
invite="$(api -X POST -d '{"email":"persist@example.org","role":"member"}' "$base/api/admin/users")"
token="$(sed -n 's/.*"token":"\([^"]*\)".*/\1/p' <<<"$invite")"
member_id="$(sed -n 's/.*"user":{"id":\([0-9]*\).*/\1/p' <<<"$invite")"
accept_code="$(curl -s -o /dev/null -w '%{http_code}' -X POST -H 'X-Requested-With: smoke' -c "$jar2" \
  -H 'Content-Type: application/json' \
  -d "{\"token\":\"$token\",\"password\":\"$MEMBER_PASSWORD\"}" "$base/api/auth/accept-invite")"
check "an invited colleague can accept the invitation and choose a password" test "$accept_code" = 200
check "the colleague is signed in right after accepting" \
  grep -q '"email":"persist@example.org"' <<<"$(curl -s -b "$jar2" "$base/api/auth/me")"
check "the administrator can deactivate the colleague" \
  test "$(api -o /dev/null -w '%{http_code}' -X PATCH -d '{"is_active":false}' "$base/api/admin/users/$member_id")" = 200
check "the deactivated colleague's session ends at once" \
  test "$(curl -s -o /dev/null -w '%{http_code}' -b "$jar2" "$base/api/auth/me")" = 401
check "a deactivated colleague cannot sign in" \
  test "$(curl -s -o /dev/null -w '%{http_code}' -X POST -H 'X-Requested-With: smoke' -H 'Content-Type: application/json' \
    -d "{\"email\":\"persist@example.org\",\"password\":\"$MEMBER_PASSWORD\"}" "$base/api/auth/login")" = 401
check "the administrator can reactivate the colleague, who then keeps the old password" \
  test "$(api -o /dev/null -w '%{http_code}' -X PATCH -d '{"is_active":true}' "$base/api/admin/users/$member_id")" = 200

uid="$(docker exec "$c1" sh -c "awk '/^Uid:/ {print \$2}' /proc/1/status")"
check "the server process is not root (uid $uid)" bash -c '[ -n "$1" ] && [ "$1" != "0" ]' _ "$uid"
processes="$(docker top "$c1" -eo pid,args | tail -n +2)"
check "exactly one process runs, and it is the app server" bash -c '[ "$(wc -l <<<"$1")" -eq 1 ] && grep -q "app.server" <<<"$1"' _ "$processes"

stray="$(docker run --rm --entrypoint sh "$image" -c 'find / -xdev \( -name ".env" -o -name ".env.*" \) 2>/dev/null')"
check "the image contains no .env files" test -z "$stray"
check "image history contains no secrets" bash -c '! docker history --no-trunc "$1" | grep -q "dummy-"' _ "$image"

check "the app user can write to /data" docker exec "$c1" sh -c 'echo persisted > /data/marker.txt'
docker rm -f "$c1" >/dev/null 2>&1
# The replacement gets NO first-admin settings: the accounts must come from the volume.
c2="$(start replaced 8080 "${app_env[@]}" -v "$volume:/data")"
base2="http://127.0.0.1:$(host_port "$c2" 8080)"
check "data written to /data survives replacing the container" \
  bash -c '[ "$(docker exec "$1" cat /data/marker.txt)" == "persisted" ]' _ "$c2"
check "the replacement is healthy without first-admin settings: the accounts were kept" \
  wait_for_status "$base2/api/health" 200 30
login_again="$(curl -s -o /dev/null -w '%{http_code}' -X POST -H 'X-Requested-With: smoke' \
  -H 'Content-Type: application/json' \
  -d "{\"email\":\"persist@example.org\",\"password\":\"$MEMBER_PASSWORD\"}" "$base2/api/auth/login")"
check "a colleague created before the replacement can still sign in" test "$login_again" = 200

# --- 2. Clean shutdown (the replacement container) -------------------------------------------
base2="http://127.0.0.1:$(host_port "$c2" 8080)"
wait_for_status "$base2/api/health" 200 30 >/dev/null
started="$(date +%s%N)"
docker stop -t 20 "$c2" >/dev/null
elapsed_ms=$((($(date +%s%N) - started) / 1000000))
exit_code="$(docker inspect -f '{{.State.ExitCode}}' "$c2")"
check "docker stop finishes well inside the grace period (${elapsed_ms} ms)" test "$elapsed_ms" -lt 8000
check "the server exits cleanly on SIGTERM (exit code $exit_code)" test "$exit_code" -eq 0
check "the log shows a graceful shutdown" bash -c 'docker logs "$1" 2>&1 | grep -q "Finished server process"' _ "$c2"

# --- 3. PORT is honoured ---------------------------------------------------------------------
c3="$(start port 9000 "${good_env[@]}" -e PORT=9000 -v "$volume:/data")"
check "PORT=9000 is honoured" wait_for_status "http://127.0.0.1:$(host_port "$c3" 9000)/api/health" 200 30

# --- 4. Misconfiguration: unhealthy, named in the log, secrets not printed -------------------
c4="$(start nomodel 8080 -e "LLM_API_KEY=$SECRET_LLM" -e "FUNDRAISINGBOX_APITOKEN=$SECRET_FB" \
  -e INITIAL_ADMIN_EMAIL=admin@example.org -e "INITIAL_ADMIN_PASSWORD=$SECRET_ADMIN" -v "$volume:/data")"
check "without LLM_MODEL the health check is 503" wait_for_status "http://127.0.0.1:$(host_port "$c4" 8080)/api/health" 503 30
logs4="$(docker logs "$c4" 2>&1)"
check "the log names the missing setting" bash -c 'grep -q "LLM_MODEL" <<<"$1"' _ "$logs4"
check "the log does not print secret values" \
  bash -c '! grep -q -e "$1" -e "$2" -e "$3" <<<"$4"' _ "$SECRET_LLM" "$SECRET_FB" "$SECRET_ADMIN" "$logs4"

# --- 4b. No accounts and no first-admin settings: unhealthy, and the log says what to set -----
c6="$(start noadmin 8080 "${app_env[@]}" -v "$empty_volume:/data")"
check "with no accounts and no first-admin settings the health check is 503" \
  wait_for_status "http://127.0.0.1:$(host_port "$c6" 8080)/api/health" 503 30
check "the log names the first-admin settings" \
  bash -c 'docker logs "$1" 2>&1 | grep -q "INITIAL_ADMIN_EMAIL"' _ "$c6"

# --- 5. Data directory not writable: unhealthy ------------------------------------------------
c5="$(start rodata 8080 "${good_env[@]}" -v "$volume:/data:ro")"
check "a read-only /data makes the health check 503" wait_for_status "http://127.0.0.1:$(host_port "$c5" 8080)/api/health" 503 30
check "the log says /data is not writable" bash -c 'docker logs "$1" 2>&1 | grep -q "not writable"' _ "$c5"

# --- 6. Mock mode with no FundraisingBox token: healthy, says so, sends nothing out -----------
# A stand-in model endpoint on this machine returns a fixed card, so no model key is needed.
stub_dir="$(mktemp -d)"
cat >"$stub_dir/stub.py" <<'PY'
import json, sys
from http.server import BaseHTTPRequestHandler, HTTPServer

CARD = {"salutation": "Frau", "title": "", "first_name": "Anna", "last_name": "Meier",
        "company": "Acme GmbH", "position": "Leiterin", "email": "anna@acme.org",
        "phone": "+49 30 1234", "mobile": "", "street": "Hauptstr. 1", "postal_code": "10115",
        "city": "Berlin", "country": "Deutschland", "website": "https://acme.org", "notes": ""}

class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        self.rfile.read(int(self.headers.get("content-length", 0)))
        body = json.dumps({"choices": [{"message": {"content": json.dumps(CARD)}}]}).encode()
        self.send_response(200)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
    def log_message(self, *args):
        pass

server = HTTPServer(("0.0.0.0", 0), Handler)
print(server.server_address[1], flush=True)
server.serve_forever()
PY
python3 "$stub_dir/stub.py" >"$stub_dir/port" &
stub_pid=$!
for _ in 1 2 3 4 5 6 7 8 9 10; do [ -s "$stub_dir/port" ] && break; sleep 0.3; done
stub_port="$(cat "$stub_dir/port")"
base64 -d >"$stub_dir/card.jpg" <<'B64'
/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDABsSFBcUERsXFhceHBsgKEIrKCUlKFE6PTBCYFVlZF9VXVtqeJmBanGQc1tdhbWGkJ6jq62rZ4C8ybqmx5moq6T/2wBDARweHigjKE4rK06kbl1upKSkpKSkpKSkpKSkpKSkpKSkpKSkpKSkpKSkpKSkpKSkpKSkpKSkpKSkpKSkpKSkpKT/wAARCABQAHgDASIAAhEBAxEB/8QAHwAAAQUBAQEBAQEAAAAAAAAAAAECAwQFBgcICQoL/8QAtRAAAgEDAwIEAwUFBAQAAAF9AQIDAAQRBRIhMUEGE1FhByJxFDKBkaEII0KxwRVS0fAkM2JyggkKFhcYGRolJicoKSo0NTY3ODk6Q0RFRkdISUpTVFVWV1hZWmNkZWZnaGlqc3R1dnd4eXqDhIWGh4iJipKTlJWWl5iZmqKjpKWmp6ipqrKztLW2t7i5usLDxMXGx8jJytLT1NXW19jZ2uHi4+Tl5ufo6erx8vP09fb3+Pn6/8QAHwEAAwEBAQEBAQEBAQAAAAAAAAECAwQFBgcICQoL/8QAtREAAgECBAQDBAcFBAQAAQJ3AAECAxEEBSExBhJBUQdhcRMiMoEIFEKRobHBCSMzUvAVYnLRChYkNOEl8RcYGRomJygpKjU2Nzg5OkNERUZHSElKU1RVVldYWVpjZGVmZ2hpanN0dXZ3eHl6goOEhYaHiImKkpOUlZaXmJmaoqOkpaanqKmqsrO0tba3uLm6wsPExcbHyMnK0tPU1dbX2Nna4uPk5ebn6Onq8vP09fb3+Pn6/9oADAMBAAIRAxEAPwDVooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooA//Z
B64

mock_env=(-e LLM_MODEL=smoke-model -e LLM_API_KEY=dummy -e "LLM_BASE_URL=http://host.docker.internal:$stub_port/v1"
  -e FUNDRAISINGBOX_MODE=mock -e AUTH_COOKIE_SECURE=false
  -e INITIAL_ADMIN_EMAIL=admin@example.org -e "INITIAL_ADMIN_PASSWORD=$SECRET_ADMIN")
c7="$(start mock 8080 "${mock_env[@]}" --add-host host.docker.internal:host-gateway -v "$mock_volume:/data")"
base7="http://127.0.0.1:$(host_port "$c7" 8080)"
check "mock mode with no FundraisingBox token is healthy" wait_for_status "$base7/api/health" 200 30
check "the health response says it is mock" grep -q '"fundraisingbox":"mock"' <<<"$(curl -s "$base7/api/health")"
: >"$jar"
api -o /dev/null -X POST -d "{\"email\":\"admin@example.org\",\"password\":\"$SECRET_ADMIN\"}" "$base7/api/auth/login"
check "the app reports mock mode to a signed-in user" grep -q '"fundraisingbox_mode":"mock"' <<<"$(api "$base7/api/app-info")"
session="$(curl -s -b "$jar" -H 'X-Requested-With: smoke' -F "file=@$stub_dir/card.jpg;type=image/jpeg" "$base7/api/sessions")"
session_id="$(sed -n 's/.*"id":"\([^"]*\)".*/\1/p' <<<"$session")"
check "a card can be scanned (stand-in model)" test -n "$session_id"
contact='{"first_name":"Anna","last_name":"Meier","company":"Acme GmbH","email":"anna@acme.org","phone":"+49 30 1234","street":"Hauptstr. 1","postal_code":"10115","city":"Berlin","country":"Deutschland","website":"https://acme.org"}'
sent="$(api -X POST -d "{\"contact\":$contact,\"company\":{\"mode\":\"none\"},\"preferences\":{\"newsletter\":true}}" "$base7/api/sessions/$session_id/send")"
check "the send succeeds with a demo record id" grep -Eq '"person_id":"9[0-9]+"' <<<"$sent"
check "the preview holds the person and its email, phone, address and website records" \
  bash -c 'for k in "\"person\"" "\"emails\"" "\"phones\"" "\"addresses\"" "\"websites\""; do grep -q "$k" <<<"$1" || exit 1; done' _ "$sent"
check "the preview links the details to the new person" grep -q '"fb_person_id":9' <<<"$sent"
check "the ticked newsletter option is in the preview and no contact flag is" \
  bash -c 'grep -q "\"wants_newsletter\":true" <<<"$1" && ! grep -q "wants_no_" <<<"$1"' _ "$sent"
check "no contact data is left in the preview's info text" bash -c '! grep -q "Email:" <<<"$1"' _ "$sent"
kill "$stub_pid" 2>/dev/null
rm -rf "$stub_dir"

echo
if [ "$failures" -eq 0 ]; then echo "All smoke checks passed."; else echo "$failures check(s) failed."; exit 1; fi
