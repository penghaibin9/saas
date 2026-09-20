import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

const nav = readFileSync(new URL('../src/components/MobileNavBar.vue', import.meta.url), 'utf8')
const leave = readFileSync(new URL('../src/pages/student/affairs/leave.vue', import.meta.url), 'utf8')

test('legacy back shorthand and show-back share one live mobile return action', () => {
  assert.match(nav, /back:\s*\{ type: Boolean, default: false \}/)
  assert.match(nav, /canGoBack\(\) \{ return this\.showBack \|\| this\.back \}/)
  assert.match(nav, /v-if="canGoBack" class="mnav__back"/)
  assert.match(nav, /if \(!this\.canGoBack \|\| this\.backing\) return/)
})

test('a one-page H5 deep link returns to the signed-in role workbench, not blindly to login', () => {
  assert.match(nav, /const STUDENT_HOME = '\/pages\/student\/home\/index'/)
  assert.match(nav, /const TEACHER_HOME = '\/pages\/teacher\/workbench\/index'/)
  assert.match(nav, /session\?\.logged && session\?\.isTeacher/)
  assert.match(nav, /navBack\(this\.resolvedFallbackUrl\)/)
})

test('leave deep links fall back to the student affairs home when browser history is absent', () => {
  assert.match(leave, /<MobileNavBar variant="brand" title="我的请假" back fallback-url="\/pages\/student\/affairs\/index"\s*\/>/)
})
