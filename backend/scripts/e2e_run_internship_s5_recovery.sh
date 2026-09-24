#!/usr/bin/env bash
# E2E-only S5 recovery gate. It refuses non-local/non-test databases.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

: "${DATABASE_URL:?DATABASE_URL is required}"
: "${TEST_DATABASE_URL:?TEST_DATABASE_URL is required}"
: "${DB_HOST:?DB_HOST is required}"
: "${DB_NAME:?DB_NAME is required}"
: "${DB_PASSWORD:?DB_PASSWORD is required}"
: "${BACKUP_DIR:?BACKUP_DIR is required}"
: "${UPLOAD_DIR:?UPLOAD_DIR is required}"
: "${E2E_EXPECTED_SHA:?E2E_EXPECTED_SHA is required}"
: "${E2E_PRODUCT_EXACT_SHA:?E2E_PRODUCT_EXACT_SHA is required}"
S5_PORT="${S5_PORT:-8000}"

case "${APP_ENV:-}" in
  prod|production) echo "S5 E2E gate refuses APP_ENV=${APP_ENV}" >&2; exit 2 ;;
esac
case "${DEPLOYMENT_MODE:-}" in
  prod|production|staging) echo "S5 E2E gate refuses DEPLOYMENT_MODE=${DEPLOYMENT_MODE}" >&2; exit 2 ;;
esac
case "$DB_HOST" in
  127.0.0.1|localhost|::1) ;;
  *) echo "S5 E2E gate requires local DB_HOST, got $DB_HOST" >&2; exit 2 ;;
esac
case "${DB_NAME,,}" in
  *e2e*|*test*) ;;
  *) echo "S5 E2E gate requires an e2e/test DB_NAME, got $DB_NAME" >&2; exit 2 ;;
esac
test "${E2E_ALLOW_DESTRUCTIVE_TESTS:-}" = "true"

ACTUAL="$(git rev-parse HEAD)"
test "$ACTUAL" = "$E2E_EXPECTED_SHA"
git cat-file -e "$E2E_PRODUCT_EXACT_SHA^{commit}"

mkdir -p e2e/runtime e2e/runtime-logs "$BACKUP_DIR" "$UPLOAD_DIR"
BOOT_PID=""
FINAL_PID=""
cleanup() {
  for pid in "$FINAL_PID" "$BOOT_PID"; do
    if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
      kill "$pid" 2>/dev/null || true
      wait "$pid" 2>/dev/null || true
    fi
  done
}
trap cleanup EXIT

wait_health() {
  local log_file="$1"
  for _ in {1..60}; do
    if curl -fsS "http://127.0.0.1:${S5_PORT}/health" >/dev/null; then
      return 0
    fi
    sleep 2
  done
  cat "$log_file" >&2 || true
  return 1
}

assert_guardian_route_auth_gate() {
  local path="$1"
  local body_file="e2e/runtime/guardian-route-${2}.json"
  local code
  code="$(curl -sS -o "$body_file" -w '%{http_code}' \
    -H 'Content-Type: application/json' \
      -X POST --data '{}' "http://127.0.0.1:${S5_PORT}${path}")"
  case "$code" in
    401|403)
      echo "[s5-route] ${path} registered and auth-gated HTTP=${code}"
      ;;
    *)
      echo "[s5-route] ${path} unexpected HTTP=${code}" >&2
      cat "$body_file" >&2 || true
      return 1
      ;;
  esac
}

stop_pid() {
  local pid="$1"
  [ -n "$pid" ] || return 0
  kill "$pid"
  for _ in {1..30}; do
    if ! kill -0 "$pid" 2>/dev/null; then
      wait "$pid" 2>/dev/null || true
      return 0
    fi
    sleep 1
  done
  echo "process $pid did not stop cleanly" >&2
  return 1
}

pushd backend >/dev/null
HEADS="$(python -m alembic heads | grep -c '(head)')"
python -m alembic heads
test "$HEADS" = "1"
python -m alembic upgrade head
python -m alembic current
python scripts/bootstrap_control_plane_school_iam_authority.py
python scripts/e2e_seed_playwright_tenants.py
python scripts/e2e_seed_control_plane_school_iam.py

nohup uvicorn app.main:app --host 127.0.0.1 --port "$S5_PORT" > ../e2e/runtime-logs/s5-bootstrap-backend.log 2>&1 &
BOOT_PID=$!
popd >/dev/null
wait_health "e2e/runtime-logs/s5-bootstrap-backend.log"

pushd backend >/dev/null
python scripts/e2e_bootstrap_graduation_accounts_ci.py
python scripts/e2e_reset_graduation_passwords.py
python scripts/e2e_verify_graduation_accounts.py
python scripts/e2e_seed_internship_sandbox.py
popd >/dev/null

stop_pid "$BOOT_PID"
BOOT_PID=""

pushd backend >/dev/null
E2E_S5_PHASE=snapshot python scripts/e2e_verify_internship_s5_recovery.py
popd >/dev/null

bash deploy/backup/backup-mysql.sh
S5_MANIFEST="$(find "$BACKUP_DIR" -maxdepth 1 -name 'manifest_*.json' -type f | sort | tail -1)"
test -n "$S5_MANIFEST"
export S5_MANIFEST
cat "$S5_MANIFEST"
(
  cd "$BACKUP_DIR"
  sha256sum -c "$(basename "$S5_MANIFEST").sha256"
)

pushd backend >/dev/null
python -m alembic upgrade head
test "$(python -m alembic heads | grep -c '(head)')" = "1"
python -m alembic current

test "${MOCK_LOGIN_ENABLED:-}" = "false"
nohup uvicorn app.main:app --host 127.0.0.1 --port "$S5_PORT" > ../e2e/runtime-logs/s5-final-backend.log 2>&1 &
FINAL_PID=$!
popd >/dev/null
wait_health "e2e/runtime-logs/s5-final-backend.log"

# Probe the already-running final-RC backend itself. These two product routes must
# exist in the real runtime and reject an unauthenticated caller; 404/405 or any
# successful/unguarded response is a hard failure.
assert_guardian_route_auth_gate "/api/v1/internship/compliance/consents/deliver" deliver
assert_guardian_route_auth_gate "/api/v1/internship/compliance/consents/1/redeliver" redeliver

pushd backend >/dev/null
E2E_S5_PHASE=verify-upgraded python scripts/e2e_verify_internship_s5_recovery.py
# Guardian route reachability is intentionally sealed by the live final-RC HTTP
# probes above plus S6 source closure. Do not re-import the app through pytest's
# DB-disabled conftest here: that creates a different bootstrap topology and can
# only add runner noise, not stronger production evidence.
# Inject explicit candidate-only damage while the backed-up canonical fixture still exists.
# The subsequent real-MySQL smoke is intentionally allowed to mutate/clean current candidate data;
# governed restore must recover both that drift and the explicit DB/file damage below.
E2E_S5_PHASE=mutate python scripts/e2e_verify_internship_s5_recovery.py
pytest tests/test_internship_e_series_final_mysql.py -q -p no:warnings \
  -k 'hot_position_headcount_one_has_exactly_one_winner or student_enterprise_school_chain_closes_one_canonical_placement'
popd >/dev/null

stop_pid "$FINAL_PID"
FINAL_PID=""

bash deploy/backup/restore-backup-set.sh "$S5_MANIFEST"

pushd backend >/dev/null
E2E_S5_PHASE=verify-restored python scripts/e2e_verify_internship_s5_recovery.py
python -m alembic current
popd >/dev/null
python scripts/check/check-internship-production-contracts.py

python - <<'PY'
import json
import os
from pathlib import Path
state = json.loads(Path(os.environ["E2E_S5_STATE_FILE"]).read_text(encoding="utf-8"))
assert state.get("verified") is True
assert state.get("phase") == "RESTORE_VERIFIED"
print(json.dumps({
    "gate": "S5",
    "status": "PASS",
    "productExactSha": state.get("productExactSha"),
    "runnerExactSha": state.get("runnerExactSha"),
    "alembicRevision": state["restoredSchema"]["alembicRevision"],
    "trackedTableCount": len(state["restoredTableCounts"]),
    "uniqueIndexes": state["restoredSchema"]["uniqueIndexes"],
    "fileBindingRestored": True,
    "historicalReadsRestored": True,
    "guardianRuntimeRoutesAuthGated": True,
}, ensure_ascii=False, sort_keys=True))
PY
