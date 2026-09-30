import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'
import { teacherServices, teacherServiceRoute, TEACHER_SERVICE_ROUTES, teacherVisual } from '../src/services/teacherServiceCatalog.mjs'
import { createNetworkPager } from '../src/utils/networkPager.js'

const read = path => readFileSync(new URL(`../${path}`, import.meta.url), 'utf8')
function component(path, deps = {}) {
  const source = read(path).match(/<script>([\s\S]*?)<\/script>/)[1].replace(/^import .*$/gm, '').replace('export default', 'module.exports =')
  const context = { module: { exports: {} }, ...deps }
  vm.runInNewContext(source, context)
  const options = context.module.exports, page = { ...options.data() }
  for (const [key, fn] of Object.entries(options.methods || {})) page[key] = fn.bind(page)
  for (const [key, fn] of Object.entries(options.computed || {})) Object.defineProperty(page, key, { get: () => fn.call(page) })
  return { page, options }
}
const deferred = queue => new Promise((resolve, reject) => queue.push({ resolve, reject }))

test('service catalogue retains only published teacher routes and preserves exact queue contexts', () => {
  const manifest = JSON.parse(read('src/pages.json'))
  const routes = new Set(manifest.subPackages.flatMap(pkg => pkg.pages.map(page => '/' + pkg.root + '/' + page.path)))
  for (const path of Object.values(TEACHER_SERVICE_ROUTES)) assert.ok(routes.has(path.split('?')[0]), path)
  assert.equal(teacherServiceRoute('recommend', 'employment'), '/pages/teacher/employment-follow/index?tab=unemployed')
  assert.equal(teacherServiceRoute('gd-peer-review', 'gd_reviewer'), '/pages/teacher/graduation-guide/index?tab=peer')
  const config = { quickActions: [{ key: 'status' }, { key: 'examDefer' }, { key: 'missing' }] }
  const result = teacherServices(config, 'academic')
  assert.equal(result.length, 2)
  assert.equal(result[1].path, '')
  assert.ok(result[1].disabledReason)
})

test('internship catalogue fails closed and consults each existing scoped permission', () => {
  const config = { quickActions: [{ key: 'weekly' }, { key: 'insurance' }, { key: 'visit' }] }
  assert.equal(teacherServices(config, 'intern_mentor').length, 0)
  assert.deepEqual(teacherServices(config, 'intern_mentor', { can: permission => permission === 'internship.report.review' }).map(item => item.key), ['weekly'])
  assert.equal(teacherServiceRoute('risk', 'intern_mentor'), '/pages/teacher-internship/internship-risk/index')
  assert.deepEqual(teacherVisual('班级材料'), { icon: 'file-text', tone: 'violet' })
})

test('service search spans categories; late identity responses cannot replace a new role', async () => {
  const pending = [], navigated = []
  let generation = 1
  const session = { currentRole: 'counselor', isTeacher: true, roleConfig: { label: '辅导员', quickActions: [{ key: 'myClasses', label: '我的班级' }, { key: 'affairsLeave', label: '请假管理' }] }, applyRealUser() {} }
  const { page } = component('src/pages/teacher/services/index.vue', {
    useSessionStore: () => session, me: () => deferred(pending), currentSessionGeneration: () => generation,
    teacherServices, teacherVisual, normalizeError: () => ({ pageState: 'error' }), go: path => navigated.push(path), toast() {}
  })
  const old = page.load(); generation++
  session.currentRole = 'academic'
  session.roleConfig = { label: '教务老师', quickActions: [{ key: 'academicTask', label: '教学任务确认' }] }
  const latest = page.load(); pending[1].resolve({}); await latest; pending[0].resolve({}); await old
  assert.equal(page.services.length, 1); assert.equal(page.roleLabel, '教务老师')
  page.selectedCategory = '日常事务'; page.keyword = '教学'
  assert.equal(page.groups[0].items[0].key, 'academicTask')
  page.open(page.services[0]); assert.equal(navigated[0], '/pages/teacher/academic-task/index')
  session.currentRole = 'counselor'; page.open(page.services[0]); assert.equal(navigated.length, 1)
  const failed = page.load(); pending[2].reject(new Error('offline')); await failed
  assert.equal(page.state, 'error'); assert.equal(page.services.length, 0)
})

function messages() {
  let generation = 1
  const pending = [], reads = []
  const result = component('src/pages/teacher/messages/index.vue', {
    currentSessionGeneration: () => generation, createNetworkPager, fromNow() {}, go() {}, stashDetail() {}, canNavigate() {}, runAction() {},
    normalizeError: () => ({ pageState: 'error' }),
    getTeacherMessagesPage: () => deferred(pending), getTeacherMessageBadges: async () => ({ badges: { system: 1 } }),
    markTeacherMessageRead: () => deferred(reads)
  })
  result.page.setupPager()
  return { ...result, pending, reads, switchAccount: () => generation++ }
}
test('message category races and pagination keep only the latest visible response', async () => {
  const { page, pending } = messages()
  const old = page.refresh(), latest = page.selectTab('risk')
  pending[1].resolve({ items: [{ id: 'risk' }], nextCursor: 'next' }); await latest
  pending[0].resolve({ items: [{ id: 'old' }] }); await old
  assert.equal(page.list[0].id, 'risk')
  const more = page.loadMore(); pending[2].resolve({ items: [{ id: 'risk' }, { id: 'next' }] }); await more
  assert.deepEqual(Array.from(page.list, item => item.id), ['risk', 'next'])
  assert.equal(page.pagerState.hasMore, false)
})
test('message errors remain retryable and a prior-account response cannot populate the screen', async () => {
  const { page, pending, switchAccount } = messages()
  const failed = page.refresh(); pending[0].reject(new Error('network')); await failed
  assert.equal(page.state, 'error')
  const stale = page.refresh(); switchAccount(); pending[1].resolve({ items: [{ id: 'previous-account' }] }); await stale
  assert.equal(page.list.length, 0)
})
test('only persisted notices can become read; failed read rolls back without completing a todo', async () => {
  const { page, reads } = messages()
  const todo = { id: '123', kind: 'TODO', read: false }
  page.markRead(todo); assert.equal(todo.read, false); assert.equal(reads.length, 0)
  const notice = { id: '1234567890123456789', kind: 'UNIFIED_MESSAGE', read: false }
  page.badges.system = 1; page.markRead(notice); page.markRead(notice)
  assert.equal(reads.length, 1); assert.equal(page.badges.system, 0)
  reads[0].reject(new Error('network')); await new Promise(resolve => setImmediate(resolve))
  assert.equal(notice.read, false); assert.equal(page.badges.system, 1)
})

test('teacher and student identity refresh retain verified school names only within the same tenant', () => {
  const source = read('src/stores/session.js').replace(/^import .*$/gm, '').replace('export const useSessionStore', 'const useSessionStore').replace('export default useSessionStore', '')
  let store
  vm.runInNewContext(source, {
    defineStore: (_, options) => { store = options; return () => ({}) },
    registerForceLogoutHandler() {}, ROLE: { STUDENT: 'student' },
    getRoleConfig: role => ({ side: role === 'student' ? 'student' : 'teacher' }),
    roleKeyFromBackendRole: value => value, setForcePasswordChange() {}
  })
  for (const roleCode of ['student', 'counselor']) {
    const page = { ...store.state(), persist() {} }
    const identity = { userId: 'db-1', tenantId: '1000000000000000007', tenantName: '学校甲', currentRole: { roleCode } }
    store.actions.applyRealUser.call(page, identity)
    store.actions.applyRealUser.call(page, { ...identity, tenantName: undefined })
    assert.equal(page.mockUser.tenantName, '学校甲')
    store.actions.applyRealUser.call(page, { ...identity, tenantId: '1000000000000000008', tenantName: undefined })
    assert.equal(page.mockUser.tenantName, '')
    page.mockUser.tenantName = '未核验的缓存'; page.persistedIdentityVerified = false
    store.actions.applyRealUser.call(page, { ...identity, tenantName: undefined })
    assert.equal(page.mockUser.tenantName, '')
  }
})

test('returning during a workbench load starts a current request and restores real identity after refresh', async () => {
  const identities = []
  const session = { currentRole: 'counselor', isTeacher: true, identity: { userId: 'db-1' }, realUser: { tenantId: '7' }, roleConfig: { label: '辅导员', quickActions: [] }, mockUser: {}, applyRealUser() { this.mockUser = { name: '真实教师' } } }
  const { page, options } = component('src/pages/teacher/workbench/index.vue', {
    tenantBrandConfig: {}, teacherDateText: () => '', teacherGreeting: () => '', ensureTeacherPerformanceApi() {},
    teacherServices, teacherVisual, teacherServiceRoute, currentSessionGeneration: () => 1,
    useSessionStore: () => session, useInternshipContextStore: () => ({}), getTeacherWorkbenchVersion: () => 1,
    me: () => deferred(identities), teacherApi: { getWorkbench: async () => ({ pendingTotal: 3, dueSoon: [] }) },
    normalizeError: () => ({ pageState: 'error' }), getTeacherMessagesPage: async () => ({ items: [] }),
    deadlineText() {}, isOverdue() {}, fromNow() {}, messageModuleLabel() {}, go() {}, toast() {}
  })
  page._pageActive = true
  const old = page.load(); options.onHide.call(page)
  page._pageActive = true
  const latest = page.load()
  assert.equal(identities.length, 2)
  identities[1].resolve({}); await latest
  assert.equal(page.state, 'ready'); assert.equal(page.user.name, '真实教师'); assert.equal(page.todoBadge, 3)
  identities[0].resolve({}); await old
  assert.equal(page.state, 'ready'); assert.equal(page.todoBadge, 3)
})

test('teacher shell keeps page layout outside component slots for WeChat style isolation', () => {
  const hero = read('src/components/MobileTeacherHero.vue')
  assert.doesNotMatch(hero, /<slot\b/)
  for (const path of [
    'src/pages/teacher/workbench/index.vue',
    'src/pages/teacher/services/index.vue',
    'src/pages/teacher/me/index.vue'
  ]) {
    const source = read(path)
    assert.match(source, /<MobileGlobalState v-if="state !== 'ready'"/)
    assert.doesNotMatch(source, /<MobileGlobalState :state="state"/)
  }
})
