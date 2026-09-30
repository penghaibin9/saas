#!/usr/bin/env bash
set -euo pipefail

ROOT="${GITHUB_WORKSPACE:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
PROFILE="${BROWSER_RUNTIME_PROFILE:-graduation}"
EXPECTED_SHA="${E2E_EXPECTED_SHA:?E2E_EXPECTED_SHA is required}"
VERIFY_GOLD="${VERIFY_GOLD_MANIFEST:-false}"
LOG_DIR="$ROOT/e2e/runtime-logs"
BACKEND_HEALTH_URL="http://127.0.0.1:8000/health"
CURRENT_PHASE="init"
mkdir -p "$LOG_DIR"

log() { printf '\n[browser-runtime] phase=%s %s\n' "$CURRENT_PHASE" "$*"; }

phase() {
  CURRENT_PHASE="$1"
  shift
  log "$*"
}

fail() {
  echo "[browser-runtime] phase=$CURRENT_PHASE ERROR: $*" >&2
  tail -n 200 "$LOG_DIR"/*.log 2>/dev/null || true
  exit 1
}

wait_for_url() {
  local url="$1"
  local label="$2"
  local attempts="${3:-90}"
  local attempt

  for ((attempt = 1; attempt <= attempts; attempt += 1)); do
    if curl -fsS --max-time 5 "$url" >/dev/null; then
      echo "[browser-runtime] phase=$CURRENT_PHASE ready=$label url=$url attempt=$attempt"
      return 0
    fi
    sleep 2
  done

  fail "$label did not become ready at $url"
}

require_backend_ready() {
  local consumer="$1"
  if ! curl -fsS --max-time 5 "$BACKEND_HEALTH_URL" >/dev/null; then
    fail "API-dependent bootstrap '$consumer' attempted before backend readiness"
  fi
}

run_api_bootstrap() {
  local label="$1"
  shift
  require_backend_ready "$label"
  log "api-bootstrap=$label"
  (
    cd "$ROOT/backend"
    "$@"
  )
}

if [[ "$PROFILE" != "graduation" && "$PROFILE" != "full" ]]; then
  echo "unsupported BROWSER_RUNTIME_PROFILE=$PROFILE" >&2
  exit 2
fi

cd "$ROOT"
ACTUAL_SHA="$(git rev-parse HEAD)"
phase "exact-head" "actual=$ACTUAL_SHA expected=$EXPECTED_SHA profile=$PROFILE"
test "$ACTUAL_SHA" = "$EXPECTED_SHA"
if [[ "$VERIFY_GOLD" == "true" ]]; then
  git diff --exit-code -- e2e/gold/graduation-v9-gold-manifest.json
fi

phase "architecture-contract" "verify the shared workflow/action/bootstrap ownership and phase graph"
node scripts/check/check-graduation-browser-architecture.mjs

phase "backend-dependencies" "install backend and run the complete runtime safety contract"
python -m pip install -r backend/requirements.txt
(
  cd backend
  pytest tests/test_playwright_artifact_safety.py -q -p no:warnings
)

phase "database-foundation" "migrate one isolated MySQL and seed common school authority"
(
  cd backend
  test "$(python -m alembic heads | grep -c '(head)')" = '1'
  python -m alembic upgrade head
  python ../scripts/check/check-migrated-schema-parity.py
  python scripts/bootstrap_control_plane_school_iam_authority.py
  python scripts/e2e_seed_playwright_tenants.py
  python scripts/e2e_seed_control_plane_school_iam.py
)

if [[ "$PROFILE" == "full" ]]; then
  phase "database-domain-prerequisites" "materialize DB-only full-suite organization and academic facts"
  (
    cd backend
    python scripts/e2e_seed_academic_b_selection.py
    python scripts/e2e_seed_academic_b_w3_schedule.py
    python scripts/e2e_seed_academic_b_w4_selection.py
    python scripts/e2e_seed_academic_b_w4_formation.py
    python scripts/e2e_seed_academic_archive_correction_w1.py
    python - <<'PY'
from app.services.school_iam_authority_service import converge_school_iam_authority
converge_school_iam_authority(
    source='unified-browser-runtime',
    source_commit_sha=__import__('os').environ['E2E_EXPECTED_SHA'],
    actor_user_id=None,
)
print('[browser-runtime] school IAM authority converged')
PY
    python scripts/e2e_seed_academic_exam_incident_w2.py
  )
  for fixture in \
    e2e/academic-b-w1-fixture.json \
    e2e/academic-b-w3-fixture.json \
    e2e/academic-b-w4-fixture.json \
    e2e/academic-b-w4-formation-fixture.json \
    e2e/academic-archive-correction-w1-fixture.json \
    e2e/academic-exam-incident-w2-fixture.json; do
    test -s "$fixture"
  done
fi

phase "backend-api" "start backend before every API-dependent identity bootstrap"
(
  cd backend
  nohup uvicorn app.main:app --host 127.0.0.1 --port 8000 > "$LOG_DIR/backend.log" 2>&1 &
  echo $! > "$LOG_DIR/backend.pid"
)
wait_for_url "$BACKEND_HEALTH_URL" "backend API"

phase "api-identity-bootstrap" "import and verify canonical identities through production APIs"
run_api_bootstrap "graduation canonical identity import" \
  python scripts/e2e_bootstrap_graduation_accounts_ci.py
run_api_bootstrap "graduation password normalization" \
  python scripts/e2e_reset_graduation_passwords.py
run_api_bootstrap "graduation identity verification" \
  python scripts/e2e_verify_graduation_accounts.py

if [[ "$PROFILE" == "full" ]]; then
  run_api_bootstrap "student-affairs counselor canonical identity" \
    python scripts/e2e_bootstrap_affairs_counselor_ci.py
fi

if [[ "$PROFILE" == "full" ]]; then
  phase "identity-dependent-fixtures" "materialize facts that depend on canonical user identities"
  (
    cd backend
    python scripts/e2e_seed_academic_b_w5_selection.py
    python scripts/e2e_seed_internship_sandbox.py
  )
  test -s e2e/academic-b-w5-fixture.json
fi

phase "background-workers" "start message delivery only after canonical identity state is stable"
(
  cd backend
  nohup python -c "import time; from scripts.run_scheduled_jobs import job_delivery_and_outbox; exec('while True:\\n    job_delivery_and_outbox()\\n    time.sleep(2)')" > "$LOG_DIR/message-delivery.log" 2>&1 &
  echo $! > "$LOG_DIR/message-delivery.pid"
)

phase "client-surfaces" "install and start staff PC"
(
  cd frontend
  npm ci
  nohup env VITE_USE_MOCK=false VITE_API_BASE_URL=http://127.0.0.1:8000 npm run dev -- --host 127.0.0.1 --port 5173 > "$LOG_DIR/frontend.log" 2>&1 &
  echo $! > "$LOG_DIR/frontend.pid"
)

log "install and start student PC"
(
  cd student-portal
  npm ci
  nohup env VITE_BASE=/portal/ VITE_API_BASE_URL=/ VITE_PROXY_TARGET=http://127.0.0.1:8000 npm run dev -- --host 127.0.0.1 --port 5199 > "$LOG_DIR/student-portal.log" 2>&1 &
  echo $! > "$LOG_DIR/student-portal.pid"
)

log "install and start teacher miniapp H5"
(
  cd miniapp
  npm ci
  nohup env VITE_USE_MOCK=false VITE_API_BASE_URL=http://127.0.0.1:8000 npm run dev:h5 -- --host 127.0.0.1 --port 5188 > "$LOG_DIR/miniapp.log" 2>&1 &
  echo $! > "$LOG_DIR/miniapp.pid"
)

CLIENT_URLS=(
  "http://127.0.0.1:5173/login|staff PC"
  "http://127.0.0.1:5199/portal/login|student PC"
  "http://127.0.0.1:5188/|teacher miniapp H5"
)

if [[ "$PROFILE" == "full" ]]; then
  log "install and start enterprise portal"
  (
    cd enterprise-portal
    npm ci
    nohup env VITE_BASE=/enterprise/ VITE_API_BASE_URL=/ VITE_PROXY_TARGET=http://127.0.0.1:8000 npm run dev -- --host 127.0.0.1 --port 5202 > "$LOG_DIR/enterprise-portal.log" 2>&1 &
    echo $! > "$LOG_DIR/enterprise-portal.pid"
  )
  CLIENT_URLS+=("http://127.0.0.1:5202/enterprise/login|enterprise portal")
fi

phase "client-readiness" "wait for every browser surface after the backend and fixtures are stable"
for entry in "${CLIENT_URLS[@]}"; do
  IFS='|' read -r url label <<< "$entry"
  wait_for_url "$url" "$label"
done

phase "playwright-dependencies" "install Playwright once for this runtime"
(
  cd e2e
  npm ci
  npx playwright install --with-deps chromium
)

python - <<'PY'
import json
import os
from pathlib import Path
payload = {
    'head': os.environ['E2E_EXPECTED_SHA'],
    'profile': os.environ.get('BROWSER_RUNTIME_PROFILE', 'graduation'),
    'runId': os.environ.get('GITHUB_RUN_ID', 'local'),
    'runAttempt': os.environ.get('GITHUB_RUN_ATTEMPT', '1'),
    'mockLogin': os.environ.get('MOCK_LOGIN_ENABLED'),
    'database': 'mysql-8.4',
    'redisDatabase': os.environ.get('REDIS_URL', '').rsplit('/', 1)[-1],
    'phaseModel': [
        'database-foundation',
        'database-domain-prerequisites',
        'backend-api',
        'api-identity-bootstrap',
        'identity-dependent-fixtures',
        'background-workers',
        'client-surfaces',
        'playwright-dependencies',
    ],
    'surfaces': ['backend', 'staff-pc', 'student-pc', 'teacher-miniapp-h5'] + (
        ['enterprise-portal'] if os.environ.get('BROWSER_RUNTIME_PROFILE') == 'full' else []
    ),
}
Path('e2e/runtime-logs/runtime-provenance.json').write_text(
    json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8'
)
PY

phase "ready" "runtime ready"
