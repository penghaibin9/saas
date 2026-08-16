#!/usr/bin/env bash
set -euo pipefail

: "${MAIN_SHA:?}"
: "${A_SHA:?}"
: "${B_SHA:?}"
: "${C_SHA:?}"
: "${INT_SHA:?}"
: "${EXACT_D_SHA:?}"

EXPECTED_MAIN_SHA="$MAIN_SHA"
EXPECTED_A_SHA="$A_SHA"
EXPECTED_B_SHA="$B_SHA"
EXPECTED_C_SHA="$C_SHA"
EXPECTED_INT_SHA="$INT_SHA"

HEAD_MATRIX=/tmp/academic-d-w5-head-matrix.txt
MERGE_LEDGER=/tmp/academic-d-w5-merge-ledger.txt
CONTRACT_INVENTORY=/tmp/academic-d-w5-contract-inventory.txt
EVIDENCE=/tmp/academic-d-w5-evidence.txt
JUNIT=/tmp/academic-d-w5-targeted.xml
ALEMBIC_CURRENT=/tmp/academic-d-w5-alembic-current.txt

actual_d="$(git rev-parse HEAD)"
test "$actual_d" = "$EXACT_D_SHA"

git fetch --no-tags origin \
  "+refs/heads/main:refs/remotes/origin/main" \
  "+refs/heads/agent/academic-a-semester-core:refs/remotes/origin/agent/academic-a-semester-core" \
  "+refs/heads/agent/academic-b-schedule-selection:refs/remotes/origin/agent/academic-b-schedule-selection" \
  "+refs/heads/agent/academic-c-teaching-execution:refs/remotes/origin/agent/academic-c-teaching-execution" \
  "+refs/heads/integration/academic-school-gold:refs/remotes/origin/integration/academic-school-gold"

# PRE-GOLD is allowed to consume a single immutable snapshot of active A/B/C/INT heads.
# Final Gold will replace this with frozen contract pins after all upstream lines stop moving.
MAIN_SHA="$(git rev-parse origin/main)"
A_SHA="$(git rev-parse origin/agent/academic-a-semester-core)"
B_SHA="$(git rev-parse origin/agent/academic-b-schedule-selection)"
C_SHA="$(git rev-parse origin/agent/academic-c-teaching-execution)"
INT_SHA="$(git rev-parse origin/integration/academic-school-gold)"
SNAPSHOT_UTC="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

cat > "$HEAD_MATRIX" <<EOF
snapshot_mode=JOB_START_FETCH
snapshot_utc=$SNAPSHOT_UTC
expected_main=$EXPECTED_MAIN_SHA
expected_a=$EXPECTED_A_SHA
expected_b=$EXPECTED_B_SHA
expected_c=$EXPECTED_C_SHA
expected_int=$EXPECTED_INT_SHA
main=$MAIN_SHA
a=$A_SHA
b=$B_SHA
c=$C_SHA
d=$EXACT_D_SHA
int=$INT_SHA
main_drifted=$([[ "$MAIN_SHA" == "$EXPECTED_MAIN_SHA" ]] && echo false || echo true)
a_drifted=$([[ "$A_SHA" == "$EXPECTED_A_SHA" ]] && echo false || echo true)
b_drifted=$([[ "$B_SHA" == "$EXPECTED_B_SHA" ]] && echo false || echo true)
c_drifted=$([[ "$C_SHA" == "$EXPECTED_C_SHA" ]] && echo false || echo true)
int_drifted=$([[ "$INT_SHA" == "$EXPECTED_INT_SHA" ]] && echo false || echo true)
EOF
cat "$HEAD_MATRIX"

git config user.name "academic-d-w5-final-gold"
git config user.email "academic-d-w5-final-gold@invalid.local"
git switch --detach "$MAIN_SHA"
: > "$MERGE_LEDGER"

merge_layer() {
  local layer="$1"
  local sha="$2"
  echo "[merge] $layer $sha" | tee -a "$MERGE_LEDGER"
  if ! git merge --no-ff --no-edit "$sha"; then
    echo "[conflicts] $layer" | tee -a "$MERGE_LEDGER"
    git diff --name-only --diff-filter=U | tee -a "$MERGE_LEDGER"
    exit 1
  fi
  echo "[merged] $layer tree=$(git rev-parse HEAD^{tree}) commit=$(git rev-parse HEAD)" | tee -a "$MERGE_LEDGER"
  git diff --check HEAD^
}

merge_layer A "$A_SHA"
merge_layer B "$B_SHA"
merge_layer C "$C_SHA"
merge_layer D "$EXACT_D_SHA"
merge_layer INT "$INT_SHA"

test -z "$(git status --porcelain)"

cd backend

mysql -h127.0.0.1 -uroot -proot -e '
  DROP DATABASE IF EXISTS student_lifecycle_test;
  CREATE DATABASE student_lifecycle_test CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
'
test "$(alembic heads | grep -c '(head)')" -eq 1
alembic upgrade head
alembic current | tee "$ALEMBIC_CURRENT"

files=(
  tests/test_aa_school_setup_program_post_confirm_pipeline_int.py
  tests/test_academic_int_ac4_schema_mysql.py
  tests/test_academic_int_c1_attendance_backfill_mysql.py
  tests/test_aa_selection_w6_roster_reconcile_mysql.py
  tests/test_aa_attendance_published_occurrence_contract.py
  tests/test_aa_graduation_d_w0_scope_guard.py
  tests/test_aa_archive_d_w1_authority_regressions.py
  tests/test_aa_semester_pilot_r11.py
  tests/test_aa_main_permission_middleware_compat.py
)
printf '%s\n' "${files[@]}" | tee "$CONTRACT_INVENTORY"
for file in "${files[@]}"; do test -f "$file"; done

pytest -q -p no:warnings \
  "${files[@]}" \
  --maxfail=1 \
  --junitxml="$JUNIT"

cat > "$EVIDENCE" <<EOF
w5_phase=PRE_GOLD_REPLAY
snapshot_mode=JOB_START_FETCH
snapshot_utc=$SNAPSHOT_UTC
d_source_commit=$EXACT_D_SHA
main_commit=$MAIN_SHA
a_commit=$A_SHA
b_commit=$B_SHA
c_commit=$C_SHA
int_commit=$INT_SHA
clean_tenant_schema_proven=true
migrated_tenant_contracts_proven=true
permission_negative_contract_included=true
datascope_negative_contract_included=true
cross_tenant_sentinel_included=true
r11_contract_included=true
twenty_k_proven_on_w5_head=false
outbox_recovery_proven_on_w5_head=false
mysql_pitr_proven_on_w5_head=false
fileobject_restore_proven_on_w5_head=false
final_browser_gold_proven_on_w5_head=false
upstream_contract_heads_frozen=false
w5_final_gold=false
EOF
sha256sum "$EVIDENCE" > "${EVIDENCE}.sha256"
sha256sum -c "${EVIDENCE}.sha256"
