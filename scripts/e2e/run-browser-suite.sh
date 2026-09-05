#!/usr/bin/env bash
set -uo pipefail

ROOT="${GITHUB_WORKSPACE:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
SUITE="${1:?suite name is required}"
RESULT_DIR="$ROOT/e2e/gate-results"
PLAYWRIGHT_JSON="$RESULT_DIR/${SUITE}-playwright.json"
FAILURE_JSON="$RESULT_DIR/${SUITE}-failures.json"
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
  "exitCode": ${exit_code},
  "playwrightReport": "gate-results/${SUITE}-playwright.json",
  "failureReport": "gate-results/${SUITE}-failures.json"
}
JSON
}

summarize_playwright_report() {
  local report="$1"
  local suite="$2"
  local output="$3"
  node --input-type=module - "$report" "$suite" "$output" <<'NODE'
import fs from 'node:fs'
import path from 'node:path'

const [, , reportPath, suite, outputPath] = process.argv
const head = process.env.E2E_EXPECTED_SHA || process.env.GITHUB_SHA || 'local'
const runId = process.env.GITHUB_RUN_ID || 'local'
const stepSummary = process.env.GITHUB_STEP_SUMMARY || ''

function redact(value) {
  return String(value || '')
    .replace(/Bearer\s+[A-Za-z0-9._~+/=-]+/gi, 'Bearer [REDACTED]')
    .replace(/((?:token|ticket|password|authorization|secret)(?:=|:|%3D)\s*)[^&\s"'<>]+/gi, '$1[REDACTED]')
    .replace(/([?&](?:token|ticket|password|authorization|secret)=)[^&\s"'<>]+/gi, '$1[REDACTED]')
    .replace(/\b[A-Za-z0-9_-]{18,}\.[A-Za-z0-9_-]{18,}\.[A-Za-z0-9_-]{18,}\b/g, '[REDACTED_JWT]')
    .replace(/\u001b\[[0-9;]*m/g, '')
}

function oneLine(value, limit = 1600) {
  return redact(value).replace(/\s+/g, ' ').trim().slice(0, limit)
}

function annotationEscape(value) {
  return oneLine(value)
    .replace(/%/g, '%25')
    .replace(/\r/g, '%0D')
    .replace(/\n/g, '%0A')
    .replace(/:/g, '%3A')
    .replace(/,/g, '%2C')
}

function firstError(result) {
  const errors = Array.isArray(result?.errors) ? result.errors : []
  const error = errors[0] || result?.error || null
  if (!error) return { message: `Playwright result status=${result?.status || 'unknown'}`, stack: '', location: null }
  return {
    message: oneLine(error.message || error.value || error.stack || error),
    stack: redact(error.stack || ''),
    location: error.location || null
  }
}

const failures = []
const rootErrors = []

function walkSuite(node, parents = []) {
  const nextParents = [...parents, node?.title].filter(Boolean)
  for (const spec of node?.specs || []) {
    for (const test of spec?.tests || []) {
      const results = test?.results || []
      const terminal = results.at(-1) || null
      if (!terminal || !['failed', 'timedOut', 'interrupted'].includes(terminal.status)) continue
      const error = firstError(terminal)
      const location = error.location || test.location || spec.location || {
        file: spec.file || '', line: 1, column: 1
      }
      failures.push({
        title: [...nextParents, spec.title, test.title].filter(Boolean).join(' › '),
        project: test.projectName || '',
        status: terminal.status,
        retry: terminal.retry ?? results.length - 1,
        durationMs: terminal.duration ?? null,
        file: location?.file || spec.file || '',
        line: Number(location?.line || 1),
        column: Number(location?.column || 1),
        message: error.message,
        stack: error.stack.slice(0, 6000),
        attachments: (terminal.attachments || []).map((item) => ({
          name: oneLine(item.name, 200),
          path: item.path ? path.relative(process.cwd(), item.path) : '',
          contentType: item.contentType || ''
        }))
      })
    }
  }
  for (const child of node?.suites || []) walkSuite(child, nextParents)
}

let parseError = ''
if (!fs.existsSync(reportPath)) {
  parseError = `Playwright JSON report was not created: ${reportPath}`
} else {
  try {
    const report = JSON.parse(fs.readFileSync(reportPath, 'utf8'))
    for (const suiteNode of report.suites || []) walkSuite(suiteNode)
    for (const error of report.errors || []) rootErrors.push(oneLine(error.message || error.stack || error))
  } catch (error) {
    parseError = `Unable to parse Playwright JSON report: ${oneLine(error?.message || error)}`
  }
}

const payload = {
  contract: 'playwright-failure-diagnostics-v1',
  suite,
  head,
  runId,
  status: parseError || failures.length || rootErrors.length ? 'FAILED' : 'PASSED',
  parseError,
  failureCount: failures.length,
  rootErrorCount: rootErrors.length,
  failures,
  rootErrors
}
fs.writeFileSync(outputPath, `${JSON.stringify(payload, null, 2)}\n`, 'utf8')

const markdown = []
markdown.push(`## Playwright suite: ${suite}`)
markdown.push('')
markdown.push(`- HEAD: \`${head}\``)
markdown.push(`- Failures: **${failures.length}**`)
markdown.push(`- Root errors: **${rootErrors.length}**`)
if (parseError) markdown.push(`- Reporter error: ${parseError}`)
markdown.push('')
if (failures.length) {
  markdown.push('| # | Test | Status | Location | First error |')
  markdown.push('|---:|---|---|---|---|')
  failures.slice(0, 50).forEach((failure, index) => {
    const title = failure.title.replace(/\|/g, '\\|')
    const message = failure.message.replace(/\|/g, '\\|')
    markdown.push(`| ${index + 1} | ${title} | ${failure.status} | \`${failure.file}:${failure.line}\` | ${message} |`)
  })
} else if (!parseError && !rootErrors.length) {
  markdown.push('All selected Playwright tests passed.')
}
if (rootErrors.length) {
  markdown.push('')
  markdown.push('### Root reporter errors')
  rootErrors.slice(0, 20).forEach((error) => markdown.push(`- ${error}`))
}
markdown.push('')
if (stepSummary) fs.appendFileSync(stepSummary, `${markdown.join('\n')}\n`, 'utf8')
console.log(markdown.join('\n'))

if (parseError) {
  console.log(`::error title=Playwright reporter::${annotationEscape(parseError)}`)
}
for (const failure of failures.slice(0, 50)) {
  const file = annotationEscape(failure.file)
  const title = annotationEscape(`${suite}: ${failure.title}`)
  const message = annotationEscape(failure.message || failure.status)
  console.log(`::error file=${file},line=${failure.line},col=${failure.column},title=${title}::${message}`)
}
for (const error of rootErrors.slice(0, 20)) {
  console.log(`::error title=${annotationEscape(`${suite}: root reporter error`)}::${annotationEscape(error)}`)
}
NODE
}

run_playwright() {
  rm -f "$PLAYWRIGHT_JSON" "$FAILURE_JSON"
  (
    cd "$ROOT/e2e"
    PLAYWRIGHT_JSON_OUTPUT_NAME="$PLAYWRIGHT_JSON" \
      npx playwright test "$@" --reporter=line,json
  )
  local code=$?
  summarize_playwright_report "$PLAYWRIGHT_JSON" "$SUITE" "$FAILURE_JSON"
  return "$code"
}

run_specs() {
  local label="$1"
  shift
  printf '%s\n' "$@" > "$RESULT_DIR/${SUITE}-selected-specs.txt"
  echo "[browser-suite] suite=$SUITE group=$label specs=$#"
  run_playwright "$@"
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

    run_playwright "${GOLD_SPECS[@]}" \
      --retries=0 \
      --update-snapshots=all \
      --update-source-method=overwrite
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
