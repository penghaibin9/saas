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

# INT imported the frozen C-C1 attendance consumer first, then added the shared
# persisted source/occurrence Authority. C subsequently promoted the public
# attendance surface to explicit relation-aware command/read delegates and reduced
# the historical attendance_service module to a compatibility export. W5 preserves
# those two final C facades plus their final relation-aware contracts while retaining
# the reviewed B/INT occurrence, warning, source-contract and exact-session miniapp
# handoff. Any other conflict fails closed.
INT_C1_IMPORT_SHA="93650baec930d7e4efd7b04e9ec851e5887a795b"
INT_SOURCE_AUTH_SHA="0703ec4fb11cab9b50d6bbaf4eddfbbea8091b62"
INT_C_HANDOFF_PATHS=(
  backend/app/modules/academic_affairs/services/academic_affairs_attendance_occurrence_consumer.py
  backend/app/modules/academic_affairs/services/academic_affairs_attendance_public_service.py
  backend/app/modules/academic_affairs/services/academic_affairs_attendance_service.py
  backend/app/modules/academic_affairs/services/academic_affairs_warning_service.py
  backend/tests/test_aa_attendance_admin_special_contract.py
  backend/tests/test_aa_attendance_class_options_formal_schedule.py
  backend/tests/test_aa_attendance_expected_schedule_item_contract.py
  backend/tests/test_aa_attendance_published_occurrence_contract.py
  backend/tests/test_aa_attendance_warning_source_contract.py
  miniapp/src/pages/teacher/academic-affairs/attendance.vue
  miniapp/tests/academic-attendance-source-contract.test.mjs
)
INT_C_HANDOFF_TAKE_INT=(
  backend/app/modules/academic_affairs/services/academic_affairs_attendance_occurrence_consumer.py
  backend/app/modules/academic_affairs/services/academic_affairs_warning_service.py
  backend/tests/test_aa_attendance_admin_special_contract.py
  backend/tests/test_aa_attendance_published_occurrence_contract.py
  backend/tests/test_aa_attendance_warning_source_contract.py
)
INT_C_HANDOFF_KEEP_C=(
  backend/app/modules/academic_affairs/services/academic_affairs_attendance_public_service.py
  backend/app/modules/academic_affairs/services/academic_affairs_attendance_service.py
  backend/tests/test_aa_attendance_class_options_formal_schedule.py
  backend/tests/test_aa_attendance_expected_schedule_item_contract.py
  miniapp/src/pages/teacher/academic-affairs/attendance.vue
  miniapp/tests/academic-attendance-source-contract.test.mjs
)
INT_C_HANDOFF_KEEP_C_UNTOUCHED=(
  miniapp/src/pages/teacher/academic-affairs/attendance.vue
  miniapp/tests/academic-attendance-source-contract.test.mjs
)
declare -A INT_C_HANDOFF_C_BLOBS=(
  [backend/app/modules/academic_affairs/services/academic_affairs_attendance_occurrence_consumer.py]="76f42d0f515fc9881aee87bfbaa1bb49b02b8ae3"
  [backend/app/modules/academic_affairs/services/academic_affairs_attendance_public_service.py]="1b1125cfa8d48c72e0efa5f7026a6754b4deec6e"
  [backend/app/modules/academic_affairs/services/academic_affairs_attendance_service.py]="bb6bb7a330be2ce08dc763f82e70e2b2d44d2728"
  [backend/app/modules/academic_affairs/services/academic_affairs_warning_service.py]="b442eef7ed496b03196bebb5e56c527d7c7c8fc5"
  [backend/tests/test_aa_attendance_admin_special_contract.py]="c394c83722727afb0985f58c487a88579ebeb081"
  [backend/tests/test_aa_attendance_class_options_formal_schedule.py]="5c6460b57d004df67f785ca50c1197494d217531"
  [backend/tests/test_aa_attendance_expected_schedule_item_contract.py]="1c837a29070401551af946cf8ac0a32d5cf88ed4"
  [backend/tests/test_aa_attendance_published_occurrence_contract.py]="d2d6b2e70b55d2a5d82427ac16f6c087bc1e6955"
  [backend/tests/test_aa_attendance_warning_source_contract.py]="6c1458a2c967630bf9f1dfc3d5e00b8b62d0305e"
  [miniapp/src/pages/teacher/academic-affairs/attendance.vue]="8153bddd3769309bf387cedf53217eb27b4398c8"
  [miniapp/tests/academic-attendance-source-contract.test.mjs]="1fe7efb1b673a598c13af80fde481b62b495d42f"
)
declare -A INT_C_HANDOFF_IMPORT_MINI_BLOBS=(
  [miniapp/src/pages/teacher/academic-affairs/attendance.vue]="9df52087dcbe47a37f3bca57b03430fc363d022c"
  [miniapp/tests/academic-attendance-source-contract.test.mjs]="a94116cefb269ed9db1c06eaf64cb58b799d31ea"
)
C_FINAL_RELATION_GUARD_PATH="backend/app/modules/academic_affairs/services/academic_affairs_attendance_teacher_relation_guard.py"
C_FINAL_RELATION_GUARD_BLOB="749194bfcea1299324bcd4d8ce6dd2a4181d0255"

# B is built on the shared INT Authority while C owns the final relation-aware
# public/compatibility facades, their relation-aware contracts, plus exact-session
# reopen. At the reviewed topology, merging C after B yields exactly the eleven
# attendance conflicts below. Program expand no longer conflicts because B is a
# descendant of the C migration, but its safer descendant blob remains pinned
# independently and must survive unchanged.
B_C_PROGRAM_MIGRATION_PATH="backend/alembic/versions/20260817_aa_prog_expand.py"
B_C_HANDOFF_PATHS=(
  "${INT_C_HANDOFF_PATHS[@]}"
)
B_C_HANDOFF_TAKE_B=(
  "${INT_C_HANDOFF_TAKE_INT[@]}"
)
B_C_HANDOFF_KEEP_C=(
  "${INT_C_HANDOFF_KEEP_C[@]}"
)
declare -A B_C_HANDOFF_B_BLOBS=(
  [backend/alembic/versions/20260817_aa_prog_expand.py]="6c8b165767f01c6aaa8e868dcad2bcc343d081b7"
  [backend/app/modules/academic_affairs/services/academic_affairs_attendance_occurrence_consumer.py]="2bc151356268eafa7300bddbd78a878f067caa72"
  [backend/app/modules/academic_affairs/services/academic_affairs_attendance_public_service.py]="4d5dbdcb72a470f0a276b01bfe6559fa62305e0e"
  [backend/app/modules/academic_affairs/services/academic_affairs_attendance_service.py]="a8e08149d8d813e25cb6fe050977ce1c995d1a36"
  [backend/app/modules/academic_affairs/services/academic_affairs_warning_service.py]="6feee794a472525dfe66a4e46231672530598a01"
  [backend/tests/test_aa_attendance_admin_special_contract.py]="b8782621fe902a684e27cc5c9a0f0ff16080e3a8"
  [backend/tests/test_aa_attendance_class_options_formal_schedule.py]="960b55947993bd3c9eb7d946a62fb9031f56bec6"
  [backend/tests/test_aa_attendance_expected_schedule_item_contract.py]="7546ba765e4b9dd6e40a10b18dfbd68149a71e41"
  [backend/tests/test_aa_attendance_published_occurrence_contract.py]="cf413b96988d4b3fa777dcca2890f5365ad4ff12"
  [backend/tests/test_aa_attendance_warning_source_contract.py]="4d3664032fba681ba3eef0149cd12dae5bdef234"
  [miniapp/src/pages/teacher/academic-affairs/attendance.vue]="9df52087dcbe47a37f3bca57b03430fc363d022c"
  [miniapp/tests/academic-attendance-source-contract.test.mjs]="a94116cefb269ed9db1c06eaf64cb58b799d31ea"
)
B_C_PROGRAM_MIGRATION_C_BLOB="7d5217d43f13e4237afd4247328164bb30874eed"

# Final W5 is an integration rehearsal: the source branches deliberately keep
# their independent Alembic ownership. Only after all five layers are merged may
# W5 materialize the one reviewed no-DDL convergence node, and only when the
# exact unresolved head set is the known B/C sibling pair.
B_C_DAG_HEAD_A="20260818_acad_main_int_merge"
B_C_DAG_HEAD_C="20260818_merge_prog_grade_dl"
B_C_DAG_REVISION="20260818_acad_bc_final"
B_C_DAG_PATH="backend/alembic/versions/20260818_academic_bc_final_merge.py"

HEAD_MATRIX=/tmp/academic-d-w5-head-matrix.txt
MERGE_LEDGER=/tmp/academic-d-w5-merge-ledger.txt
CONTRACT_INVENTORY=/tmp/academic-d-w5-contract-inventory.txt
EVIDENCE=/tmp/academic-d-w5-evidence.txt
JUNIT=/tmp/academic-d-w5-targeted.xml
ALEMBIC_CURRENT=/tmp/academic-d-w5-alembic-current.txt
MIGRATED_EVIDENCE=/tmp/academic-d-w5-migrated-tenant.txt
MIGRATED_WORKTREE=/tmp/academic-d-w5-main-worktree
REPO_ROOT="$(pwd)"

SNAPSHOT_UTC="not_reached"
CURRENT_LAYER=""
W5_PHASE="EXACT_D_CHECK"
CLEAN_SCHEMA_PROVEN=false
MIGRATED_TENANT_SCHEMA_PROVEN=false
TARGETED_CONTRACTS_PROVEN=false
PERMISSION_NEGATIVE_PROVEN=false
DATASCOPE_NEGATIVE_PROVEN=false
CROSS_TENANT_SENTINEL_PROVEN=false
DAG_CONVERGENCE_PROVEN=false
DAG_CONVERGENCE_BLOB=""
DAG_CONVERGENCE_COMMIT=""
MAIN_ALEMBIC_VERSION=""
INTEGRATED_ALEMBIC_VERSION=""
MIGRATED_PROBE_DIGEST=""

: > "$HEAD_MATRIX"
: > "$MERGE_LEDGER"
: > "$CONTRACT_INVENTORY"
: > "$ALEMBIC_CURRENT"
: > "$MIGRATED_EVIDENCE"

write_evidence() {
  local rc="$1"
  local replay_success=false
  if [[ "$rc" -eq 0 ]]; then
    replay_success=true
  fi
  cat > "$EVIDENCE" <<EOF
w5_phase=$W5_PHASE
exit_code=$rc
replay_success=$replay_success
failed_layer=$CURRENT_LAYER
snapshot_mode=JOB_START_FETCH
snapshot_utc=$SNAPSHOT_UTC
d_source_commit=$EXACT_D_SHA
main_commit=${MAIN_SHA:-}
a_commit=${A_SHA:-}
b_commit=${B_SHA:-}
c_commit=${C_SHA:-}
int_commit=${INT_SHA:-}
dag_convergence_proven=$DAG_CONVERGENCE_PROVEN
dag_convergence_revision=$B_C_DAG_REVISION
dag_convergence_parents=$B_C_DAG_HEAD_A,$B_C_DAG_HEAD_C
dag_convergence_blob=$DAG_CONVERGENCE_BLOB
dag_convergence_commit=$DAG_CONVERGENCE_COMMIT
clean_tenant_schema_proven=$CLEAN_SCHEMA_PROVEN
migrated_tenant_schema_proven=$MIGRATED_TENANT_SCHEMA_PROVEN
migrated_tenant_contracts_proven=$TARGETED_CONTRACTS_PROVEN
main_alembic_version=$MAIN_ALEMBIC_VERSION
integrated_alembic_version=$INTEGRATED_ALEMBIC_VERSION
migrated_probe_digest=$MIGRATED_PROBE_DIGEST
permission_negative_contract_proven=$PERMISSION_NEGATIVE_PROVEN
datascope_negative_contract_proven=$DATASCOPE_NEGATIVE_PROVEN
cross_tenant_sentinel_proven=$CROSS_TENANT_SENTINEL_PROVEN
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
}

cleanup_worktree() {
  git -C "$REPO_ROOT" worktree remove --force "$MIGRATED_WORKTREE" >/dev/null 2>&1 || true
  git -C "$REPO_ROOT" worktree prune >/dev/null 2>&1 || true
}

trap 'rc=$?; trap - EXIT; set +e; write_evidence "$rc"; cleanup_worktree; exit "$rc"' EXIT

actual_d="$(git rev-parse HEAD)"
test "$actual_d" = "$EXACT_D_SHA"

W5_PHASE="SNAPSHOT_FETCH"
git fetch --no-tags origin \
  "+refs/heads/main:refs/remotes/origin/main" \
  "+refs/heads/agent/academic-a-semester-core:refs/remotes/origin/agent/academic-a-semester-core" \
  "+refs/heads/agent/academic-b-schedule-selection:refs/remotes/origin/agent/academic-b-schedule-selection" \
  "+refs/heads/agent/academic-c-teaching-execution:refs/remotes/origin/agent/academic-c-teaching-execution" \
  "+refs/heads/integration/academic-school-gold:refs/remotes/origin/integration/academic-school-gold"

# PRE-GOLD consumes one immutable snapshot of active A/B/C/INT heads.
# Final Gold replaces this with frozen contract pins after upstream construction stops moving.
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

verify_b_c_handoff_contract() {
  if ! git merge-base --is-ancestor "$INT_C1_IMPORT_SHA" "$B_SHA"; then
    echo "[handoff-drift] B no longer descends from reviewed C-C1 import $INT_C1_IMPORT_SHA" | tee -a "$MERGE_LEDGER"
    return 1
  fi
  if ! git merge-base --is-ancestor "$INT_SOURCE_AUTH_SHA" "$B_SHA"; then
    echo "[handoff-drift] B no longer descends from reviewed INT source Authority $INT_SOURCE_AUTH_SHA" | tee -a "$MERGE_LEDGER"
    return 1
  fi

  local migration_b_blob migration_c_blob path b_blob c_blob guard_blob
  migration_b_blob="$(git rev-parse "${B_SHA}:${B_C_PROGRAM_MIGRATION_PATH}")"
  migration_c_blob="$(git rev-parse "${C_SHA}:${B_C_PROGRAM_MIGRATION_PATH}")"
  if [[ "$migration_b_blob" != "${B_C_HANDOFF_B_BLOBS[$B_C_PROGRAM_MIGRATION_PATH]}" ]]; then
    echo "[handoff-drift] B migration blob expected=${B_C_HANDOFF_B_BLOBS[$B_C_PROGRAM_MIGRATION_PATH]} actual=$migration_b_blob" | tee -a "$MERGE_LEDGER"
    return 1
  fi
  if [[ "$migration_c_blob" != "$B_C_PROGRAM_MIGRATION_C_BLOB" ]]; then
    echo "[handoff-drift] C migration blob expected=$B_C_PROGRAM_MIGRATION_C_BLOB actual=$migration_c_blob" | tee -a "$MERGE_LEDGER"
    return 1
  fi

  for path in "${B_C_HANDOFF_PATHS[@]}"; do
    b_blob="$(git rev-parse "${B_SHA}:${path}")"
    if [[ "$b_blob" != "${B_C_HANDOFF_B_BLOBS[$path]}" ]]; then
      echo "[handoff-drift] B blob $path expected=${B_C_HANDOFF_B_BLOBS[$path]} actual=$b_blob" | tee -a "$MERGE_LEDGER"
      return 1
    fi

    c_blob="$(git rev-parse "${C_SHA}:${path}")"
    if [[ "$c_blob" != "${INT_C_HANDOFF_C_BLOBS[$path]}" ]]; then
      echo "[handoff-drift] C blob $path expected=${INT_C_HANDOFF_C_BLOBS[$path]} actual=$c_blob" | tee -a "$MERGE_LEDGER"
      return 1
    fi
  done

  guard_blob="$(git rev-parse "${C_SHA}:${C_FINAL_RELATION_GUARD_PATH}")"
  if [[ "$guard_blob" != "$C_FINAL_RELATION_GUARD_BLOB" ]]; then
    echo "[handoff-drift] C relation guard expected=$C_FINAL_RELATION_GUARD_BLOB actual=$guard_blob" | tee -a "$MERGE_LEDGER"
    return 1
  fi
}

resolve_b_c_handoff_conflicts() {
  local actual_conflicts expected_conflicts path ours_blob theirs_blob migration_head_blob migration_worktree_blob
  actual_conflicts="$(git diff --name-only --diff-filter=U | LC_ALL=C sort)"
  expected_conflicts="$(printf '%s\n' "${B_C_HANDOFF_PATHS[@]}" | LC_ALL=C sort)"
  if [[ "$actual_conflicts" != "$expected_conflicts" ]]; then
    echo "[handoff-rejected] C conflict set differs from reviewed B/INT -> C attendance handoff" | tee -a "$MERGE_LEDGER"
    printf '%s\n' "$actual_conflicts" | tee -a "$MERGE_LEDGER"
    return 1
  fi

  if ! verify_b_c_handoff_contract; then
    return 1
  fi

  # Program expand is no longer a conflict at this topology. Prove the automatic
  # merge kept the reviewed descendant-safe B/INT version byte-for-byte.
  migration_head_blob="$(git rev-parse "HEAD:${B_C_PROGRAM_MIGRATION_PATH}")"
  migration_worktree_blob="$(git hash-object "$B_C_PROGRAM_MIGRATION_PATH")"
  if [[ "$migration_head_blob" != "${B_C_HANDOFF_B_BLOBS[$B_C_PROGRAM_MIGRATION_PATH]}" || "$migration_worktree_blob" != "${B_C_HANDOFF_B_BLOBS[$B_C_PROGRAM_MIGRATION_PATH]}" ]]; then
    echo "[handoff-drift] automatic C merge changed reviewed descendant-safe Program migration" | tee -a "$MERGE_LEDGER"
    return 1
  fi

  for path in "${B_C_HANDOFF_PATHS[@]}"; do
    ours_blob="$(git rev-parse ":2:${path}")"
    theirs_blob="$(git rev-parse ":3:${path}")"
    if [[ "$ours_blob" != "${B_C_HANDOFF_B_BLOBS[$path]}" ]]; then
      echo "[handoff-drift] C merge stage-2 blob $path expected=${B_C_HANDOFF_B_BLOBS[$path]} actual=$ours_blob" | tee -a "$MERGE_LEDGER"
      return 1
    fi
    if [[ "$theirs_blob" != "${INT_C_HANDOFF_C_BLOBS[$path]}" ]]; then
      echo "[handoff-drift] C merge stage-3 blob $path expected=${INT_C_HANDOFF_C_BLOBS[$path]} actual=$theirs_blob" | tee -a "$MERGE_LEDGER"
      return 1
    fi
  done

  git checkout --ours -- "${B_C_HANDOFF_TAKE_B[@]}"
  git checkout --theirs -- "${B_C_HANDOFF_KEEP_C[@]}"
  git add -- "${B_C_HANDOFF_PATHS[@]}"
  test -z "$(git diff --name-only --diff-filter=U)"
  test -z "$(git ls-files -u)"
  git commit --no-edit
  echo "[handoff-resolved] B/INT occurrence+warning+source contracts preserved; C final attendance facades, relation-aware contracts and exact-session miniapp reopen preserved; descendant-safe Program migration verified unchanged" | tee -a "$MERGE_LEDGER"
}

verify_int_c_handoff_contract() {
  git merge-base --is-ancestor "$INT_C1_IMPORT_SHA" "$INT_SHA"
  git merge-base --is-ancestor "$INT_SOURCE_AUTH_SHA" "$INT_SHA"

  local path actual_blob imported_blob int_blob guard_blob
  for path in "${INT_C_HANDOFF_PATHS[@]}"; do
    actual_blob="$(git rev-parse "${C_SHA}:${path}")"
    if [[ "$actual_blob" != "${INT_C_HANDOFF_C_BLOBS[$path]}" ]]; then
      echo "[handoff-drift] C blob $path expected=${INT_C_HANDOFF_C_BLOBS[$path]} actual=$actual_blob" | tee -a "$MERGE_LEDGER"
      return 1
    fi
  done

  guard_blob="$(git rev-parse "${C_SHA}:${C_FINAL_RELATION_GUARD_PATH}")"
  if [[ "$guard_blob" != "$C_FINAL_RELATION_GUARD_BLOB" ]]; then
    echo "[handoff-drift] C relation guard expected=$C_FINAL_RELATION_GUARD_BLOB actual=$guard_blob" | tee -a "$MERGE_LEDGER"
    return 1
  fi

  # The five retained INT backend/source-contract files remain byte-for-byte the
  # reviewed C-C1 import before INT layered source/occurrence Authority.
  for path in "${INT_C_HANDOFF_TAKE_INT[@]}"; do
    imported_blob="$(git rev-parse "${INT_C1_IMPORT_SHA}:${path}")"
    if [[ "$imported_blob" != "${INT_C_HANDOFF_C_BLOBS[$path]}" ]]; then
      echo "[handoff-drift] INT imported backend blob $path expected=${INT_C_HANDOFF_C_BLOBS[$path]} actual=$imported_blob" | tee -a "$MERGE_LEDGER"
      return 1
    fi
  done

  # INT still carries the reviewed pre-final-C public/compatibility implementation
  # and the two pre-relation-aware contracts. Final C deliberately supersedes these
  # four paths while the merged INT source contracts prove persisted source semantics.
  for path in \
    backend/app/modules/academic_affairs/services/academic_affairs_attendance_public_service.py \
    backend/app/modules/academic_affairs/services/academic_affairs_attendance_service.py \
    backend/tests/test_aa_attendance_class_options_formal_schedule.py \
    backend/tests/test_aa_attendance_expected_schedule_item_contract.py; do
    int_blob="$(git rev-parse "${INT_SHA}:${path}")"
    if [[ "$int_blob" != "${B_C_HANDOFF_B_BLOBS[$path]}" ]]; then
      echo "[handoff-drift] INT pre-final-C blob $path expected=${B_C_HANDOFF_B_BLOBS[$path]} actual=$int_blob" | tee -a "$MERGE_LEDGER"
      return 1
    fi
  done

  # C added exact session reopen after the INT import. INT has not touched either
  # miniapp file since that import, so W5 must keep the newer C version verbatim.
  for path in "${INT_C_HANDOFF_KEEP_C_UNTOUCHED[@]}"; do
    imported_blob="$(git rev-parse "${INT_C1_IMPORT_SHA}:${path}")"
    if [[ "$imported_blob" != "${INT_C_HANDOFF_IMPORT_MINI_BLOBS[$path]}" ]]; then
      echo "[handoff-drift] INT imported miniapp blob $path expected=${INT_C_HANDOFF_IMPORT_MINI_BLOBS[$path]} actual=$imported_blob" | tee -a "$MERGE_LEDGER"
      return 1
    fi
    if [[ -n "$(git diff --name-only "${INT_C1_IMPORT_SHA}..${INT_SHA}" -- "$path")" ]]; then
      echo "[handoff-drift] INT changed C-owned post-import miniapp path $path" | tee -a "$MERGE_LEDGER"
      return 1
    fi
  done
}

resolve_int_c_handoff_conflicts() {
  local actual_conflicts expected_conflicts
  actual_conflicts="$(git diff --name-only --diff-filter=U | LC_ALL=C sort)"
  expected_conflicts="$(printf '%s\n' "${INT_C_HANDOFF_PATHS[@]}" | LC_ALL=C sort)"
  if [[ "$actual_conflicts" != "$expected_conflicts" ]]; then
    echo "[handoff-rejected] INT conflict set differs from reviewed final C attendance handoff" | tee -a "$MERGE_LEDGER"
    printf '%s\n' "$actual_conflicts" | tee -a "$MERGE_LEDGER"
    return 1
  fi

  verify_int_c_handoff_contract

  git checkout --theirs -- "${INT_C_HANDOFF_TAKE_INT[@]}"
  git checkout --ours -- "${INT_C_HANDOFF_KEEP_C[@]}"
  git add -- "${INT_C_HANDOFF_PATHS[@]}"
  test -z "$(git diff --name-only --diff-filter=U)"
  test -z "$(git ls-files -u)"
  git commit --no-edit
  echo "[handoff-resolved] INT occurrence+warning+source contracts layered over reviewed C-C1; C final attendance facades, relation-aware contracts and newer miniapp exact-session reopen preserved" | tee -a "$MERGE_LEDGER"
}

merge_layer() {
  local layer="$1"
  local sha="$2"
  CURRENT_LAYER="$layer"
  W5_PHASE="MERGE_${layer}"
  echo "[merge] $layer $sha" | tee -a "$MERGE_LEDGER"
  if ! git merge --no-ff --no-edit "$sha"; then
    echo "[conflicts] $layer" | tee -a "$MERGE_LEDGER"
    git diff --name-only --diff-filter=U | tee -a "$MERGE_LEDGER"
    if [[ "$layer" == "C" ]]; then
      if ! resolve_b_c_handoff_conflicts; then
        exit 1
      fi
    elif [[ "$layer" == "INT" ]]; then
      if ! resolve_int_c_handoff_conflicts; then
        exit 1
      fi
    else
      exit 1
    fi
  fi
  echo "[merged] $layer tree=$(git rev-parse HEAD^{tree}) commit=$(git rev-parse HEAD)" | tee -a "$MERGE_LEDGER"
  # A successful automatic merge or an audited handoff must leave no unresolved
  # index stages. We do not run a broad historical whitespace audit.
  test -z "$(git diff --name-only --diff-filter=U)"
  test -z "$(git ls-files -u)"
}

materialize_bc_dag_convergence() {
  CURRENT_LAYER="ALEMBIC_DAG"
  W5_PHASE="ALEMBIC_DAG_CONVERGENCE"

  if [[ -e "$B_C_DAG_PATH" ]]; then
    echo "[dag-convergence-rejected] unexpected existing path $B_C_DAG_PATH" | tee -a "$MERGE_LEDGER"
    return 1
  fi

  local actual_heads expected_heads
  actual_heads="$(cd backend && alembic heads | awk '{print $1}' | LC_ALL=C sort)"
  expected_heads="$(printf '%s\n' "$B_C_DAG_HEAD_A" "$B_C_DAG_HEAD_C" | LC_ALL=C sort)"
  if [[ "$actual_heads" != "$expected_heads" ]]; then
    echo "[dag-convergence-rejected] expected exact B/C sibling heads" | tee -a "$MERGE_LEDGER"
    printf 'expected:\n%s\nactual:\n%s\n' "$expected_heads" "$actual_heads" | tee -a "$MERGE_LEDGER"
    return 1
  fi

  grep -F "revision = \"$B_C_DAG_HEAD_A\"" backend/alembic/versions/20260818_academic_main_int_merge.py >/dev/null
  grep -F "revision = \"$B_C_DAG_HEAD_C\"" backend/alembic/versions/20260818_merge_prog_grade_deadline.py >/dev/null

  cat > "$B_C_DAG_PATH" <<'PY'
"""Merge Academic B/INT and Academic C final migration heads.

Revision ID: 20260818_acad_bc_final
Revises: 20260818_acad_main_int_merge, 20260818_merge_prog_grade_dl

Pure W5 integration convergence. Both parent heads are independently reviewed
additive lineages; this node intentionally performs no DDL and no data rewrite.
The exact source is emitted as W5 evidence so the final integration owner can
persist the byte-identical revision once the upstream PR merge order is fixed.
"""
from __future__ import annotations

revision = "20260818_acad_bc_final"
down_revision = (
    "20260818_acad_main_int_merge",
    "20260818_merge_prog_grade_dl",
)
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
PY

  git add -- "$B_C_DAG_PATH"
  git diff --cached --check
  git commit -m "ci(academic): prove B/C Alembic DAG convergence"
  DAG_CONVERGENCE_COMMIT="$(git rev-parse HEAD)"
  DAG_CONVERGENCE_BLOB="$(git rev-parse "HEAD:${B_C_DAG_PATH}")"

  test "$(cd backend && alembic heads | awk '{print $1}')" = "$B_C_DAG_REVISION"
  DAG_CONVERGENCE_PROVEN=true
  CURRENT_LAYER=""
  echo "[dag-convergence-proven] revision=$B_C_DAG_REVISION parents=$B_C_DAG_HEAD_A,$B_C_DAG_HEAD_C blob=$DAG_CONVERGENCE_BLOB commit=$DAG_CONVERGENCE_COMMIT" | tee -a "$MERGE_LEDGER"
}

merge_layer A "$A_SHA"
merge_layer B "$B_SHA"
merge_layer C "$C_SHA"
merge_layer D "$EXACT_D_SHA"
merge_layer INT "$INT_SHA"
CURRENT_LAYER=""

materialize_bc_dag_convergence

W5_PHASE="POST_MERGE_WORKTREE_GUARD"
test -z "$(git status --porcelain --untracked-files=no)"

cd backend

W5_PHASE="CLEAN_SCHEMA"
mysql -h127.0.0.1 -uroot -proot -e '
  DROP DATABASE IF EXISTS student_lifecycle_test;
  CREATE DATABASE student_lifecycle_test CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
'
test "$(alembic heads | grep -c '(head)')" -eq 1
alembic upgrade head
alembic current | tee "$ALEMBIC_CURRENT"
CLEAN_SCHEMA_PROVEN=true

# Migrated-tenant Gold must prove an already-upgraded current-main database survives
# the integrated A/B/C/D/INT migration lineage with its pre-existing bytes intact.
W5_PHASE="MIGRATED_TENANT_MAIN_BASELINE"
MIGRATED_DB="academic_d_w5_migrated"
MIGRATED_URL="mysql+pymysql://root:root@127.0.0.1:3306/${MIGRATED_DB}?charset=utf8mb4"
mysql -h127.0.0.1 -uroot -proot -e "
  DROP DATABASE IF EXISTS ${MIGRATED_DB};
  CREATE DATABASE ${MIGRATED_DB} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
"
cd "$REPO_ROOT"
cleanup_worktree
git worktree add --detach "$MIGRATED_WORKTREE" "$MAIN_SHA"
(
  cd "$MIGRATED_WORKTREE/backend"
  test "$(alembic heads | grep -c '(head)')" -eq 1
  DATABASE_URL="$MIGRATED_URL" TEST_DATABASE_URL="$MIGRATED_URL" alembic upgrade head
)
MAIN_ALEMBIC_VERSION="$(mysql -h127.0.0.1 -uroot -proot -Nse "SELECT GROUP_CONCAT(version_num ORDER BY version_num SEPARATOR ',') FROM ${MIGRATED_DB}.alembic_version")"
test -n "$MAIN_ALEMBIC_VERSION"

mysql -h127.0.0.1 -uroot -proot "$MIGRATED_DB" <<'SQL'
CREATE TABLE t_d_w5_migrated_tenant_probe (
  id BIGINT PRIMARY KEY,
  tenant_key VARCHAR(64) NOT NULL,
  payload VARBINARY(128) NOT NULL
) ENGINE=InnoDB;
INSERT INTO t_d_w5_migrated_tenant_probe(id, tenant_key, payload)
VALUES
  (1, 'existing-school-a', UNHEX(SHA2('academic-d-w5-existing-a', 256))),
  (2, 'existing-school-b', UNHEX(SHA2('academic-d-w5-existing-b', 256)));
SQL
MIGRATED_PROBE_DIGEST="$(mysql -h127.0.0.1 -uroot -proot -Nse "SELECT SHA2(GROUP_CONCAT(CONCAT(id, ':', tenant_key, ':', HEX(payload)) ORDER BY id SEPARATOR '|'), 256) FROM ${MIGRATED_DB}.t_d_w5_migrated_tenant_probe")"
test -n "$MIGRATED_PROBE_DIGEST"

W5_PHASE="MIGRATED_TENANT_INTEGRATED_UPGRADE"
cd "$REPO_ROOT/backend"
test "$(alembic heads | grep -c '(head)')" -eq 1
DATABASE_URL="$MIGRATED_URL" TEST_DATABASE_URL="$MIGRATED_URL" alembic upgrade head
INTEGRATED_ALEMBIC_VERSION="$(mysql -h127.0.0.1 -uroot -proot -Nse "SELECT GROUP_CONCAT(version_num ORDER BY version_num SEPARATOR ',') FROM ${MIGRATED_DB}.alembic_version")"
test -n "$INTEGRATED_ALEMBIC_VERSION"
AFTER_PROBE_DIGEST="$(mysql -h127.0.0.1 -uroot -proot -Nse "SELECT SHA2(GROUP_CONCAT(CONCAT(id, ':', tenant_key, ':', HEX(payload)) ORDER BY id SEPARATOR '|'), 256) FROM ${MIGRATED_DB}.t_d_w5_migrated_tenant_probe")"
test "$AFTER_PROBE_DIGEST" = "$MIGRATED_PROBE_DIGEST"
test "$(mysql -h127.0.0.1 -uroot -proot -Nse "SELECT COUNT(*) FROM ${MIGRATED_DB}.t_d_w5_migrated_tenant_probe")" = "2"
test "$(mysql -h127.0.0.1 -uroot -proot -Nse "SELECT COUNT(*) FROM information_schema.COLUMNS WHERE TABLE_SCHEMA='${MIGRATED_DB}' AND TABLE_NAME='t_aa_program_course' AND COLUMN_NAME='formation_mode'")" = "1"
test "$(mysql -h127.0.0.1 -uroot -proot -Nse "SELECT COUNT(*) FROM information_schema.COLUMNS WHERE TABLE_SCHEMA='${MIGRATED_DB}' AND TABLE_NAME='t_aa_teaching_task' AND COLUMN_NAME='formation_mode'")" = "1"
test "$(mysql -h127.0.0.1 -uroot -proot -Nse "SELECT COUNT(*) FROM information_schema.COLUMNS WHERE TABLE_SCHEMA='${MIGRATED_DB}' AND TABLE_NAME='t_aa_teaching_task_batch' AND COLUMN_NAME='editable_scope_key'")" = "1"
cat > "$MIGRATED_EVIDENCE" <<EOF
main_commit=$MAIN_SHA
main_alembic_version=$MAIN_ALEMBIC_VERSION
integrated_alembic_version=$INTEGRATED_ALEMBIC_VERSION
probe_rows=2
probe_digest_before=$MIGRATED_PROBE_DIGEST
probe_digest_after=$AFTER_PROBE_DIGEST
probe_bytes_preserved=true
formation_mode_program_course_present=true
formation_mode_teaching_task_present=true
editable_scope_key_present=true
migrated_tenant_schema_proven=true
EOF
sha256sum "$MIGRATED_EVIDENCE" > "${MIGRATED_EVIDENCE}.sha256"
sha256sum -c "${MIGRATED_EVIDENCE}.sha256"
MIGRATED_TENANT_SCHEMA_PROVEN=true
cleanup_worktree

W5_PHASE="CONTRACT_INVENTORY"
files=(
  tests/test_aa_school_setup_program_post_confirm_pipeline_int.py
  tests/test_academic_int_ac4_schema_mysql.py
  tests/test_academic_int_c1_attendance_backfill_mysql.py
  tests/test_academic_int_attendance_handoff_contract.py
  tests/test_aa_selection_w6_roster_reconcile_mysql.py
  tests/test_aa_attendance_admin_special_contract.py
  tests/test_aa_attendance_published_occurrence_contract.py
  tests/test_aa_attendance_warning_source_contract.py
  tests/test_aa_attendance_occurrence_concurrency.py
  tests/test_aa_graduation_d_w0_scope_guard.py
  tests/test_aa_graduation_d_w5_permission_negative.py
  tests/test_aa_graduation_d_w5_datascope_negative.py
  tests/test_aa_archive_d_w1_authority_regressions.py
  tests/test_aa_semester_pilot_r11.py
  tests/test_aa_main_permission_middleware_compat.py
)
printf '%s\n' "${files[@]}" | tee "$CONTRACT_INVENTORY"
for file in "${files[@]}"; do test -f "$file"; done

W5_PHASE="TARGETED_CONTRACTS"
pytest -q -p no:warnings \
  "${files[@]}" \
  --maxfail=1 \
  --junitxml="$JUNIT"

cd "$REPO_ROOT"
node --test miniapp/tests/academic-attendance-source-contract.test.mjs
cd backend

PERMISSION_NEGATIVE_PROVEN=true
DATASCOPE_NEGATIVE_PROVEN=true
CROSS_TENANT_SENTINEL_PROVEN=true
TARGETED_CONTRACTS_PROVEN=true
W5_PHASE="PRE_GOLD_REPLAY_COMPLETE"
