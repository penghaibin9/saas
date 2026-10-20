import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'

const view = fs.readFileSync(
  new URL('../src/modules/graduation/views/GraduationDefenseGradeView.vue', import.meta.url),
  'utf8',
)

test('graduation specialist workspace exposes only panels granted to the current role', () => {
  assert.match(view, /const PANEL_PERMISSIONS = \{[\s\S]*plagiarism: \['graduationDesign\.plagiarism\.view'\]/)
  assert.match(view, /review: \['graduationDesign\.review\.view'\]/)
  assert.match(view, /defense: \['graduationDesign\.defense\.score', 'graduationDesign\.defense\.scoreConfirm'\]/)
  assert.match(view, /grade: \['graduationDesign\.grade\.view'\]/)
  assert.match(view, /v-if="canPanel\('plagiarism'\)"/)
  assert.match(view, /v-if="canPanel\('review'\)"/)
  assert.match(view, /v-if="canPanel\('defense'\)"/)
  assert.match(view, /v-if="canPanel\('grade'\)"/)
})

test('route meta wins over a stale or forged panel query and API loading fails closed', () => {
  assert.match(view, /const requested = this\.\$route\.meta\?\.defaultPanel \|\| this\.routeText\(query\.panel\)/)
  assert.match(view, /this\.tab = this\.canPanel\(requested\) \? requested : \(this\.firstAllowedPanel\(\) \|\| 'plagiarism'\)/)
  assert.match(view, /if \(!this\.current \|\| !this\.canPanel\(this\.tab\)\) return false/)
  assert.match(view, /switchTab\(tab\) \{[\s\S]*if \(this\.commandLocked \|\| !this\.canPanel\(tab\)\) return/)
  assert.match(view, /const routeName = this\.panelRoute\(tab\)[\s\S]*if \(!routeName\) return/)
})

test('grade batch mode is invisible and non-callable without grade view permission', () => {
  assert.match(view, /v-if="canUseGradeBatch" class="gp-mode__btn"/)
  assert.match(view, /v-if="mode === 'batch' && canUseGradeBatch"/)
  assert.match(view, /canUseGradeBatch\(\) \{ return this\.canPanel\('grade'\) \}/)
  assert.match(view, /if \(!this\.canUseGradeBatch \|\| !batchId\)/)
  assert.match(view, /setMode\(mode\) \{[\s\S]*mode === 'batch' && !this\.canUseGradeBatch/)
})

test('defense secretary stays on the confirmation route instead of being sent to scoring', () => {
  assert.match(view, /graduation-defense-confirmation/)
  assert.match(view, /this\.hasPermission\('graduationDesign\.defense\.scoreConfirm'\)/)
  assert.match(view, /this\.hasPermission\('graduationDesign\.defense\.score'\)/)
  assert.match(view, /return 'graduation-defense-confirmation'/)
})

test('specialist reads and writes remain tied to current batch student and panel', () => {
  assert.match(view, /isCurrentSnapshot\(snapshot\)/)
  assert.match(view, /snapshot\.batchId === String\(this\.batchStore\.selectedBatchId \|\| ''\)/)
  assert.match(view, /snapshot\.studentId === String\(this\.current\?\.id \|\| ''\)/)
  assert.match(view, /snapshot\.tab === this\.tab/)
  assert.match(view, /createCommandSnapshot\(action, extra = \{\}\)/)
  assert.match(view, /route: this\.currentRouteSnapshot\(\)/)
})
