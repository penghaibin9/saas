import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'

const source = fs.readFileSync(new URL('../src/pages/student-internship/index.vue', import.meta.url), 'utf8')
const script = source.split('<script>')[1].split('</script>')[0]
  .replace(/^import .*$/gm, '').replace('export default', 'return')
const page = new Function('formatDateTime', 'toast', 'go', script)(String, () => {}, () => {})
function view(statusText) {
  const instance = { ...page.data(), i: { hasBatch: true, statusText }, compliance: {} }
  for (const [key, getter] of Object.entries(page.computed)) {
    Object.defineProperty(instance, key, { get: () => getter.call(instance) })
  }
  return instance
}
test('preparation retains every service while only onsite students get daily tasks', () => {
  const preparing = view('PREPARING')
  assert.equal(preparing.canShowDailyWork, false)
  const groups = preparing.serviceGroups
  assert.equal(groups.find(g => g.key === 'today').items.length, 1)
  assert.match(groups.find(g => g.key === 'today').items[0].path, /\/help\//)
  assert.equal(new Set(groups.flatMap(g => g.items.map(item => item.path))).size, 17)
  assert.equal(view('ONBOARD').canShowDailyWork, true)
  assert.equal(view('ONBOARD').serviceGroups.find(g => g.key === 'today').items.length, 4)
  assert.equal(view('ARCHIVED').canShowDailyWork, false)
})
test('a refreshed deep link returns to its parent and still respects the password gate', () => {
  const nav = fs.readFileSync(new URL('../src/utils/nav.js', import.meta.url), 'utf8')
    .replace(/import[\s\S]*?from[^\n]+\n/, '').replace(/export default[^\n]+/, '')
    .replace(/export /g, '')
  const calls = []
  let forced = false
  const back = new Function('uni', 'getCurrentPages', 'forcePasswordChangeRequired', 'FORCE_PASSWORD_CHANGE_ROUTE', 'isForcePasswordChangeRoute', nav + '\nreturn back')(
    { reLaunch: ({ url }) => calls.push(url), navigateBack: () => calls.push('back') },
    () => [{}], () => forced, '/required-password', () => false)
  back('/pages/teacher-internship/internship-students/index?batchId=22')
  assert.equal(calls.pop(), '/pages/teacher-internship/internship-students/index?batchId=22')
  forced = true
  back('/pages/student/me/index')
  assert.equal(calls.pop(), '/required-password')
})
