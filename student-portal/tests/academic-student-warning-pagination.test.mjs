import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { parse, compileScript } from '@vue/compiler-sfc'
import * as vue from 'vue'
import * as ui from '../src/components/academic/studentAcademicUi.js'
import * as guard from '../src/components/academic/studentAcademicCommandGuard.js'

function mount(loader, initialQuery = {}) {
  const source = readFileSync(new URL('../src/views/academic/StudentAcademicReadOnlyView.vue', import.meta.url), 'utf8')
  let script = compileScript(parse(source).descriptor, { id: 'warning-paging' }).content
  const route = vue.reactive({ path: '/academic/warning', query: initialQuery, meta: { academicReadModel: 'warning' } })
  const session = { user: { userId: 'A', studentNo: 'S-A' }, token: 'token-A' }
  const navigations = [], disposers = []
  const modules = {
    vue: { ...vue, onMounted() {}, onBeforeUnmount: fn => disposers.push(fn) },
    'vue-router': { useRoute: () => route, useRouter: () => ({ push: location => navigations.push(location) }) },
    '../../services/portalApi': { portalApi: { academicWarning: loader } },
    '../../stores/session': { useSessionStore: () => session },
    '../../components/academic/studentAcademicUi': ui,
    '../../components/academic/studentAcademicCommandGuard': guard
  }
  script = script.replace(/^import (.+?) from ['"](.+?)['"];?$/gm, (_, binding, path) =>
    binding.startsWith('{') ? `const ${binding.replace(/\bas\b/g, ':')} = modules[${JSON.stringify(path)}]` : `const ${binding} = {}`
  ).replace('export default', 'return')
  const component = new Function('modules', script)(modules)
  return { ...component.setup({}, { expose() {} }), route, session, navigations, dispose: () => disposers.forEach(fn => fn()) }
}

const result = (page, items = [{ warningId: String(page) }], total = 51) => ({ items, total, page, pageSize: 50, hasMore: page * 50 < total })
const deferred = () => {
  let resolve, reject
  const promise = new Promise((yes, no) => { resolve = yes; reject = no })
  return { promise, resolve, reject }
}

test('warning page uses the URL page and preserves original object identity when paging back', async () => {
  const requests = []
  const page = mount(async params => { requests.push(params); return result(params.page) }, { warningPage: '2', warningId: '9007199254740993' })
  await page.load()
  assert.deepEqual(requests, [{ page: 2, pageSize: 50 }])
  assert.equal(page.warningPageReady.value, true)
  assert.equal(page.warningTotal.value, 51)
  assert.equal(page.warningIsPartial.value, false)
  page.changeWarningPage(3)
  assert.equal(page.navigations.length, 0)
  page.changeWarningPage(1)
  assert.equal(page.navigations[0].query.warningPage, '1')
  assert.equal(page.navigations[0].query.warningId, '9007199254740993')
  page.dispose()
})

test('warning page rejects wrong-page, contradictory-count and malformed receipts', async () => {
  for (const payload of [result(1), result(2, [{ warningId: '2' }], 0), { ...result(2), hasMore: true }, { ...result(2), items: null }]) {
    const page = mount(async () => payload, { warningPage: '2' })
    await page.load()
    assert.notEqual(page.error.value, '')
    assert.equal(page.rows.value.length, 0)
    assert.equal(page.warningPageReady.value, false)
    page.dispose()
  }
})

test('late warning reply cannot overwrite a newer reload or the next student', async () => {
  const late = deferred()
  let reads = 0
  const page = mount(async () => ++reads === 1 ? late.promise : result(1, [{ warningId: 'new' }]))
  const earlier = page.load()
  page.session.user = { userId: 'B', studentNo: 'S-B' }; page.session.token = 'token-B'
  await page.load()
  late.resolve(result(1, [{ warningId: 'old-private' }]))
  await earlier
  assert.equal(page.rows.value[0].warningId, 'new')
  assert.equal(page.error.value, '')
  page.dispose()
})

test('warning 403 clears prior records and component disposal suppresses late success', async () => {
  const late = deferred()
  let reads = 0
  const page = mount(async () => {
    if (++reads === 1) return result(1)
    if (reads === 2) throw Object.assign(new Error('Forbidden'), { status: 403 })
    return late.promise
  })
  await page.load()
  await page.load()
  assert.equal(page.rows.value.length, 0)
  assert.notEqual(page.error.value, '')
  const pending = page.load()
  page.dispose()
  late.resolve(result(1, [{ warningId: 'late' }]))
  await pending
  assert.equal(page.rows.value.length, 0)
})
