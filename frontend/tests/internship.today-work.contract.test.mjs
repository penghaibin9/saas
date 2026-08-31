import { readFile } from 'node:fs/promises'
import { test } from 'node:test'
import assert from 'node:assert/strict'

const dashboard = await readFile(new URL('../src/modules/internship/views/InternshipDashboardView.vue', import.meta.url), 'utf8')
const backend = await readFile(new URL('../../backend/app/modules/internship/services/internship_service.py', import.meta.url), 'utf8')

test('Today Work renders concrete objects before KPI and never writes from the dashboard', () => {
  const todayIndex = dashboard.indexOf('id="idb-todos"')
  const heroIndex = dashboard.indexOf('<ModuleHero')
  assert.ok(todayIndex > -1 && heroIndex > -1 && todayIndex < heroIndex, '真实对象必须先于 KPI/总览')
  assert.match(dashboard, /v-for="item in workItems"/)
  assert.match(dashboard, /item\.whyHere/)
  assert.match(dashboard, /item\.recentChange/)
  assert.match(dashboard, /item\.waitingOn/)
  assert.match(dashboard, /item\.nextActor/)
  assert.match(dashboard, /item\.receipt/)
  assert.doesNotMatch(dashboard, /internshipApi\.(review|handle|approve|publish|close)/)
})

test('dashboard projection reuses the three existing authorities and exposes continuity metadata', () => {
  for (const model of ['WeeklyReport', 'AttendanceException', 'RiskRecord']) {
    assert.match(backend, new RegExp(`select\\(${model}\\)`))
  }
  for (const field of ['whyHere', 'recentChange', 'waitingOn', 'nextActor', 'receipt', 'resumeKey', 'sourceVersion']) {
    assert.match(backend, new RegExp(`"${field}"`), `缺少 ${field}`)
  }
  assert.match(backend, /work_candidates\[:8\]/)
  assert.match(backend, /does not create\s*#?\s*another todo table/i)
})

test('missing batch is an actionable setup state rather than a load failure', () => {
  assert.match(dashboard, /v-else-if="needsBatch"/)
  assert.match(dashboard, /前往批次管理/)
  const missingBatchBranch = dashboard.slice(dashboard.indexOf('if (!this.batchStore.selectedBatchId)'), dashboard.indexOf('this.loading = true', dashboard.indexOf('if (!this.batchStore.selectedBatchId)') + 1))
  assert.match(missingBatchBranch, /this\.needsBatch = true/)
  assert.match(missingBatchBranch, /this\.error = ''/)
})

test('opening a concrete report or exception seeds the existing continuous-review queue', () => {
  assert.match(dashboard, /saveReviewQueue/)
  assert.match(dashboard, /WEEKLY_REPORT: 'weekly-report'/)
  assert.match(dashboard, /ATTENDANCE_EXCEPTION: 'attendance-exception'/)
  assert.match(dashboard, /listPath: '\/admin\/internship'/)
})
