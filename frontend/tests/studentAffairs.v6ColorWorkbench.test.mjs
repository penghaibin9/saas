import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'

const main = fs.readFileSync(new URL('../src/main.js', import.meta.url), 'utf8')
const css = fs.readFileSync(new URL('../src/styles/student-affairs-v6-color-workbench.css', import.meta.url), 'utf8')
const dashboard = fs.readFileSync(new URL('../src/modules/studentAffairs/views/StudentAffairsDashboardView.vue', import.meta.url), 'utf8')
const student360 = fs.readFileSync(new URL('../src/views/admin/student/StudentDetailView.vue', import.meta.url), 'utf8')
const affairsProfile = fs.readFileSync(new URL('../src/modules/studentAffairs/views/StudentAffairsProfileDetailView.vue', import.meta.url), 'utf8')
const affairsFacade = fs.readFileSync(new URL('../src/modules/studentAffairs/api/studentAffairsB.api.js', import.meta.url), 'utf8')

const scopedRoot = '#app .base-portal-layout:has(.sa-v6-page-shell)'

test('colorful V6 stylesheet loads after global shell and theme hardening', () => {
  const themeIndex = main.indexOf("import './styles/base-portal-theme-controls.css'")
  const v6Index = main.indexOf("import './styles/student-affairs-v6-color-workbench.css'")
  assert.ok(themeIndex >= 0)
  assert.ok(v6Index > themeIndex)
})

test('colorful shell overrides are page-scoped and preserve the approved geometry', () => {
  assert.ok(css.includes(scopedRoot))
  assert.match(css, /--sa-v6-topbar-h:\s*54px/)
  assert.match(css, /--sa-v6-rail-w:\s*64px/)
  assert.match(css, /--sa-v6-nav-w:\s*232px/)
  assert.match(css, /--sa-v6-page-x:\s*16px/)
  assert.match(css, /--sa-v6-row-h:\s*66px/)
  assert.match(css, /@media \(max-width: 1450px\)[\s\S]*?--sa-v6-rail-w:\s*62px[\s\S]*?--sa-v6-nav-w:\s*214px/)
  assert.doesNotMatch(css, /(^|\n)(?!#app )\.bpl-(topbar|rail|aside|main)\s*\{/)
})

test('A1 uses a light conclusion surface, compact flow locator and semantic work rows', () => {
  assert.match(css, /\.sa-v6-hero__summary[\s\S]*?min-height:\s*82px/)
  assert.match(css, /\.sa-v6-flow[\s\S]*?min-height:\s*30px/)
  assert.match(css, /\.sa-v6-queue-row[\s\S]*?min-height:\s*var\(--sa-v6-row-h\)/)
  assert.match(css, /grid-template-columns:\s*40px\s+minmax\(0,\s*1fr\)\s+110px\s+92px/)
  assert.match(css, /@media \(max-width: 1450px\)[\s\S]*?grid-template-columns:\s*38px\s+minmax\(0,\s*1fr\)\s+108px\s+86px/)
  assert.match(css, /\.sa-v6-queue-row__count strong[\s\S]*?font-variant-numeric:\s*tabular-nums[\s\S]*?white-space:\s*nowrap/)
  assert.match(css, /\.sa-v6-queue-row\.is-danger/)
  assert.match(css, /\.sa-v6-entry-grid[\s\S]*?repeat\(2,/)
  assert.match(dashboard, /v-for="item in businessQueues"/)
  assert.match(dashboard, /:class="`is-\$\{item\.tone\}`"/)
})

test('visual work keeps the real A1 data boundary and does not add sample students', () => {
  assert.doesNotMatch(css, /李明轩|陈佳怡|赵宇航|王雨晴/)
  assert.doesNotMatch(dashboard, /priorityStudents|recommendedAction|dormExceptionCount/)
  assert.match(dashboard, /studentAffairsApi\.getDashboard\(\)/)
  assert.match(dashboard, /studentAffairsApi\.getAuditLogs\(\)/)
  assert.match(dashboard, /card\.drillPath/)
})

test('A1 remains isolated from A2 and keeps both real Student360 implementations intact', () => {
  assert.doesNotMatch(dashboard, /StudentDetailView|StudentAffairsProfileDetailView/)
  assert.match(student360, /studentApi\.getStudentDetail\(this\.\$route\.params\.studentId\)/)
  assert.match(affairsProfile, /studentAffairsApi\.getProfile\(this\.studentId\)/)
  assert.match(affairsProfile, /studentAffairsApi\.getTimeline\(this\.studentId\)/)
  assert.match(affairsFacade, /getProfile\(studentId\)\s*\{[\s\S]*?core\.getStudentProfile\(studentId\)/)
  assert.match(affairsFacade, /getTimeline\(studentId,\s*params\s*=\s*\{\}\)\s*\{[\s\S]*?core\.getStudentTimeline\(studentId,\s*params\)/)
})
