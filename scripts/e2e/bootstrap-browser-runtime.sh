#!/usr/bin/env bash
set -euo pipefail

ROOT="${GITHUB_WORKSPACE:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
PROFILE="${BROWSER_RUNTIME_PROFILE:-graduation}"
EXPECTED_SHA="${E2E_EXPECTED_SHA:?E2E_EXPECTED_SHA is required}"
VERIFY_GOLD="${VERIFY_GOLD_MANIFEST:-false}"
LOG_DIR="$ROOT/e2e/runtime-logs"
mkdir -p "$LOG_DIR"

log() { printf '\n[browser-runtime] %s\n' "$*"; }

if [[ "$PROFILE" != "graduation" && "$PROFILE" != "full" ]]; then
  echo "unsupported BROWSER_RUNTIME_PROFILE=$PROFILE" >&2
  exit 2
fi

cd "$ROOT"
ACTUAL_SHA="$(git rev-parse HEAD)"
log "exact-head actual=$ACTUAL_SHA expected=$EXPECTED_SHA profile=$PROFILE"
test "$ACTUAL_SHA" = "$EXPECTED_SHA"
if [[ "$VERIFY_GOLD" == "true" ]]; then
  git diff --exit-code -- e2e/gold/graduation-v9-gold-manifest.json
fi

log "install backend and verify the complete workflow/action/bootstrap safety graph"
python -m pip install -r backend/requirements.txt
(
  cd backend
  pytest tests/test_playwright_artifact_safety.py -q -p no:warnings
)

log "migrate one isolated MySQL and seed common school authority"
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
  log "materialize full-suite organization prerequisites before canonical account import"
  (
    cd backend
    python scripts/e2e_bootstrap_affairs_counselor_ci.py
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
    e2e/academic-b-w3-fixture.json \
    e2e/academic-b-w4-fixture.json \
    e2e/academic-b-w4-formation-fixture.json \
    e2e/academic-archive-correction-w1-fixture.json \
    e2e/academic-exam-incident-w2-fixture.json; do
    test -s "$fixture"
  done
fi

log "import and verify the canonical graduation identities after organization prerequisites"
(
  cd backend
  python scripts/e2e_bootstrap_graduation_accounts_ci.py
  python scripts/e2e_reset_graduation_passwords.py
  python scripts/e2e_verify_graduation_accounts.py
)

if [[ "$PROFILE" == "full" ]]; then
  log "materialize identity-dependent full-suite fixtures"
  (
    cd backend
    python scripts/e2e_seed_academic_b_w5_selection.py
    python scripts/e2e_seed_internship_sandbox.py
  )
  test -s e2e/academic-b-w5-fixture.json
fi

log "start backend and message delivery worker"
(
  cd backend
  nohup uvicorn app.main:app --host 127.0.0.1 --port 8000 > "$LOG_DIR/backend.log" 2>&1 &
  echo $! > "$LOG_DIR/backend.pid"
  nohup python -c "import time; from scripts.run_scheduled_jobs import job_delivery_and_outbox; exec('while True:\\n    job_delivery_and_outbox()\\n    time.sleep(2)')" > "$LOG_DIR/message-delivery.log" 2>&1 &
  echo $! > "$LOG_DIR/message-delivery.pid"
)

log "install and start staff PC"
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

URLS=(
  "http://127.0.0.1:8000/health"
  "http://127.0.0.1:5173/login"
  "http://127.0.0.1:5199/portal/login"
  "http://127.0.0.1:5188/"
)

if [[ "$PROFILE" == "full" ]]; then
  log "install and start enterprise portal"
  (
    cd enterprise-portal
    npm ci
    nohup env VITE_BASE=/enterprise/ VITE_API_BASE_URL=/ VITE_PROXY_TARGET=http://127.0.0.1:8000 npm run dev -- --host 127.0.0.1 --port 5202 > "$LOG_DIR/enterprise-portal.log" 2>&1 &
    echo $! > "$LOG_DIR/enterprise-portal.pid"
  )
  URLS+=("http://127.0.0.1:5202/enterprise/login")
fi

log "wait for runtime readiness"
for url in "${URLS[@]}"; do
  ready=''
  for _ in {1..90}; do
    if curl -fsS "$url" >/dev/null; then
      ready=1
      break
    fi
    sleep 2
  done
  if [[ -z "$ready" ]]; then
    echo "application not ready: $url" >&2
    tail -n 200 "$LOG_DIR"/*.log 2>/dev/null || true
    exit 1
  fi
  echo "[browser-runtime] ready $url"
done

log "install Playwright once for this runtime"
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
    'surfaces': ['backend', 'staff-pc', 'student-pc', 'teacher-miniapp-h5'] + (
        ['enterprise-portal'] if os.environ.get('BROWSER_RUNTIME_PROFILE') == 'full' else []
    ),
}
Path('e2e/runtime-logs/runtime-provenance.json').write_text(
    json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8'
)
PY

log "runtime ready"
