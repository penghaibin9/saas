import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'

const pageGuide = fs.readFileSync(
  new URL('../src/components/common/experience/AppPageGuide.vue', import.meta.url),
  'utf8'
)
const staffWorkbench = fs.readFileSync(
  new URL('../src/modules/workbench/views/WorkbenchView.vue', import.meta.url),
  'utf8'
)
const internshipDashboard = fs.readFileSync(
  new URL('../src/modules/internship/views/InternshipDashboardView.vue', import.meta.url),
  'utf8'
)
const internshipLayout = fs.readFileSync(
  new URL('../src/modules/internship/views/AdminInternshipLayout.vue', import.meta.url),
  'utf8'
)
const basePortalLayout = fs.readFileSync(
  new URL('../src/layouts/BasePortalLayout.vue', import.meta.url),
  'utf8'
)
const adminWorkbench = fs.readFileSync(
  new URL('../src/views/AdminWorkbenchView.vue', import.meta.url),
  'utf8'
)

test('Staff first screen does not auto-cover Today Work but keeps replayable help', () => {
  assert.match(pageGuide, /autoOpen:\s*\{\s*type:\s*Boolean,\s*default:\s*true\s*\}/)
  assert.match(pageGuide, /if\s*\(!this\.autoOpen\s*\|\|\s*!this\.steps\.length\)\s*return/)
  assert.match(pageGuide, /onGuideReplay\(this\.replay\)/)
  assert.match(staffWorkbench, /guide-key="workbench\.first-login"\s+:auto-open="false"/)
})

test('Internship Staff dashboard keeps bounded concrete work and removes duplicate metric blocks', () => {
  assert.match(internshipDashboard, /class="mp-card idb-today"/)
  assert.match(internshipDashboard, /v-for="item in workItems"/)
  assert.match(internshipDashboard, /最近发生了什么/)
  assert.match(internshipDashboard, /item\.waitingOn/)
  assert.match(internshipDashboard, /办完交给谁/)
  assert.match(internshipDashboard, /workItemLimit:\s*8/)

  assert.doesNotMatch(internshipDashboard, /<ModuleHero/)
  assert.doesNotMatch(internshipDashboard, /id="idb-batch-progress"/)
})

test('Internship Staff uses Today Work as the single work entry', () => {
  assert.match(internshipLayout, /\bhide-global-workbench\b/)
  assert.match(basePortalLayout, /!this\.hideGlobalWorkbench \|\| group\.key !== 'workbench'/)
  assert.match(adminWorkbench, /\['INTERN_MENTOR', 'INTERNSHIP_MENTOR', 'INTERN_ADVISOR'\]\.includes\(role\)/)
  assert.match(adminWorkbench, /this\.\$router\.replace\('\/admin\/internship'\)/)
})
