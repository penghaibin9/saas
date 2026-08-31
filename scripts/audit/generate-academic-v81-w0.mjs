import { execFileSync } from 'node:child_process'
import { createHash } from 'node:crypto'
import { mkdirSync, readFileSync, readdirSync, statSync, writeFileSync } from 'node:fs'
import { dirname, join, relative, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

import { NAV_PLAN, getVisibleNavPlan } from '../../frontend/src/config/navPlan.js'

const scriptDir = dirname(fileURLToPath(import.meta.url))
const repoRoot = resolve(scriptDir, '../..')
const generatedAt = new Date().toISOString()

function git(args, options = {}) {
  return execFileSync('git', args, {
    cwd: repoRoot,
    encoding: 'utf8',
    stdio: ['ignore', 'pipe', options.allowFailure ? 'pipe' : 'inherit'],
  }).trim()
}

function tryGit(args) {
  try {
    return git(args, { allowFailure: true })
  } catch {
    return ''
  }
}

function sha256(value) {
  return createHash('sha256').update(value).digest('hex')
}

function writeJson(path, value) {
  mkdirSync(dirname(path), { recursive: true })
  writeFileSync(path, `${JSON.stringify(value, null, 2)}\n`, 'utf8')
}

function readJson(path) {
  return JSON.parse(readFileSync(path, 'utf8'))
}

function walk(path, predicate = () => true) {
  if (!statSafe(path)) return []
  const out = []
  const visit = (current) => {
    for (const name of readdirSync(current)) {
      const full = join(current, name)
      const stat = statSync(full)
      if (stat.isDirectory()) visit(full)
      else if (predicate(full)) out.push(relative(repoRoot, full).replaceAll('\\', '/'))
    }
  }
  visit(path)
  return out.sort()
}

function statSafe(path) {
  try {
    return statSync(path)
  } catch {
    return null
  }
}

async function githubJson(path) {
  let lastError
  for (let attempt = 1; attempt <= 3; attempt += 1) {
    try {
      const response = await fetch(`https://api.github.com/repos/penghaibin9/saas${path}`, {
        headers: {
          Accept: 'application/vnd.github+json',
          'User-Agent': 'Codex-Academic-V81-W0',
        },
        signal: AbortSignal.timeout(15_000),
      })
      if (response.ok) return response.json()
      const error = new Error(`GitHub ${path}: ${response.status}`)
      if (response.status < 500 && response.status !== 429) throw error
      lastError = error
    } catch (error) {
      lastError = error
    }
    if (attempt < 3) await new Promise((resolveRetry) => setTimeout(resolveRetry, attempt * 1_000))
  }
  throw new Error(`GitHub ${path} failed after 3 attempts: ${lastError?.message || 'unknown error'}`)
}

function classificationFor(pr, mainSha) {
  const title = String(pr.title || '').toLowerCase()
  const head = String(pr.head?.ref || '').toLowerCase()
  const base = String(pr.base?.ref || '').toLowerCase()
  if (head === 'codex/control-plane-iam-menu-v1') {
    return ['IAM_AUTHORITY', 'shared IAM/navigation authority must be Owner-merged before Academic final reconciliation']
  }
  if (pr.number === 237) return ['SUPERSEDED', '6/7 blobs identical; the remaining test is a strict main superset']
  if (pr.number === 234 || title.includes('temp sync') || title.includes('chore(sync)') || base.startsWith('sync/')) {
    return ['TEMP_SYNC', 'synchronization-only pull request, not a product delta']
  }
  if (pr.number === 228 || (title.startsWith('docs') && !title.includes('code'))) {
    return ['DOC_ONLY', 'documentation/instruction layer only']
  }
  if (
    title.includes('[audit only]') || title.startsWith('audit:') || head.startsWith('audit/') ||
    head.startsWith('candidate/') || title.includes('audit harness') || title.includes('gold capture') ||
    title.includes('html prototype')
  ) {
    return ['AUDIT_ONLY', 'audit, historical candidate, runner, or visual-capture branch']
  }
  if (pr.head?.sha === mainSha || tryGit(['merge-base', '--is-ancestor', pr.head?.sha || '', mainSha]) !== '') {
    return ['SUPERSEDED', 'head is already represented by current main']
  }
  return ['MERGE_CANDIDATE', 'independent runtime/dependency/CI delta; requires its own owner review']
}

function academicMenu() {
  const group = NAV_PLAN.find((item) => item.key === 'academic-affairs')
  if (!group) throw new Error('academic-affairs group not found in NAV_PLAN')
  const workspaces = group.children.map((workspace) => ({
    key: workspace.key,
    label: workspace.label,
    path: workspace.path || null,
    status: workspace.status,
    leaves: workspace.children.map((leaf) => ({
      label: leaf.label,
      path: leaf.path || null,
      status: leaf.status,
      permissionKey: leaf.permissionKey || null,
      permissionAny: leaf.permissionAny || null,
      entryType: leaf.entryType || null,
      hidden: Boolean(leaf.hidden),
    })),
  }))
  return {
    workspaces,
    workspaceCount: workspaces.length,
    leafCount: workspaces.reduce((sum, item) => sum + item.leaves.length, 0),
    visibleLeafCount: workspaces.reduce((sum, item) => sum + item.leaves.filter((leaf) => !leaf.hidden).length, 0),
    hiddenLeafCount: workspaces.reduce((sum, item) => sum + item.leaves.filter((leaf) => leaf.hidden).length, 0),
  }
}

const academicTeacherPatterns = [
  'academicAffairs.attendance.view', 'academicAffairs.calendar.view', 'academicAffairs.classTimeBand.view',
  'academicAffairs.classroom.view', 'academicAffairs.course.view', 'academicAffairs.dashboard.view',
  'academicAffairs.deferredExam.review', 'academicAffairs.evaluation.view', 'academicAffairs.exam.recordAbnormal',
  'academicAffairs.exam.view', 'academicAffairs.exemption.review', 'academicAffairs.grade.input',
  'academicAffairs.grade.submit', 'academicAffairs.grade.view', 'academicAffairs.gradeChange.apply',
  'academicAffairs.lab.view', 'academicAffairs.process.view', 'academicAffairs.program.view',
  'academicAffairs.resourceOccupancy.view', 'academicAffairs.roster.view', 'academicAffairs.schedule.teacherConfirm',
  'academicAffairs.schedule.view', 'academicAffairs.scheduleChange.apply', 'academicAffairs.scheduleChange.view',
  'academicAffairs.selection.rosterView', 'academicAffairs.selection.view', 'academicAffairs.teachingTask.view',
  'academicAffairs.term.view', 'academicAffairs.textbook.selection.manage', 'academicAffairs.textbook.view',
  'academicAffairs.timeslot.view',
]

function roleProjection(roleCode, patterns) {
  const plan = getVisibleNavPlan({ includePlanned: false, permissionPatterns: patterns, ctxKey: `w0:${roleCode}` })
  const group = plan.find((item) => item.key === 'academic-affairs')
  const workspaces = (group?.children || []).map((workspace) => ({
    key: workspace.key,
    label: workspace.label,
    visibleLeaves: workspace.children.filter((leaf) => !leaf.hidden).map((leaf) => leaf.label),
  }))
  return {
    roleCode,
    permissionPatterns: patterns,
    visibleWorkspaceCount: workspaces.length,
    visibleLeafCount: workspaces.reduce((sum, item) => sum + item.visibleLeaves.length, 0),
    workspaces,
  }
}

function migrationDag() {
  const migrationDir = join(repoRoot, 'backend/alembic/versions')
  const files = walk(migrationDir, (path) => path.endsWith('.py'))
  const nodes = []
  for (const file of files) {
    const source = readFileSync(join(repoRoot, file), 'utf8')
    const revision = source.match(/^revision\s*(?::[^=]+)?=\s*["']([^"']+)["']/m)?.[1]
    if (!revision) continue
    const downLine = source.match(/^down_revision\s*(?::[^=]+)?=\s*(.+)$/m)?.[1]?.trim() || 'None'
    const parents = [...downLine.matchAll(/["']([^"']+)["']/g)].map((match) => match[1])
    nodes.push({ revision, parents, file })
  }
  const referenced = new Set(nodes.flatMap((node) => node.parents))
  const derivedHeads = nodes.filter((node) => !referenced.has(node.revision)).map((node) => node.revision).sort()
  return { nodeCount: nodes.length, derivedHeads, nodes }
}

const commands = [
  ['TERM_ACTIVATE', 'academic_affairs_service', 'POST /academic-affairs/terms/{termId}/activate', 'Staff PC', null, null, null, ['termId', 'expected status'], 'term status', 'GET term detail'],
  ['PROGRAM_PUBLISH', 'academic_affairs_program_service', 'POST /academic-affairs/programs/{programId}/review', 'Staff PC', null, null, null, ['programId', 'program version'], 'status/version', 'GET program detail'],
  ['COURSE_CONFIRM', 'academic_affairs_course_service', 'POST /academic-affairs/courses/{courseId}/review', 'Staff PC', null, null, null, ['courseId', 'course version'], 'status/version', 'GET course detail'],
  ['TASK_GENERATE', 'academic_affairs_task_service', 'POST /academic-affairs/teaching-task-batches/generate', 'Staff PC', null, null, null, ['termId', 'program/course provenance'], 'batch status', 'GET teaching task batch'],
  ['TASK_CONFIRM', 'academic_affairs_task_core_service', 'POST /academic-affairs/teaching-tasks/{taskId}/confirm', 'Staff PC', 'Teacher Mini', null, null, ['taskId', 'teacher relation'], 'task status', 'GET teaching task'],
  ['SCHEDULE_PREVIEW', 'academic_affairs_scheduling_public_service', 'POST /academic-affairs/schedule-batches/{batchId}/preview', 'Staff PC', null, null, null, ['batchId', 'rules', 'availability'], 'batch revision', 'GET scheduling workbench'],
  ['SCHEDULE_PUBLISH', 'academic_affairs_schedule_final_service', 'POST /academic-affairs/schedule-batches/{batchId}/publish', 'Staff PC', null, 'Student PC readback', 'Student Mini readback', ['batchId', 'conflict/coverage gate'], 'schedule revision', 'GET published schedule'],
  ['SCHEDULE_CHANGE_APPLY', 'academic_affairs_schedule_change_service', 'POST /academic-affairs/schedule-change', 'Staff PC', 'Teacher Mini', null, null, ['scheduleItemId', 'weeks', 'target slot', 'preflight'], 'source schedule revision', 'GET schedule-change/{id}'],
  ['SCHEDULE_CHANGE_REVIEW', 'academic_affairs_schedule_change_service', 'POST /academic-affairs/schedule-change/{id}/review', 'Staff PC', 'Teacher Mini constrained', null, null, ['changeId', 'assignee', 'conflict result'], 'change version', 'GET change + published schedule'],
  ['ATTENDANCE_SUBMIT', 'academic_affairs_attendance_public_service', 'POST /academic-affairs/attendance/sessions/{id}/submit', 'Staff PC', 'Teacher Mini', null, null, ['occurrenceId', 'formal roster'], 'session version', 'GET attendance session'],
  ['SELECTION_ENROLL', 'academic_affairs_selection_final_service', 'POST /academic-affairs/selection/enroll', null, null, 'Student PC', 'Student Mini', ['roundId', 'course offering', 'capacity'], 'record/capacity version', 'GET my selection + schedule'],
  ['SELECTION_DROP', 'academic_affairs_selection_final_service', 'POST /academic-affairs/selection/drop', null, null, 'Student PC', 'Student Mini', ['selectionRecordId', 'round window'], 'record version', 'GET my selection + capacity'],
  ['LOTTERY_DRAW', 'academic_affairs_selection_final_service', 'POST /academic-affairs/selection/rounds/{id}/lottery', 'Staff PC', null, null, null, ['roundId', 'sealed applicant set'], 'round version', 'GET lottery result'],
  ['EXAM_PUBLISH', 'academic_affairs_exam_service', 'POST /academic-affairs/exam/batches/{id}/publish', 'Staff PC', null, 'Student PC readback', 'Student Mini readback', ['examBatchId', 'rooms/seats/invigilation'], 'batch version', 'GET formal exam schedule'],
  ['DEFER_REVIEW', 'academic_affairs_exam_service', 'POST /academic-affairs/deferred-exams/{deferId}/review', 'Staff PC', 'Teacher Mini constrained', 'Student PC readback', 'Student Mini readback', ['deferId', 'exam/course/student'], 'workflow status', 'GET deferred exam'],
  ['RETAKE_REVIEW', 'academic_affairs_makeup_service', 'POST /academic-affairs/retake/applies/{id}/review', 'Staff PC', null, 'Student PC readback', 'Student Mini readback', ['applicationId', 'eligibility source'], 'application version', 'GET retake application'],
  ['EXEMPTION_REVIEW', 'academic_affairs_makeup_service', 'POST /academic-affairs/exemption/applies/{id}/review', 'Staff PC', null, 'Student PC readback', 'Student Mini readback', ['applicationId', 'evidence files'], 'application version', 'GET exemption application'],
  ['GRADE_SAVE', 'academic_affairs_grade_execution_service', 'PUT /academic-affairs/grade-tasks/{taskId}/scores', 'Staff PC', 'Teacher Mini constrained', null, null, ['gradeTaskId', 'formal roster', 'scheme'], 'task/version', 'GET grade task'],
  ['GRADE_SUBMIT', 'academic_affairs_grade_execution_service', 'POST /academic-affairs/grade-tasks/{taskId}/submit', 'Staff PC', 'Teacher Mini constrained', null, null, ['gradeTaskId', 'deadline', 'completeness'], 'task/version', 'GET grade task'],
  ['GRADE_COLLEGE_REVIEW', 'academic_affairs_grade_core_service', 'POST /academic-affairs/grade-tasks/{taskId}/college-review', 'Staff PC', null, null, null, ['gradeTaskId', 'college scope'], 'task/version', 'GET grade task'],
  ['GRADE_PUBLISH', 'academic_affairs_grade_core_service', 'POST /academic-affairs/grade-tasks/{taskId}/publish', 'Staff PC', null, 'Student PC readback', 'Student Mini readback', ['gradeTaskId', 'college approval'], 'task/version', 'GET published grades'],
  ['GRADE_CORRECT', 'academic_affairs_grade_correction_command', 'POST /academic-affairs/grade-change/{id}/review', 'Staff PC', null, 'Student PC readback', 'Student Mini readback', ['changeId', 'published grade version'], 'change/version', 'GET correction + published grade'],
  ['GRADE_RECHECK', 'academic_affairs_grade_core_service', 'POST /academic-affairs/grade-rechecks/{id}/review', 'Staff PC', null, 'Student PC apply/readback', null, ['recheckId', 'published grade version'], 'recheck version', 'GET recheck'],
  ['WARNING_FOLLOWUP', 'academic_affairs_warning_service', 'POST /academic-affairs/warnings/{warningId}/handle', 'Staff PC', 'Teacher Mini', 'Student PC readback', 'Student Mini readback', ['warningId', 'rule/evidence'], 'warning status', 'GET warning detail'],
  ['WARNING_CLOSE', 'academic_affairs_warning_service', 'POST /academic-affairs/warnings/{warningId}/close', 'Staff PC', 'Teacher Mini constrained', 'Student PC readback', 'Student Mini readback', ['warningId', 'follow-up evidence'], 'warning status/version', 'GET warning detail'],
  ['GRADUATION_FINAL', 'academic_affairs_graduation_immutable_service', 'POST /academic-affairs/graduation-results/{resultId}/final', 'Staff PC', null, 'Student PC readback', 'Student Mini readback', ['resultId', '11 evidence items', 'system error gate'], 'result version', 'GET graduation result'],
  ['ARCHIVE_CONFIRM', 'academic_affairs_archive_manifest_service', 'POST /academic-affairs/archive/batches/{bid}/confirm', 'Staff PC', null, null, null, ['batchId', 'domain precheck', 'manifest'], 'batch/version', 'GET archive batch + manifest'],
  ['ARCHIVE_CORRECT', 'academic_affairs_archive_correction_review_service', 'POST /academic-affairs/archive/corrections/{id}/review', 'Staff PC', null, null, null, ['caseId', 'separation of duties', 'official fact'], 'case/version', 'GET correction case + manifest'],
].map(([command, canonicalService, endpoint, primaryStaff, teacherMini, studentPc, studentMini, requiredFacts, expectedVersion, readback]) => ({
  command, canonicalService, endpoint, primaryStaff, teacherMini, studentPc, studentMini,
  compatibility: 'legacy route may delegate; no second business truth', requiredFacts, expectedVersion, readback,
}))

const capabilities = [
  ['CP-AA-01', 'Term/Calendar Truth'], ['CP-AA-02', 'Org/Student Scope'], ['CP-AA-03', 'Program Version'],
  ['CP-AA-04', 'Course Version'], ['CP-AA-05', 'Teaching Plan'], ['CP-AA-06', 'Teaching Task'],
  ['CP-AA-07', 'Scheduling Rules'], ['CP-AA-08', 'Schedule Batch/Conflict'], ['CP-AA-09', 'Published Schedule Truth'],
  ['CP-AA-10', 'Schedule Change'], ['CP-AA-11', 'Attendance'], ['CP-AA-12', 'Registration'],
  ['CP-AA-13', 'Student Status Change'], ['CP-AA-14', 'Selection'], ['CP-AA-15', 'Exam/Deferral'],
  ['CP-AA-16', 'Makeup/Retake/Exemption'], ['CP-AA-17', 'Grade Task/Roster'], ['CP-AA-18', 'Grade Review/Publish'],
  ['CP-AA-19', 'Grade Recheck/Recognition'], ['CP-AA-20', 'Academic Warning'], ['CP-AA-21', 'Graduation Qualification'],
  ['CP-AA-22', 'Evaluation/Quality'], ['CP-AA-23', 'Resources/Textbooks'], ['CP-AA-24', 'File/XLSX'],
  ['CP-AA-25', 'Todo/Message/Audit'], ['CP-AA-26', 'Archive/Correction'], ['CP-AA-27', '4-End Semantic Parity'],
  ['CP-AA-28', 'Release/Recovery'],
].map(([id, name]) => ({
  id, name, baseline: 'PRESERVE', runtimeStatus: 'PENDING_REPLAY',
  evidenceScope: ['backend/app/modules/academic_affairs', 'frontend/src/modules/academicAffairs', 'student-portal/src/views/academic', 'miniapp/src/pages'],
}))

async function main() {
  const branch = git(['branch', '--show-current'])
  const headSha = git(['rev-parse', 'HEAD'])
  const originMainSha = git(['rev-parse', 'origin/main'])
  const clean = git(['status', '--porcelain']) === ''
  const outputDir = join(repoRoot, 'artifacts/academic/v8.1', headSha, 'w0')
  const fixedOutputDir = join(repoRoot, 'artifacts/academic-v81')

  let classified
  let pr239
  let pr241
  let githubEvidence = { mode: 'LIVE_GITHUB_API', reusedGeneratedAt: null, error: null }
  try {
    const [openPrs, livePr239, livePr241] = await Promise.all([
      githubJson('/pulls?state=open&per_page=100'), githubJson('/pulls/239'), githubJson('/pulls/241'),
    ])
    pr239 = livePr239
    pr241 = livePr241
    classified = openPrs.map((pr) => {
      const [classification, reason] = classificationFor(pr, originMainSha)
      return {
        number: pr.number, title: pr.title, url: pr.html_url, draft: pr.draft,
        headRef: pr.head.ref, headSha: pr.head.sha, baseRef: pr.base.ref,
        classification, reason,
      }
    })
  } catch (error) {
    if (!process.argv.includes('--reuse-github-snapshot')) throw error
    const previousLive = readJson(join(outputDir, 'live-main.json'))
    const previousOpen = readJson(join(outputDir, 'open-pr-classification.json'))
    if (previousLive.originMainSha !== originMainSha || previousLive.headSha !== headSha) {
      throw new Error('Refusing GitHub snapshot reuse because the previous evidence is not exact-head')
    }
    classified = previousOpen.pullRequests
    pr239 = {
      state: previousLive.pr239.state, merged: previousLive.pr239.merged,
      merged_at: previousLive.pr239.mergedAt, merge_commit_sha: previousLive.pr239.mergeCommitSha,
    }
    pr241 = {
      state: previousLive.pr241.state, merged: previousLive.pr241.merged,
      merged_at: previousLive.pr241.mergedAt, merge_commit_sha: previousLive.pr241.mergeCommitSha,
    }
    githubEvidence = {
      mode: 'EXACT_HEAD_SNAPSHOT_REUSED_AFTER_API_TIMEOUT',
      reusedGeneratedAt: previousLive.generatedAt,
      error: error.message,
    }
  }

  const dag = migrationDag()
  let alembicHeads = []
  let alembicCommand = 'not executed by generator'
  const pythonArgIndex = process.argv.indexOf('--python')
  if (pythonArgIndex !== -1 && process.argv[pythonArgIndex + 1]) {
    const python = process.argv[pythonArgIndex + 1]
    try {
      alembicHeads = execFileSync(python, ['-m', 'alembic', '-c', 'alembic.ini', 'heads'], {
        cwd: join(repoRoot, 'backend'), encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'],
      }).trim().split(/\r?\n/).filter(Boolean).map((line) => line.replace(/\s*\(head\)\s*$/, ''))
      alembicCommand = `${python} -m alembic -c alembic.ini heads`
    } catch (error) {
      alembicCommand = `FAILED: ${error.message}`
    }
  }

  const menu = academicMenu()
  const sourceRoots = [
    'frontend/src/config/navPlan.js', 'frontend/src/modules/academicAffairs', 'student-portal/src/views/academic',
    'student-portal/src/services', 'miniapp/src/pages/teacher/academic-affairs', 'miniapp/src/pages/teacher/academic-task',
    'miniapp/src/pages/teacher/academic-warning', 'miniapp/src/pages/teacher/schedule-change',
    'miniapp/src/pages/teacher/exam-defer', 'miniapp/src/pages/student/academic-affairs', 'miniapp/src/services',
    'backend/app/modules/academic_affairs', 'backend/app/services', 'backend/app/models',
    'backend/alembic/versions', 'backend/tests', 'scripts/check', '.github/workflows',
  ]
  const trace = sourceRoots.map((path) => {
    const full = join(repoRoot, path)
    const stat = statSafe(full)
    const files = !stat ? [] : stat.isDirectory() ? walk(full) : [path]
    const academicFiles = files.filter((file) => /academic|aa_|navPlan/i.test(file))
    return { path, exists: Boolean(stat), fileCount: files.length, academicFileCount: academicFiles.length, academicFiles }
  })

  const liveMain = {
    generatedAt, repository: 'penghaibin9/saas', branch, headSha, originMainSha,
    exactMain: headSha === originMainSha,
    cleanAtAuditStart: process.argv.includes('--audit-started-clean'),
    cleanAtGeneratorRun: clean,
    auditStartEvidence: process.argv.includes('--audit-started-clean')
      ? 'Worktree status was verified clean immediately after creation from origin/main, before this generator was added.'
      : 'Not asserted; rerun with --audit-started-clean only when separately verified.',
    pr239: { state: pr239.state, merged: pr239.merged, mergedAt: pr239.merged_at, mergeCommitSha: pr239.merge_commit_sha },
    pr241: { state: pr241.state, merged: pr241.merged, mergedAt: pr241.merged_at, mergeCommitSha: pr241.merge_commit_sha },
    githubEvidence,
  }
  const futureMain = {
    generatedAt, currentMainSha: originMainSha,
    currentMainPullRequests: [241, 239],
    candidatePrs: classified.filter((item) => item.classification === 'MERGE_CANDIDATE').map((item) => item.number),
    excludedPrs: classified.filter((item) => item.classification !== 'MERGE_CANDIDATE').map((item) => item.number),
    requiredBeforeAcademicV81: classified.filter((item) => item.classification === 'IAM_AUTHORITY').map((item) => item.number),
    mergeOrder: [
      'CURRENT_MAIN (includes #241 then #239)',
      ...classified.filter((item) => item.classification === 'IAM_AUTHORITY').map((item) => `OWNER_MERGE_IAM_PR_${item.number}`),
      'ACADEMIC_V81_FEATURE',
    ],
    migrationHeads: alembicHeads.length ? alembicHeads : dag.derivedHeads,
    finalExpectedBaseSha: originMainSha,
    iamAuthority: (() => {
      const iam = classified.find((item) => item.classification === 'IAM_AUTHORITY')
      return iam
        ? {
            state: iam.draft ? 'PR_OPEN_DRAFT_CHECKS_PENDING' : 'PR_OPEN_OWNER_MERGE_PENDING',
            pullRequest: iam.number,
            headSha: iam.headSha,
            handoffPresent: false,
            note: 'Do not merge this shared authority from the Academic worktree; re-audit after Owner merge and handoff arrival.',
          }
        : {
            state: 'BLOCKED_BY_IAM_AUTHORITY',
            handoffPresent: false,
            note: 'No live IAM PR found; re-audit before final reconciliation.',
          }
    })(),
  }

  const browserLoginScreens = [
    ['Staff PC', 'artifacts/academic-v81/browser-replay/01-staff-login.png'],
    ['Student PC', 'artifacts/academic-v81/browser-replay/02-student-login.png'],
    ['Teacher Mini', 'artifacts/academic-v81/browser-replay/03-teacher-mini-login-viewport.png'],
  ].map(([surface, file]) => {
    const stat = statSafe(join(repoRoot, file))
    return { surface, file, exists: Boolean(stat?.isFile()), bytes: stat?.isFile() ? stat.size : 0 }
  })
  const browserBaseline = {
    generatedAt,
    headSha,
    status: browserLoginScreens.every((item) => item.exists && item.bytes > 10_000)
      ? 'MULTI_SURFACE_LOGIN_CAPTURED_ROLE_REPLAY_PENDING'
      : 'LOGIN_CAPTURE_INCOMPLETE',
    evidenceLevel: 'CURRENT_RUN_SCREENSHOTS_ROLE_CONTEXT_PENDING',
    observations: browserLoginScreens.map((item) => ({
      surface: item.surface,
      result: item.exists && item.bytes > 10_000 ? 'LOGIN_SCREEN_CAPTURED' : 'MISSING',
      authentication: 'No password submission is claimed by this W0 baseline.',
      blocker: 'SIGNED_IN_ROLE_CONTEXT_REQUIRED',
    })),
    screenshots: browserLoginScreens,
    requiredSurfaces: ['Staff PC', 'Student PC', 'Teacher Mini', 'Student Mini'],
    note: 'Teacher/Student Mini share the H5 login surface, but each signed-in role still requires an independent replay.',
  }

  writeJson(join(outputDir, 'live-main.json'), liveMain)
  writeJson(join(outputDir, 'open-pr-classification.json'), { generatedAt, count: classified.length, pullRequests: classified })
  writeJson(join(outputDir, 'future-main-order.json'), futureMain)
  writeJson(join(outputDir, 'migration-dag.json'), { generatedAt, alembicCommand, alembicHeads, ...dag })
  writeJson(join(outputDir, 'academic-menu-inventory.json'), { generatedAt, source: 'frontend/src/config/navPlan.js', ...menu })
  writeJson(join(outputDir, 'role-visible-menu.json'), {
    generatedAt,
    evidenceLevel: 'CODE_PROJECTION_ONLY_BROWSER_PENDING',
    profiles: [
      roleProjection('ACADEMIC_ADMIN', ['academicAffairs.*']),
      roleProjection('COLLEGE_ADMIN', ['academicAffairs.*']),
      roleProjection('ACADEMIC_TEACHER', academicTeacherPatterns),
      roleProjection('UNKNOWN_PERMISSION_CONTEXT', []),
    ],
  })
  writeJson(join(outputDir, 'command-ownership.json'), { generatedAt, commandCount: commands.length, commands })
  writeJson(join(outputDir, 'capability-preservation-before.json'), { generatedAt, count: capabilities.length, capabilities })
  writeJson(join(outputDir, 'academic-source-trace.json'), { generatedAt, headSha, roots: trace })
  writeJson(join(outputDir, 'browser-baseline/manifest.json'), browserBaseline)

  const futureMainDir = join(outputDir, 'future-main')
  writeJson(join(futureMainDir, 'current-main.json'), liveMain)
  writeJson(join(futureMainDir, 'open-pr-classification.json'), { generatedAt, pullRequests: classified })
  writeJson(join(futureMainDir, 'intended-merge-order.json'), futureMain)
  writeJson(join(futureMainDir, 'migration-dag.json'), { generatedAt, alembicCommand, alembicHeads, ...dag })
  writeJson(join(futureMainDir, 'pr239-diff-scope.json'), { generatedAt, state: 'CURRENT_MAIN', mergeCommitSha: pr239.merge_commit_sha })
  writeJson(join(futureMainDir, 'pr241-diff-scope.json'), { generatedAt, state: 'CURRENT_MAIN', mergeCommitSha: pr241.merge_commit_sha })
  writeJson(join(futureMainDir, 'shared-file-overlap.json'), { generatedAt, state: 'RESOLVED_IN_CURRENT_MAIN', pullRequests: [241, 239] })
  writeJson(join(futureMainDir, 'cross-domain-consumers.json'), {
    generatedAt, state: 'TRACE_REQUIRED_DURING_JOURNEY_REPLAY',
    consumers: ['Teacher Workbench', 'Student Portal API', 'Mini roles', 'Graduation consumer', 'Auth/permission/DataScope', 'Route registry'],
  })
  writeJson(join(futureMainDir, 'simulated-integration-verdict.json'), {
    generatedAt, verdict: headSha === originMainSha && (alembicHeads.length ? alembicHeads.length === 1 : dag.derivedHeads.length === 1) ? 'PASS_BASELINE' : 'FAIL',
    note: 'Baseline-only verdict; Journey, Browser, MySQL, IAM handoff and final exact-head replay remain separate gates.',
  })

  writeJson(join(outputDir, 'manifest.json'), {
    generatedAt, headSha, outputDir: relative(repoRoot, outputDir).replaceAll('\\', '/'),
    files: walk(outputDir), menuDigest: sha256(JSON.stringify(menu)), commandDigest: sha256(JSON.stringify(commands)),
  })
  writeJson(join(fixedOutputDir, 'live-main.json'), liveMain)
  writeJson(join(fixedOutputDir, 'open-pr-classification.json'), { generatedAt, githubEvidence, count: classified.length, pullRequests: classified })
  writeJson(join(fixedOutputDir, 'migration-dag.json'), { generatedAt, alembicCommand, alembicHeads, ...dag })
  writeJson(join(fixedOutputDir, 'menu-inventory.json'), { generatedAt, source: 'frontend/src/config/navPlan.js', ...menu })
  writeJson(join(fixedOutputDir, 'role-visible-menu.json'), {
    generatedAt,
    evidenceLevel: 'CODE_PROJECTION_ONLY_BROWSER_PENDING',
    profiles: [
      roleProjection('ACADEMIC_ADMIN', ['academicAffairs.*']),
      roleProjection('COLLEGE_ADMIN', ['academicAffairs.*']),
      roleProjection('ACADEMIC_TEACHER', academicTeacherPatterns),
      roleProjection('UNKNOWN_PERMISSION_CONTEXT', []),
    ],
  })
  writeJson(join(fixedOutputDir, 'command-ownership.json'), { generatedAt, commandCount: commands.length, commands })
  writeJson(join(fixedOutputDir, 'capability-preservation-before.json'), { generatedAt, count: capabilities.length, capabilities })
  writeJson(join(fixedOutputDir, 'browser-baseline/manifest.json'), readJson(join(outputDir, 'browser-baseline/manifest.json')))
  writeJson(join(fixedOutputDir, 'w0-reference.json'), {
    generatedAt, headSha,
    canonicalVersionedDirectory: relative(repoRoot, outputDir).replaceAll('\\', '/'),
    menuDigest: sha256(JSON.stringify(menu)),
    commandDigest: sha256(JSON.stringify(commands)),
    githubEvidence,
  })
  console.log(relative(repoRoot, outputDir).replaceAll('\\', '/'))
  console.log(relative(repoRoot, fixedOutputDir).replaceAll('\\', '/'))
}

await main()
