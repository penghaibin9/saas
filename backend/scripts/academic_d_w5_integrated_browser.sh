#!/usr/bin/env bash
set -euo pipefail

: "${EXACT_D_SHA:?}"

REPO_ROOT="$(pwd)"
W5_EVIDENCE=/tmp/academic-d-w5-evidence.txt
BROWSER_EVIDENCE=/tmp/academic-d-w5-integrated-browser.txt
BROWSER_PHASE="PRECHECK"
BROWSER_SUCCESS=false
INTEGRATED_COMMIT="$(git rev-parse HEAD)"
INTEGRATED_TREE="$(git rev-parse HEAD^{tree})"

mkdir -p e2e/runtime-logs

write_browser_evidence() {
  local rc="$1"
  cat > "$BROWSER_EVIDENCE" <<EOF
browser_phase=$BROWSER_PHASE
exit_code=$rc
browser_gold=$BROWSER_SUCCESS
d_source_commit=$EXACT_D_SHA
integrated_commit=$INTEGRATED_COMMIT
integrated_tree=$INTEGRATED_TREE
management_spec=academic-d-w0-w1-graduation-archive.spec.mjs
student_spec=academic-d-w5-student-graduation.spec.mjs
teacher_mobile_spec=graduation-v9-teacher-mobile-visual.spec.mjs
management_surface_proven=$BROWSER_SUCCESS
student_surface_proven=$BROWSER_SUCCESS
teacher_surface_proven=$BROWSER_SUCCESS
visible_click_proven=$BROWSER_SUCCESS
refresh_cross_role_suite_proven=$BROWSER_SUCCESS
EOF
  sha256sum "$BROWSER_EVIDENCE" > "${BROWSER_EVIDENCE}.sha256"
}

cleanup() {
  for pid_file in \
    e2e/runtime-logs/backend.pid \
    e2e/runtime-logs/frontend.pid \
    e2e/runtime-logs/student-portal.pid \
    e2e/runtime-logs/miniapp.pid; do
    if [[ -f "$pid_file" ]]; then
      kill "$(cat "$pid_file")" >/dev/null 2>&1 || true
    fi
  done
}

trap 'rc=$?; trap - EXIT; set +e; write_browser_evidence "$rc"; cleanup; exit "$rc"' EXIT

# Browser Gold is only legal after the fixed A -> B -> C -> D -> INT backend replay succeeded.
test -f "$W5_EVIDENCE"
grep -Fqx 'replay_success=true' "$W5_EVIDENCE"
grep -Fqx 'clean_tenant_schema_proven=true' "$W5_EVIDENCE"
grep -Fqx 'migrated_tenant_schema_proven=true' "$W5_EVIDENCE"
grep -Fqx 'migrated_tenant_contracts_proven=true' "$W5_EVIDENCE"
grep -Fqx "d_source_commit=$EXACT_D_SHA" "$W5_EVIDENCE"
git merge-base --is-ancestor "$EXACT_D_SHA" HEAD

authority_scripts=(
  backend/scripts/bootstrap_control_plane_school_iam_authority.py
  backend/scripts/e2e_seed_playwright_tenants.py
  backend/scripts/e2e_seed_control_plane_school_iam.py
  backend/scripts/e2e_bootstrap_graduation_accounts_ci.py
  backend/scripts/e2e_reset_graduation_passwords.py
  backend/scripts/e2e_verify_graduation_accounts.py
)
for path in "${authority_scripts[@]}"; do test -f "$path"; done

browser_specs=(
  e2e/specs/academic-d-w0-w1-graduation-archive.spec.mjs
  e2e/specs/academic-d-w5-student-graduation.spec.mjs
  e2e/specs/graduation-v9-teacher-mobile-visual.spec.mjs
)
for path in "${browser_specs[@]}"; do test -f "$path"; done

export CI=true
export PYTHONPATH=.
export APP_ENV=test
export DEPLOYMENT_MODE=local
export TRUSTED_PROXY_IPS=127.0.0.1/32
export DB_ENABLED=true
export DATABASE_URL='mysql+pymysql://root:root@127.0.0.1:3306/academic_d_w5_browser?charset=utf8mb4'
export TEST_DATABASE_URL="$DATABASE_URL"
export DB_HOST=127.0.0.1
export DB_PORT=3306
export DB_USER=root
export DB_PASSWORD=root
export DB_NAME=academic_d_w5_browser
export REDIS_URL=redis://127.0.0.1:6379/13
export REDIS_KEY_PREFIX=academic-d-w5-integrated-browser
export REDIS_CONNECT_TIMEOUT=2
export REDIS_SOCKET_TIMEOUT=2
export JWT_SECRET=academic-d-w5-integrated-browser-secret
export JWT_SECRET_KEY=academic-d-w5-integrated-browser-secret
export MOCK_LOGIN_ENABLED=false
export SMS_ENABLED=false
export SCHEDULER_MODE=external
export E2E_ALLOW_DESTRUCTIVE_TESTS=true
export E2E_API_BASE_URL=http://127.0.0.1:8000/api/v1
export E2E_STAFF_BASE_URL=http://127.0.0.1:5173
export E2E_STUDENT_BASE_URL=http://127.0.0.1:5199/portal
export E2E_MINIAPP_BASE_URL=http://localhost:5188
export E2E_EXPECTED_SHA="$EXACT_D_SHA"

BROWSER_PHASE="SCHEMA"
mysql -h127.0.0.1 -uroot -proot -e '
  DROP DATABASE IF EXISTS academic_d_w5_browser;
  CREATE DATABASE academic_d_w5_browser CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
'
(
  cd backend
  test "$(alembic heads | grep -c '(head)')" -eq 1
  alembic upgrade head
  python scripts/bootstrap_control_plane_school_iam_authority.py
  python scripts/e2e_seed_playwright_tenants.py
  python scripts/e2e_seed_control_plane_school_iam.py
)

BROWSER_PHASE="BACKEND_START"
(
  cd backend
  nohup uvicorn app.main:app --host 127.0.0.1 --port 8000 > ../e2e/runtime-logs/backend.log 2>&1 &
  echo $! > ../e2e/runtime-logs/backend.pid
)
for _ in $(seq 1 60); do
  if curl -fsS http://127.0.0.1:8000/health >/dev/null; then break; fi
  sleep 2
done
curl -fsS http://127.0.0.1:8000/health >/dev/null || { cat e2e/runtime-logs/backend.log; exit 1; }

BROWSER_PHASE="ACCOUNT_FIXTURES"
(
  cd backend
  python scripts/e2e_bootstrap_graduation_accounts_ci.py
  python scripts/e2e_reset_graduation_passwords.py
  python scripts/e2e_verify_graduation_accounts.py
)

BROWSER_PHASE="CLIENTS_START"
(
  cd frontend
  npm ci
  nohup npm run dev -- --host 127.0.0.1 --port 5173 > ../e2e/runtime-logs/frontend.log 2>&1 &
  echo $! > ../e2e/runtime-logs/frontend.pid
)
(
  cd student-portal
  npm ci
  VITE_BASE=/portal/ VITE_API_BASE_URL=/ VITE_PROXY_TARGET=http://127.0.0.1:8000 \
    nohup npm run dev -- --host 127.0.0.1 --port 5199 > ../e2e/runtime-logs/student-portal.log 2>&1 &
  echo $! > ../e2e/runtime-logs/student-portal.pid
)
(
  cd miniapp
  npm ci
  VITE_USE_MOCK=false VITE_API_BASE_URL=http://127.0.0.1:8000 \
    nohup npm run dev:h5 > ../e2e/runtime-logs/miniapp.log 2>&1 &
  echo $! > ../e2e/runtime-logs/miniapp.pid
)

for url in http://127.0.0.1:5173/login http://127.0.0.1:5199/portal/login http://localhost:5188/; do
  ready=false
  for _ in $(seq 1 60); do
    if curl -fsS "$url" >/dev/null; then ready=true; break; fi
    sleep 2
  done
  if [[ "$ready" != true ]]; then
    echo "Application not ready: $url" >&2
    cat e2e/runtime-logs/*.log || true
    exit 1
  fi
done

BROWSER_PHASE="PLAYWRIGHT_INSTALL"
(
  cd e2e
  npm install
  npx playwright install --with-deps chromium
)

BROWSER_PHASE="VISIBLE_CLICK_E2E"
(
  cd e2e
  npx playwright test \
    specs/academic-d-w0-w1-graduation-archive.spec.mjs \
    specs/academic-d-w5-student-graduation.spec.mjs \
    specs/graduation-v9-teacher-mobile-visual.spec.mjs \
    --workers=1 \
    --retries=0
)

BROWSER_PHASE="EVIDENCE_SEAL"
python - "$W5_EVIDENCE" "$INTEGRATED_COMMIT" "$INTEGRATED_TREE" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
updates = {
    "final_browser_gold_proven_on_w5_head": "true",
    "integrated_browser_commit": sys.argv[2],
    "integrated_browser_tree": sys.argv[3],
    "management_browser_surface_proven": "true",
    "student_browser_surface_proven": "true",
    "teacher_browser_surface_proven": "true",
}
lines = path.read_text(encoding="utf-8").splitlines()
seen = set()
out = []
for line in lines:
    if "=" not in line:
        out.append(line)
        continue
    key = line.split("=", 1)[0]
    if key in updates:
        out.append(f"{key}={updates[key]}")
        seen.add(key)
    else:
        out.append(line)
for key, value in updates.items():
    if key not in seen:
        out.append(f"{key}={value}")
path.write_text("\n".join(out) + "\n", encoding="utf-8")
PY
sha256sum "$W5_EVIDENCE" > "${W5_EVIDENCE}.sha256"
sha256sum -c "${W5_EVIDENCE}.sha256"
BROWSER_SUCCESS=true
BROWSER_PHASE="COMPLETE"
