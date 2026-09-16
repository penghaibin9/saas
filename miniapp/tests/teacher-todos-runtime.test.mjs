import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'
import { reactive, computed, compile, createSSRApp, h } from 'vue'
import { renderToString } from '@vue/server-renderer'
import { createNetworkPager } from '../src/utils/networkPager.js'
import { canNavigate, disabledReasonOf } from '../src/services/actionRouterCore.mjs'

// Use Vue's cached computed values, not plain getters: the latter concealed
// updates made directly to the pager's non-reactive state.
function component(path, deps = {}) {
  const source = readFileSync(new URL(`../src/${path}`, import.meta.url), 'utf8')
    .match(/<script>([\s\S]*?)<\/script>/)[1]
    .replace(/^import .*$/gm, '').replace('export default', 'module.exports =')
  const ctx = { module: { exports: {} }, ...deps }
  vm.runInNewContext(source, ctx)
  const options = ctx.module.exports, data = reactive(options.data?.() || {}), page = {}
  for (const key of Object.keys(data)) Object.defineProperty(page, key, { get: () => data[key], set: v => { data[key] = v } })
  for (const [key, method] of Object.entries(options.methods || {})) page[key] = method.bind(page)
  for (const [key, getter] of Object.entries(options.computed || {})) {
    const value = computed(() => getter.call(page))
    Object.defineProperty(page, key, { get: () => value.value })
  }
  return { options, page }
}

const template = path => readFileSync(new URL(`../src/${path}`, import.meta.url), 'utf8').match(/<template>([\s\S]*?)<\/template>/)[1]
async function render(path, page, components = {}) {
  const draw = compile(template(path), { isCustomElement: tag => tag === 'scroll-view' })
  const app = createSSRApp({ render: () => draw(page, []) })
  for (const name of ['MobileTeacherHero', 'MobileShellIcon', 'MobileStatusTag', 'MobileGlobalState', 'MobileTeacherTabBar']) app.component(name, { render: () => h('span') })
  for (const [name, value] of Object.entries(components)) app.component(name, value)
  return renderToString(app)
}

const tick = () => new Promise(resolve => setImmediate(resolve))
const response = (ids, { pending = 1, done = 4, cursor = '' } = {}) => ({
  items: ids.map(todoId => ({ todoId, status: 'DONE' })), pendingCount: pending,
  filters: [{ key: 'all', label: '全部', badge: pending }, { key: 'done', label: '已处理', badge: done }],
  total: ids.length, nextCursor: cursor
})
function todos() {
  const requests = [], jumps = []
  let generation = 1
  const session = { identity: { userId: 'teacher-1', tenantId: 'school-1' }, currentRole: 'academic', dataScopeText: '本校' }
  const result = component('pages/teacher/todos/index.vue', {
    createNetworkPager, canNavigate, disabledReasonOf,
    currentSessionGeneration: () => generation, useSessionStore: () => session,
    teacherTodoT8Api: { list: params => new Promise((resolve, reject) => requests.push({ params, resolve, reject })) },
    TEACHER_TODO_PAGE_SIZE: 20, normalizeError: () => ({ pageState: 'error' }),
    deadlineText() {}, isOverdue() {}, runAction: (...args) => jumps.push(args)
  })
  result.options.onLoad?.call(result.page)
  return { ...result, requests, jumps, session, switchAccount: () => generation++ }
}

test('Vue computed list updates from empty to rows and across groups', async () => {
  const { page, options, requests } = todos()
  if (options.onShow) options.onShow.call(page)
  assert.equal(page.list.length, 0)
  requests[0].resolve(response(['pending-1'])); await tick()
  assert.equal(page.list[0]?.todoId, 'pending-1')
  const next = page.selectFilter('done')
  requests[1].resolve(response(['done-1', 'done-2', 'done-3', 'done-4'])); await next
  assert.equal(page.list.length, 4)
  assert.equal(page.filtersWithBadge.find(f => f.key === 'done').badge, 4)
})

test('returning reloads the selected group; changing identity clears the former rows and counts', async () => {
  const { page, options, requests, session, switchAccount } = todos()
  options.onShow.call(page); requests[0].resolve(response(['old'])); await tick()
  const done = page.selectFilter('done'); requests[1].resolve(response(['done'])); await done
  options.onHide.call(page); options.onShow.call(page)
  assert.equal(requests[2].params.group, 'done')
  requests[2].resolve(response(['new'])); await tick()
  assert.equal(page.list[0].todoId, 'new')
  options.onHide.call(page); session.currentRole = 'counselor'; switchAccount(); options.onShow.call(page)
  assert.equal(page.filter, 'all'); assert.equal(page.list.length, 0); assert.equal(page.pendingCount, null)
  requests[3].resolve(response([])); await tick()
})

test('late success cannot overwrite the latest group counts or rows', async () => {
  const { page, options, requests } = todos()
  options.onShow.call(page)
  const current = page.selectFilter('done')
  requests[1].resolve(response(['new'], { pending: 2 })); await current
  requests[0].resolve(response(['old'], { pending: 99 })); await tick()
  assert.equal(page.pendingCount, 2); assert.equal(page.list[0].todoId, 'new'); assert.equal(page.state, 'ready')
})

test('late failure cannot replace a successful group with an error', async () => {
  const { page, options, requests } = todos()
  options.onShow.call(page)
  const current = page.selectFilter('done')
  requests[1].resolve(response(['new'])); await current
  requests[0].reject(new Error('old failure')); await tick()
  assert.equal(page.state, 'ready'); assert.equal(page.list[0].todoId, 'new')
})

test('hidden pages and changed sessions reject pending responses', async () => {
  const { page, options, requests, switchAccount } = todos()
  options.onShow.call(page); options.onHide.call(page)
  requests[0].resolve(response(['hidden'])); await tick()
  assert.equal(page.list.length, 0)
  options.onShow.call(page); switchAccount()
  requests[1].resolve(response(['old-account'], { pending: 99 })); await tick()
  assert.equal(page.list.length, 0); assert.notEqual(page.pendingCount, 99)
})

test('pagination keeps rows on failure, retries the same cursor and renders appended rows', async () => {
  const { page, options, requests } = todos()
  options.onShow.call(page); requests[0].resolve(response(['one'], { cursor: 'page2' })); await tick()
  const more = page.loadMore(); page.loadMore()
  assert.equal(requests.length, 2); assert.equal(page.pagerState.loading, true)
  requests[1].reject(new Error('offline')); await more
  assert.equal(page.list.length, 1); assert.equal(page.pagingError, true); assert.equal(page.pagerState.loading, false)
  const retry = page.loadMore()
  assert.equal(requests[2].params.cursor, 'page2')
  requests[2].resolve(response(['one', 'two'])); await retry
  assert.equal(page.list.length, 2); assert.equal(page.pagerState.hasMore, false); assert.equal(page.pagingError, false)
})

test('blocked actions explain why and never navigate; valid actions retain the exact server target', () => {
  const { page, jumps } = todos()
  const blocked = { action: { disabledReason: '请在学校电脑端办理' } }
  assert.equal(page.canHandle(blocked), false)
  assert.equal(page.blockedReason(blocked), '请在学校电脑端办理')
  page.handle(blocked); page.handle({ action: { target: { path: '/pages/student/home/index' } } })
  assert.equal(jumps.length, 0)
  const action = { target: { path: '/pages/teacher/academic-task/index', query: { id: '1234567890123456789' } } }
  page.handle({ action }); assert.equal(jumps.length, 1); assert.equal(jumps[0][0], action)
})

test('the card renders a blocked reason instead of a working-looking action', async () => {
  const { options } = component('components/MobileTodoCard.vue', { MobileStatusTag: {}, messageModuleLabel: x => x })
  const state = { title: '调停课审批', overdue: false, status: '', moduleLabel: '', studentName: '', deadline: '', returnReason: '',
    actionDisabled: true, disabledReason: '请在学校电脑端办理', actionText: '去处理', $slots: {}, $emit() {} }
  const html = await render('components/MobileTodoCard.vue', state)
  assert.match(html, /请在学校电脑端办理/); assert.doesNotMatch(html, /<button/)
  state.actionDisabled = false
  assert.match(await render('components/MobileTodoCard.vue', state), /<button[^>]*>去处理<\/button>/)
  assert.equal(options.props.actionDisabled.default, false)
})

test('message categories visibly render their own unread badges and cap large counts', async () => {
  const { page } = component('pages/teacher/messages/index.vue', { fromNow() {} })
  page.state = 'ready'; page.badgeLoaded = true; page.badges = { system: 0, dynamic: 3, risk: 101, urge: 2 }
  const html = await render('pages/teacher/messages/index.vue', page)
  assert.match(html, /学生动态[\s\S]*?message-tab-badge[^>]*aria-label="3条未读"[^>]*>3</)
  assert.match(html, /风险预警[\s\S]*?message-tab-badge[^>]*>99\+</)
  page.badgeLoaded = false
  assert.doesNotMatch(await render('pages/teacher/messages/index.vue', page), /class="message-tab-badge"/)
})

test('bottom badges load real counts again on return and ignore a hidden-page response', async () => {
  const pending = [], { page, options } = component('components/MobileTeacherTabBar.vue', {
    currentSessionGeneration: () => 1,
    teacherTodoT8Api: { list: async () => ({ pendingCount: 4 }) },
    getTeacherMessageBadges: () => new Promise(resolve => pending.push(resolve))
  })
  page.pending = null; page.unread = null; page.active = 'workbench'
  options.mounted.call(page); pending[0]({ badges: { system: 1, risk: 2 } }); await tick()
  assert.equal(page.pendingCount, 4); assert.equal(page.unreadCount, 3)
  page.refresh(); page.invalidate(); pending[1]({ badges: { risk: 99 } }); await tick()
  assert.equal(page.unreadCount, null)
  page.refresh(); pending[2]({ badges: { system: 0, risk: 1 } }); await tick()
  assert.equal(page.unreadCount, 1)
  const tab = component('components/MobileTabBar.vue', { relaunch() {} }).options
  tab.render = compile(template('components/MobileTabBar.vue'))
  const html = await render('components/MobileTeacherTabBar.vue', page, { MobileTabBar: tab })
  assert.match(html, /mtabbar__badge[^>]*>1</)
})

test('completed schedule changes display only the exact personal receipt without approval buttons', async () => {
  const args = [], task = { taskId: '801', sourceBizType: 'AA_SCHEDULE_CHANGE', sourceBizId: '43', status: 'APPROVED', title: '调课审批', actedTime: '2026-09-10 10:00' }
  const { page } = component('pages/teacher/academic-affairs/schedule-change-review.vue', {
    teacherApi: { getScheduleChangePending: async () => ({ items: [], total: 0 }) },
    getDoneApprovals: async (...query) => { args.push(query); return { items: [task, { ...task, sourceBizId: '143' }] } },
    normalizeError: () => ({ pageState: 'error' }), isApprovalForbidden: () => false
  })
  page._pageActive = true; page._actionContext = 'ctx'; page.contextKey = () => 'ctx'; page.targetChangeId = '43'
  await page.load()
  assert.equal(page.state, 'ready'); assert.equal(page.completedTasks.length, 1)
  assert.deepEqual(args[0], [1, 100, '43', 'AA_SCHEDULE_CHANGE'])
  page.doAct({}, 'APPROVE') // No transport or confirmation may run for history.
  const receipt = component('components/MobileCompletedApprovalReceipt.vue').page
  receipt.tasks = page.completedTasks
  const html = await render('components/MobileCompletedApprovalReceipt.vue', receipt)
  assert.match(html, /本人已通过/); assert.match(html, /业务单号 43/); assert.doesNotMatch(html, /<button/)
})
