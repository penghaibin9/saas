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
test('student internship keeps one context-aware persistent primary action', () => {
  assert.doesNotMatch(source, /记录\s*\{\{\s*candidate\.recordId/)

  const onsite = view('ONBOARD')
  onsite.i = {
    hasBatch: true, historyMode: false, statusText: 'ONBOARD',
    checkin: { done: false }, weekly: { submitted: false, week: '第8' }
  }
  onsite.compliance = {}
  assert.equal(onsite.primaryAction.label, '立即打卡')

  onsite.i.checkin.done = true
  assert.equal(onsite.primaryAction.label, '填写第8周报')

  onsite.i.weekly.submitted = true
  assert.equal(onsite.primaryAction.done, true)
  assert.equal(onsite.primaryAction.label, '今天的实习任务已完成')

  onsite.compliance = { nextAction: { label: '补齐保险材料', route: '/pages/student-internship/insurance/index' } }
  assert.equal(onsite.primaryAction.label, '补齐保险材料')
  assert.equal(onsite.primaryAction.kind, 'route')
})

test('a refreshed deep link returns to its parent and still respects the password gate', () => {
  const nav = fs.readFileSync(new URL('../src/utils/nav.js', import.meta.url), 'utf8')
    .replace(/import[\s\S]*?from[^\n]+\n/, '').replace(/export default[^\n]+/, '')
    .replace(/export /g, '')
  const calls = []
  let forced = false
  const back = new Function('uni', 'getCurrentPages', 'forcePasswordChangeRequired', 'FORCE_PASSWORD_CHANGE_ROUTE', 'isForcePasswordChangeRoute', nav + '\nreturn back')(
    { reLaunch: ({ url, complete }) => { calls.push(url); complete() }, navigateBack: ({ complete }) => { calls.push('back'); complete() } },
    () => [{}], () => forced, '/required-password', () => false)
  back('/pages/teacher-internship/internship-students/index?batchId=22')
  assert.equal(calls.pop(), '/pages/teacher-internship/internship-students/index?batchId=22')
  forced = true
  back('/pages/student/me/index')
  assert.equal(calls.pop(), '/required-password')
})
