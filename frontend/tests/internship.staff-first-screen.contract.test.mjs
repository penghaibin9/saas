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

test('Staff first screen does not auto-cover Today Work but keeps replayable help', () => {
  assert.match(pageGuide, /autoOpen:\s*\{\s*type:\s*Boolean,\s*default:\s*true\s*\}/)
  assert.match(pageGuide, /if\s*\(!this\.autoOpen\s*\|\|\s*!this\.steps\.length\)\s*return/)
  assert.match(pageGuide, /onGuideReplay\(this\.replay\)/)
  assert.match(staffWorkbench, /guide-key="workbench\.first-login"\s+:auto-open="false"/)
})

test('Internship Staff dashboard leads with bounded concrete objects before metrics', () => {
  assert.match(internshipDashboard, /class="mp-card idb-today"/)
  assert.match(internshipDashboard, /v-for="item in workItems"/)
  assert.match(internshipDashboard, /最近发生了什么/)
  assert.match(internshipDashboard, /item\.waitingOn/)
  assert.match(internshipDashboard, /办完交给谁/)
  assert.match(internshipDashboard, /workItemLimit:\s*8/)

  const todayIndex = internshipDashboard.indexOf('class="mp-card idb-today"')
  const metricsIndex = internshipDashboard.indexOf('<ModuleHero')
  assert.ok(todayIndex >= 0 && metricsIndex > todayIndex, 'Today Work must render before KPI metrics')
})
