import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'
import * as preferences from '../src/services/homeShortcutPreferences.mjs'

const { HOME_SHORTCUT_KEY: KEY, shortcutKey } = preferences
const items = Array.from({ length: 10 }, (_, index) => ({ name: `服务${index}`, cat: 'studentAffairs', action: { target: { path: `/pages/student/affairs/service${index}` }, allowedActions: ['OPEN'] } }))
const directory = { items, categories: [{ key: 'studentAffairs', label: '学工中心' }] }
const defaults = items.slice(0, 4).map(item => ({ key: shortcutKey(item), label: item.name, action: item.action }))
const deferred = () => { let resolve; const promise = new Promise(done => { resolve = done }); return { promise, resolve } }
function setup(initial) {
  let stored = initial, generation = 1
  const calls = [], notices = [], actions = []
  const api = { getServices: async () => directory }
  const transport = { request: async (path, options) => {
    calls.push({ path, ...options })
    if (options.method === 'POST') { stored = options.data.value; return { key: KEY, value: stored } }
    return { items: stored === undefined ? {} : { [KEY]: stored } }
  } }
  const source = readFileSync(new URL('../src/pages/student/home/HomeQuickServices.vue', import.meta.url), 'utf8').match(/<script>([\s\S]*?)<\/script>/)[1]
    .replace(/^import .*$/gm, '').replace('export default', 'module.exports =')
  const context = { module: { exports: {} }, ...preferences, studentApi: api,
    realRequest: (...args) => transport.request(...args), normalizeError: error => ({ text: error.message }),
    currentSessionGeneration: () => generation, canNavigate: action => Boolean(action?.target?.path && action?.allowedActions?.includes('OPEN') && !action.disabledReason),
    runAction: (...args) => actions.push(args), serviceVisual() {}, go() {}, toast: message => notices.push(message) }
  vm.runInNewContext(source, context)
  const options = context.module.exports, page = { ...options.data(), defaults }
  for (const [name, method] of Object.entries(options.methods)) page[name] = method.bind(page)
  for (const [name, getter] of Object.entries(options.computed)) Object.defineProperty(page, name, { get: () => getter.call(page) })
  return { page, options, api, transport, calls, notices, actions, switchAccount: () => { generation++; stored = undefined }, stored: () => stored }
}
const visible = page => Array.from(page.displayed, item => item.key)
const writes = state => state.calls.filter(call => call.method === 'POST')

test('recommendations, additions, removal and ordering save through API and survive remount', async () => {
  const state = setup(), { page } = state
  await page.load(); assert.equal(visible(page).length, 4)
  await page.openEditor(); page.toggle(shortcutKey(items[0])); page.toggle(shortcutKey(items[6])); page.move(3, -1)
  await page.save()
  assert.equal(page.editing, false); assert.equal(writes(state).length, 1)
  assert.deepEqual(state.calls.map(call => call.method || 'GET'), ['GET', 'POST', 'GET'])
  const next = setup(state.stored()); await next.page.load()
  assert.deepEqual(visible(next.page), [1, 2, 6, 3].map(i => shortcutKey(items[i])))
  await next.page.openEditor(); next.page.toggle(shortcutKey(items[9])); next.page.cancel()
  assert.deepEqual(visible(next.page), visible(page)); assert.equal(writes(next).length, 0)
})

test('deliberately empty selection stays empty; restore applies only after confirmed save', async () => {
  const state = setup('[]'); await state.page.load(); assert.deepEqual(visible(state.page), [])
  await state.page.openEditor(); state.page.restore(); assert.equal(state.page.draft.length, 4)
  state.page.cancel(); assert.deepEqual(visible(state.page), [])
  await state.page.openEditor(); state.page.restore(); await state.page.save(); assert.equal(visible(state.page).length, 4)
})

test('only current server-authorized entries are rendered, including recommended centers', async () => {
  const state = setup(JSON.stringify([shortcutKey(items[0]), 'teacher/secret', 'https://evil.example']))
  state.api.getServices = async () => ({ ...directory, items: [{ ...items[0], action: { ...items[0].action, disabledReason: '学校未开放' } }] })
  await state.page.load(); assert.deepEqual(visible(state.page), [])
  const center = { key: 'internship', label: '岗位实习', action: items[1].action }
  const recommended = setup(); recommended.page.defaults = [center]
  recommended.api.getServices = async () => ({ categories: [center], items: [] })
  await recommended.page.load(); await recommended.page.openEditor(); assert.deepEqual(Array.from(recommended.page.draft), [shortcutKey(center)])
})

test('eight-item cap, invalid config repair and bounded storage', async () => {
  const state = setup('{broken'); await state.page.load(); assert.match(state.page.error, /重新选择/)
  await state.page.openEditor(); items.forEach(item => state.page.toggle(shortcutKey(item)))
  assert.equal(state.page.draft.length, 8); assert.ok(state.notices.includes('最多选择8项常用服务'))
  await state.page.save(); assert.equal(state.page.error, ''); assert.ok(state.stored().length <= 500)
  assert.throws(() => preferences.encodeShortcuts(['a', 'a']))
  assert.throws(() => preferences.encodeShortcuts(['x'.repeat(501)]))
})

test('network or readback failure preserves draft and never announces saved success', async () => {
  for (const readbackFailure of [false, true]) {
    const state = setup(); await state.page.load(); await state.page.openEditor(); state.page.toggle(shortcutKey(items[7]))
    const savedRequest = state.transport.request
    state.transport.request = async (path, options) => { if (readbackFailure && options.method === 'POST') return savedRequest(path, options); throw new Error('网络连接失败，请重试') }
    await state.page.save(); assert.equal(state.page.editing, true); assert.equal(state.page.draft.length, 5)
    assert.equal(state.page.saving, false); assert.equal(state.notices.length, 0); assert.equal(visible(state.page).length, 4)
    state.transport.request = savedRequest; await state.page.save(); assert.equal(state.page.editing, false)
  }
})

test('double-save sends one write; permission removal during editing is checked before write', async () => {
  const state = setup(); await state.page.load(); await state.page.openEditor()
  const pending = deferred(); state.api.getServices = () => pending.promise
  const first = state.page.save(); await state.page.save(); assert.equal(writes(state).length, 0)
  pending.resolve(directory); await first; assert.equal(writes(state).length, 1)
  await state.page.openEditor(); state.api.getServices = async () => ({ ...directory, items: [] })
  await state.page.save(); assert.match(state.page.error, /已停用/); assert.equal(state.page.editing, true); assert.equal(writes(state).length, 1)
})

test('account change during load discards old results and releases loading for retry', async () => {
  const state = setup(JSON.stringify([shortcutKey(items[8])])), pending = deferred()
  state.api.getServices = () => pending.promise
  const loading = state.page.load(); state.switchAccount(); pending.resolve(directory); await loading
  assert.equal(state.page.loading, false); assert.equal(state.page.loaded, false); assert.deepEqual(visible(state.page), [])
  state.api.getServices = async () => directory; await state.page.load(); assert.deepEqual(visible(state.page), defaults.map(shortcutKey))
})

test('account change or unmount during save cannot write after directory check or publish stale results', async () => {
  for (const unmount of [false, true]) {
    const state = setup(); await state.page.load(); await state.page.openEditor()
    const pending = deferred(); state.api.getServices = () => pending.promise
    const saving = state.page.save()
    if (unmount) state.options.beforeUnmount.call(state.page); else state.switchAccount()
    pending.resolve(directory); await saving
    assert.equal(writes(state).length, 0); assert.equal(state.notices.length, 0)
    if (!unmount) assert.equal(state.page.saving, false)
  }
})

test('entry uses server action; stale account click reloads rather than navigating old entry', async () => {
  const state = setup(); await state.page.load(); state.page.openService(state.page.displayed[0]); assert.equal(state.actions.length, 1)
  state.switchAccount(); await state.page.openService(state.page.displayed[0]); assert.equal(state.actions.length, 1)
})
