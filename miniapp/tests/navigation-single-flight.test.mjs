import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'

function runtime() {
  const calls = [], notices = []
  let now = 0
  const uni = { showToast: value => notices.push(value.title) }
  for (const method of ['navigateTo', 'navigateBack', 'redirectTo', 'reLaunch']) {
    uni[method] = options => calls.push({ method, options })
  }
  const context = vm.createContext({ uni, Date: { now: () => now },
    forcePasswordChangeRequired: () => false,
    getCurrentPages: () => [{ route: 'pages/student/home/index' }, { route: 'pages/student/academic-affairs/schedule' }]
  })
  vm.runInContext(readFileSync(new URL('../src/utils/nav.js', import.meta.url), 'utf8')
    .replace(/import[\s\S]*?from[^\n]+\n/, '').replace(/export default[^\n]+/, '').replace(/export /g, ''), context)
  return { context, calls, notices, advance: ms => { now += ms } }
}

test('all navigation entry points share one in-flight transition', () => {
  const { context: c, calls } = runtime()
  c.go('/pages/student/academic-affairs/transcript')
  c.go('/pages/student/academic-affairs/transcript')
  c.back(); c.relaunch('/pages/student/home/index')
  c.goSibling('/pages/student/academic-affairs/exam', '/pages/student/academic-affairs/')
  assert.equal(calls.length, 1)
  calls[0].options.complete()
  c.goSibling('/pages/student/academic-affairs/exam', '/pages/student/academic-affairs/')
  assert.equal(calls[1].method, 'redirectTo')
})

test('fallback retains the lock and failure remains visible', () => {
  const { context: c, calls, notices } = runtime()
  c.go('/pages/student/academic-affairs/transcript')
  calls[0].options.fail(); calls[0].options.complete()
  c.go('/pages/student/academic-affairs/exam')
  assert.equal(calls.length, 2)
  assert.equal(calls[1].method, 'reLaunch')
  calls[1].options.fail(); calls[1].options.complete()
  assert.equal(notices[0], '页面暂时无法打开，请稍后重试')
  c.back()
  assert.equal(calls.length, 3)
})

test('missing host callback permits retry but late callbacks cannot unlock the new route', () => {
  const { context: c, calls, advance } = runtime()
  c.go('/first'); advance(8001); c.go('/second')
  calls[0].options.fail(); calls[0].options.complete()
  c.go('/third')
  assert.equal(calls.length, 2)
  calls[1].options.complete(); c.go('/third')
  assert.equal(calls.length, 3)
})
