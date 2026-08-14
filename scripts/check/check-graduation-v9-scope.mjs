#!/usr/bin/env node
import { execFileSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'

const CARD_ALLOW = {
  S0_5: [
    /^scripts\/check\/check-graduation-v9-scope(?:\.test)?\.mjs$/,
    /^\.github\/workflows\/graduation-v9-scope\.yml$/,
  ],
  M1: [
    /^frontend\/src\/modules\/graduation\/api\/graduation-batch-context\.js$/,
    /^frontend\/src\/modules\/graduation\/api\/graduation(?:-more|-student|-risk-archive|-taskbook)?\.api\.js$/,
    /^frontend\/tests\/graduation\.v9-batch-context\.contract\.test\.mjs$/,
    /^backend\/tests\/test_graduation_round5_contracts\.py$/,
    /^scripts\/check\/check-graduation-production-gates\.mjs$/,
  ],
  M2: [
    /^backend\/app\/modules\/graduation\/routers\/graduation_student_eval\.py$/,
    /^backend\/app\/modules\/graduation\/services\/graduation_student_eval_service\.py$/,
    /^backend\/tests\/test_graduation_v9_student_eval_batch\.py$/,
    /^backend\/tests\/test_graduation_p2_eval_plan\.py$/,
  ],
  M4: [
    /^frontend\/src\/modules\/graduation\/views\/(AdminGraduationLayout|ProposalListView|FinalSubmissionListView|GraduationStudentListView)\.vue$/,
    /^frontend\/tests\/graduation\.v9-(?:product|reminder)-truth\.contract\.test\.mjs$/,
  ],
  M5: [
    /^backend\/app\/modules\/graduation\/materials\/(?:manifest|snapshot)_service\.py$/,
    /^backend\/app\/modules\/graduation\/routers\/graduation_archive_sensitive_router\.py$/,
    /^backend\/app\/modules\/graduation\/services\/graduation_archive_(?:service|consistency|data_quality)\.py$/,
    /^backend\/tests\/test_graduation_v9_u7_(?:archive_dirty_data|snapshot_dirty_guard)\.py$/,
  ],
  M7: [
    /^backend\/app\/modules\/graduation\/routers\/graduation_sensitive_router\.py$/,
    /^backend\/app\/modules\/graduation\/services\/__init__\.py$/,
    /^backend\/app\/modules\/graduation\/services\/graduation_grade_(?:read_)?service\.py$/,
    /^backend\/tests\/test_graduation_round7_pc_grade_contract\.py$/,
  ],
  U1: [
    /^frontend\/src\/modules\/graduation\/views\/GraduationDashboardView\.vue$/,
    /^frontend\/src\/modules\/graduation\/routes\.js$/,
    /^e2e\/specs\/graduation-v9-dashboard-visual\.spec\.mjs$/,
    /^e2e\/specs\/golden-rollout-business-pages\.spec\.mjs$/,
  ],
  U2: [
    /^backend\/app\/modules\/graduation\/services\/__init__\.py$/,
    /^backend\/app\/modules\/graduation\/services\/graduation_service\.py$/,
    /^backend\/app\/modules\/graduation\/services\/graduation_proposal_read_service\.py$/,
    /^backend\/tests\/test_graduation_v9_proposal_pagination\.py$/,
    /^frontend\/src\/modules\/graduation\/views\/ProposalListView\.vue$/,
    /^frontend\/tests\/graduation\.v9-proposal-review\.contract\.test\.mjs$/,
    /^e2e\/pages\/graduation\.page\.mjs$/,
    /^docs\/architecture\/file-capability-inventory\.d\/10-graduation-v9-export\.yaml$/,
  ],
  U3: [
    /^backend\/app\/modules\/graduation\/services\/__init__\.py$/,
    /^backend\/app\/modules\/graduation\/services\/graduation_final_read_service\.py$/,
    /^backend\/tests\/test_graduation_v9_final_pagination\.py$/,
    /^backend\/scripts\/e2e_seed_graduation_final_prerequisite\.py$/,
    /^frontend\/src\/modules\/graduation\/views\/FinalSubmissionListView\.vue$/,
    /^frontend\/tests\/graduation\.v9-final-review(?:-permission)?\.contract\.test\.mjs$/,
    /^e2e\/specs\/graduation-v9-final-review-visual\.spec\.mjs$/,
    /^docs\/architecture\/file-capability-inventory\.d\/10-graduation-v9-final-export\.yaml$/,
  ],
  U4: [
    /^backend\/app\/modules\/graduation\/routers\/graduation_process_sensitive_router\.py$/,
    /^backend\/app\/modules\/graduation\/services\/graduation_(?:process_consistency|guidance_stats_read_service)\.py$/,
    /^backend\/scripts\/e2e_seed_graduation_process_context\.py$/,
    /^backend\/tests\/test_graduation_v9_process_pagination\.py$/,
    /^frontend\/src\/modules\/graduation\/api\/graduation-student\.api\.js$/,
    /^frontend\/src\/modules\/graduation\/views\/GraduationProcess(?:Action(?:Base)?)?View\.vue$/,
    /^frontend\/tests\/graduation\.v9-process-context\.contract\.test\.mjs$/,
    /^e2e\/specs\/graduation-v9-process-visual\.spec\.mjs$/,
  ],
  U5: [
    /^backend\/app\/modules\/graduation\/services\/__init__\.py$/,
    /^backend\/app\/modules\/graduation\/services\/graduation_student_read_service\.py$/,
    /^backend\/tests\/test_graduation_v9_u5_student_list_scale\.py$/,
  ],
  U6: [
    /^\.github\/workflows\/graduation-targeted-repair\.yml$/,
    /^frontend\/src\/modules\/graduation\/views\/GraduationDefenseGrade(?:Form)?View\.vue$/,
  ],
  U7: [
    /^backend\/app\/modules\/graduation\/materials\/snapshot_service\.py$/,
    /^backend\/app\/modules\/graduation\/routers\/graduation_archive_sensitive_router\.py$/,
    /^backend\/app\/modules\/graduation\/services\/__init__\.py$/,
    /^backend\/app\/modules\/graduation\/services\/graduation_archive_(?:read_service|consistency|data_quality)\.py$/,
    /^backend\/tests\/test_graduation_v9_u7_(?:archive_dirty_data|snapshot_dirty_guard)\.py$/,
    /^frontend\/src\/modules\/graduation\/views\/GraduationRiskArchiveView\.vue$/,
    /^frontend\/tests\/graduation\.v9-archive-workbench\.contract\.test\.mjs$/,
    /^e2e\/specs\/graduation-v9-archive-visual\.spec\.mjs$/,
  ],
}

const ALWAYS_DENY = [
  /^frontend\/src\/layouts\/BasePortalLayout\.vue$/,
  /^frontend\/src\/services\/http\/client\.js$/,
  /^backend\/app\/(core\/security|api\/v1\/auth|services\/auth|services\/tenant)/,
]

const CANONICAL_WRITE_FILES = [
  /graduation_archive_service\.py$/,
  /graduation_grade_service\.py$/,
  /graduation_proposal_service\.py$/,
  /graduation_final_service\.py$/,
]

const CANONICAL_ALLOWED_CARDS = new Set(['M5', 'M7', 'M9', 'M10'])

export function patternsFor(card) {
  if (card === 'V9_PR') return Object.values(CARD_ALLOW).flat()
  return CARD_ALLOW[card] || []
}

export function validateFiles(files, card) {
  const allowed = patternsFor(card)
  if (!allowed.length) return [`unknown CURRENT_CARD=${card}`]
  const errors = []
  for (const file of files) {
    if (ALWAYS_DENY.some((re) => re.test(file))) {
      errors.push(`shared foundation denied: ${file}`)
      continue
    }
    if (card !== 'V9_PR' && CANONICAL_WRITE_FILES.some((re) => re.test(file)) && !CANONICAL_ALLOWED_CARDS.has(card)) {
      errors.push(`canonical write/read mixed service denied for ${card}: ${file}`)
      continue
    }
    if (!allowed.some((re) => re.test(file))) errors.push(`out of ${card} allowlist: ${file}`)
  }
  return errors
}

function gitLines(args) {
  const out = execFileSync('git', args, { encoding: 'utf8' }).trim()
  return out ? out.split(/\r?\n/).filter(Boolean) : []
}

function main() {
  const card = process.env.CURRENT_CARD || process.argv[2]
  const base = process.env.BASE_SHA || process.env.CARD_BASE_SHA || process.argv[3]
  const head = process.env.HEAD_SHA || process.argv[4] || 'HEAD'
  if (!card || !base) {
    console.error('usage: CURRENT_CARD=M1 BASE_SHA=<sha> [HEAD_SHA=<sha>] node scripts/check/check-graduation-v9-scope.mjs')
    process.exit(2)
  }
  const files = gitLines(['diff', '--name-only', `${base}..${head}`])
  const errors = validateFiles(files, card)
  if (errors.length) {
    console.error(`[graduation-v9-scope] RED card=${card} base=${base} head=${head}`)
    for (const error of errors) console.error(`- ${error}`)
    process.exit(1)
  }
  console.log(`[graduation-v9-scope] GREEN card=${card} files=${files.length}`)
  for (const file of files) console.log(`- ${file}`)
}

if (process.argv[1] && fileURLToPath(import.meta.url) === process.argv[1]) main()
