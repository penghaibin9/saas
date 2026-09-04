#!/usr/bin/env bash
set -uo pipefail

ROOT="${GITHUB_WORKSPACE:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
SUITE="${1:?suite name is required}"
RESULT_DIR="$ROOT/e2e/gate-results"
mkdir -p "$RESULT_DIR"

write_summary() {
  local status="$1"
  local exit_code="$2"
  cat > "$RESULT_DIR/${SUITE}.json" <<JSON
{
  "suite": "${SUITE}",
  "head": "${E2E_EXPECTED_SHA:-local}",
  "runId": "${GITHUB_RUN_ID:-local}",
  "runAttempt": "${GITHUB_RUN_ATTEMPT:-1}",
  "status": "${status}",
  "exitCode": ${exit_code}
}
JSON
}

run_specs() {
  local label="$1"
  shift
  printf '%s\n' "$@" > "$RESULT_DIR/${SUITE}-selected-specs.txt"
  echo "[browser-suite] suite=$SUITE group=$label specs=$#"
  (
    cd "$ROOT/e2e"
    npx playwright test "$@"
  )
}

case "$SUITE" in
  production-non-graduation)
    mapfile -t SPECS < <(
      cd "$ROOT/e2e"
      find specs -maxdepth 1 -type f -name '*.spec.mjs' \
        ! -name 'graduation*.spec.mjs' \
        ! -name '*-visual.spec.mjs' \
        ! -name 'control-plane-role-menu-projection.spec.mjs' \
        ! -name 'internship-s1-production-runtime.spec.mjs' \
        ! -name 'internship-leave-lifecycle.spec.mjs' \
        ! -name 'internship-leave-stats-xlsx-audit.spec.mjs' \
        ! -name 'internship-placement-assignment-audit.spec.mjs' \
        -print | sort
    )
    if [[ "${#SPECS[@]}" -eq 0 ]]; then
      echo 'no non-graduation functional specs discovered' >&2
      write_summary failed 2
      exit 2
    fi
    run_specs functional "${SPECS[@]}"
    code=$?
    if [[ "$code" -eq 0 ]]; then
      write_summary passed 0
    else
      write_summary failed "$code"
    fi
    exit "$code"
    ;;

  graduation-functional)
    mapfile -t SPECS < <(
      cd "$ROOT/e2e"
      find specs -maxdepth 1 -type f -name 'graduation*.spec.mjs' \
        ! -name '*-visual.spec.mjs' \
        -print | sort
    )
    if [[ "${#SPECS[@]}" -eq 0 ]]; then
      echo 'no graduation functional specs discovered' >&2
      write_summary failed 2
      exit 2
    fi
    run_specs graduation-functional "${SPECS[@]}"
    code=$?
    if [[ "$code" -eq 0 ]]; then
      write_summary passed 0
    else
      write_summary failed "$code"
    fi
    exit "$code"
    ;;

  graduation-gold)
    GOLD_SPECS=(
      specs/graduation-v9-dashboard-visual.spec.mjs
      specs/graduation-v9-final-review-visual.spec.mjs
      specs/graduation-v9-process-visual.spec.mjs
      specs/graduation-v9-archive-visual.spec.mjs
      specs/graduation-v9-teacher-mobile-visual.spec.mjs
    )
    printf '%s\n' "${GOLD_SPECS[@]}" > "$RESULT_DIR/${SUITE}-selected-specs.txt"

    (
      cd "$ROOT/e2e"
      npx playwright test "${GOLD_SPECS[@]}" \
        --retries=0 \
        --update-snapshots=all \
        --update-source-method=overwrite
    )
    capture_code=$?

    python "$ROOT/scripts/e2e/build-graduation-gold-candidate.py" \
      --repo-root "$ROOT" \
      --head "${E2E_EXPECTED_SHA:-local}"
    inventory_code=$?

    (
      cd "$ROOT"
      git diff --binary -- 'e2e/specs/graduation-v9-*-visual.spec.mjs-snapshots/*.png' \
        > e2e/gold-candidate/candidate.patch || true
      git status --short -- 'e2e/specs/graduation-v9-*-visual.spec.mjs-snapshots/*.png' \
        > e2e/gold-candidate/status.txt
    )

    final_code=0
    [[ "$capture_code" -eq 0 ]] || final_code="$capture_code"
    [[ "$inventory_code" -eq 0 ]] || final_code="$inventory_code"
    if [[ "$final_code" -eq 0 ]]; then
      write_summary passed 0
    else
      write_summary failed "$final_code"
    fi
    exit "$final_code"
    ;;

  *)
    echo "unknown browser suite: $SUITE" >&2
    write_summary failed 2
    exit 2
    ;;
esac
