import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'
import test from 'node:test'

const directory = new URL('../src/pages/student/academic-affairs/', import.meta.url)

function deferred() {
  let resolve
  const promise = new Promise(done => { resolve = done })
  return { promise, resolve }
}

function pageData(page, items, total = 45) {
  return { items, total, page, pageSize: 20, hasMore: page * 20 < total }
}

function mount(getMyWarnings) {
  const session = { generation: 1 }
  const routes = []
  const context = vm.createContext({
    studentApi: { getMyWarnings },
    currentSessionGeneration: () => session.generation,
    go: route => routes.push(route),
    AcademicPageNav: {}, AcademicPageState: {}, MobileStatusTag: {}, MobileTabBar: {}
  })
  const helper = readFileSync(new URL('read-page.js', directory), 'utf8')
    .replace(/^import .*$/gm, '').replace(/export (const|function) /g, '$1 ')
  vm.runInContext(helper, context)
  const source = readFileSync(new URL('warning.vue', directory), 'utf8')
  const script = source.match(/<script>([\s\S]*?)<\/script>/)[1]
    .replace(/^import .*$/gm, '').replace('export default', 'component =')
  vm.runInContext(script, context)
  const layers = []
  const collect = component => { for (const mixin of component.mixins || []) collect(mixin); layers.push(component) }
  collect(context.component)
  const page = {}
  for (const layer of layers) Object.assign(page, layer.data?.call(page) || {})
  for (const layer of layers) for (const [key, fn] of Object.entries(layer.methods || {})) page[key] = fn.bind(page)
  for (const layer of layers) for (const [key, getter] of Object.entries(layer.computed || {})) Object.defineProperty(page, key, { get: () => getter.call(page) })
  const hook = hookName => layers.forEach(layer => layer[hookName]?.call(page))
  return { page, session, routes, source, definition: context.component, hook }
}

test('warning page uses one verified server page at a time and preserves its page while opening linked reads', async () => {
  const calls = []
  const mounted = mount(async params => {
    calls.push(params)
    return pageData(params.page, [{ warningId: `w-${params.page}`, level: 'MEDIUM' }])
  })
  await mounted.page.load()
  assert.deepEqual(calls.map(call => ({ page: call.page, pageSize: call.pageSize })), [{ page: 1, pageSize: 20 }])
  assert.equal(mounted.page.d.items.length, 1)
  assert.match(mounted.page.warningCoverageText, /第 1 \/ 3 页，本页 1 条，共 45 条/)

  await mounted.page.nextPage()
  assert.equal(calls.at(-1).page, 2)
  assert.equal(calls.at(-1).pageSize, 20)
  assert.equal(mounted.page.page, 2)
  assert.equal(mounted.page.d.items[0].warningId, 'w-2')
  mounted.page.go('/pages/student/academic-affairs/transcript')
  assert.equal(mounted.page.page, 2)
  assert.equal(mounted.routes.at(-1), '/pages/student/academic-affairs/transcript')
  assert.doesNotMatch(mounted.source, /\.slice\(/, '服务端页不能再被客户端切片伪分页')
})
test('warning deep link reports a current-page miss and never scans every page', async () => {
  const calls = []
  const mounted = mount(async params => {
    calls.push(params)
    return pageData(params.page, [{ warningId: 'w-current', level: 'LOW' }], 51)
  })
  mounted.page.targetId = 'w-deep-link'
  await mounted.page.load()
  assert.equal(calls.length, 1)
  assert.equal(calls[0].page, 1)
  assert.equal(calls[0].pageSize, 20)
  assert.match(mounted.page.targetNotice, /未在当前页定位/)
  assert.equal(mounted.page.state, 'ready')
})
test('warning page remains navigable when the total shrinks below the current page', async () => {
  const mounted = mount(async params => pageData(params.page, [], 0))
  await mounted.page.load(3)
  assert.equal(mounted.page.state, 'ready')
  assert.equal(mounted.page.page, 3)
  assert.equal(mounted.page.hasPrevious, true)
  assert.equal(mounted.page.hasNext, false)
  await mounted.page.previousPage()
  assert.equal(mounted.page.page, 2)
})
// End of pagination lifecycle test.
test('unknown or coerced warning totals never become a successful empty page', async () => {
  for (const total of [null, false, '', '0']) {
    const mounted = mount(async () => pageData(1, [], total))
    await mounted.page.load(1)
    assert.equal(mounted.page.state, 'error')
    assert.equal(mounted.page.d, null)
  }
})

test('warning paging ignores stale results, clears 403 data, and resets page on identity change', async () => {
  const second = deferred()
  let forbidden = false
  const calls = []
  const mounted = mount(params => {
    calls.push(params)
    if (forbidden) throw { httpStatus: 403, code: '403001' }
    if (params.page === 2) return second.promise
    return Promise.resolve(pageData(1, [{ warningId: 'fresh-page-1' }]))
  })
  await mounted.page.load(1)
  const oldPage = mounted.page.load(2)
  await mounted.page.load(1)
  second.resolve(pageData(2, [{ warningId: 'stale-page-2' }]))
  await oldPage
  assert.equal(mounted.page.page, 1)
  assert.equal(mounted.page.d.items[0].warningId, 'fresh-page-1')

  forbidden = true
  mounted.page.targetId = 'private-warning'
  await mounted.page.load()
  assert.equal(mounted.page.state, 'forbidden')
  assert.equal(mounted.page.d, null)
  assert.equal(mounted.page.targetId, '')

  forbidden = false
  mounted.page.page = 3
  mounted.page.targetId = 'old-identity-warning'
  mounted.session.generation += 1
  await mounted.page.load(3)
  assert.equal(calls.at(-1).page, 1)
  assert.equal(calls.at(-1).pageSize, 20)
  assert.equal(mounted.page.page, 1)
  assert.equal(mounted.page.targetId, '')

  const late = deferred()
  const hidden = mount(() => late.promise)
  const pending = hidden.page.load()
  hidden.hook('onHide')
  late.resolve(pageData(1, [{ warningId: 'late-warning' }]))
  await pending
  assert.equal(hidden.page.d, null)
})
