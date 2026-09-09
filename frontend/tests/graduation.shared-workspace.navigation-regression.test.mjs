import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'
import vm from 'node:vm'
import { setImmediate as flushTasks } from 'node:timers/promises'

const source = fs.readFileSync(new URL('../src/modules/graduation/views/AdminGraduationLayout.vue', import.meta.url), 'utf8')
const script = source.match(/<script>([\s\S]*?)<\/script>/)?.[1]
assert.ok(script)

// Execute the production methods, replacing only imported services and router IO.
function layout({ path = '/admin/graduation', query = {}, batchId = '71', loading = Promise.resolve() } = {}) {
  const pushes = [], replaces = []
  const store = { selectedBatchId: batchId, initialized: true, ensureLoaded: () => loading }
  const options = vm.runInNewContext(
    script.replace(/^import .+\n/gm, '').replace('export default', 'globalThis.options ='),
    {
      URLSearchParams,
      BasePortalLayout: {}, LoadingState: {}, EmptyState: {}, AppInlineAlert: {},
      GraduationBatchStrip: {}, GraduationExtensionAdminPanel: {}, graduationPickerAdapters: {},
      useGraduationBatchStore: () => store,
      router: {
        push: async value => { pushes.push(value) },
        replace: async value => { replaces.push(value) }
      }
    },
    { timeout: 1000 }
  )
  const page = { $route: { path, query, fullPath: path + (Object.keys(query).length ? `?${new URLSearchParams(query)}` : '') } }
  for (const [name, method] of Object.entries(options.methods)) page[name] = method.bind(page)
  return { page, options, store, pushes, replaces }
}

const plain = value => JSON.parse(JSON.stringify(value))

test('legacy menu event and workspace navigation produce the same batch-aware destination', () => {
  const { page, pushes } = layout()
  const path = '/admin/graduation/finals?tab=PENDING_REVIEW&page=2&keyword=A%2BB#file-v3'
  page.onMenuSelect({ path })
  assert.equal(pushes[0], page.resolveWorkspaceDestination(path))
  const target = new URL(pushes[0], 'https://test.invalid')
  assert.equal(target.searchParams.get('batchId'), '71')
  assert.equal(target.hash, '#file-v3')
  assert.equal(target.searchParams.get('keyword'), 'A+B')
})

test('legacy menu callbacks never add Graduation batch to another center', () => {
  const { page, pushes } = layout()
  const paths = ['/admin/student-affairs', '/admin/internship', '/admin/internship?batchId=88', '/admin/academic-affairs', '/workbench']
  for (const path of paths) page.onMenuSelect({ path })
  assert.deepEqual(pushes, paths)
})

test('legacy menu callbacks preserve encoded explicit batch keys rather than duplicating them', () => {
  const { page, pushes } = layout()
  for (const path of ['/admin/graduation?%62atchId=99', '/admin/graduation?batchId=', '/admin/graduation?batchId=99&batchId=98']) {
    page.onMenuSelect({ path })
    assert.equal(pushes.at(-1), path)
  }
})

test('same resolved full URL is not pushed again; hash-only changes remain navigable', () => {
  const { page, pushes } = layout()
  page.$route.fullPath = '/admin/graduation?batchId=71#today'
  page.onMenuSelect({ path: '/admin/graduation#today' })
  assert.equal(pushes.length, 0)
  page.onMenuSelect({ path: '/admin/graduation#progress' })
  assert.deepEqual(pushes, ['/admin/graduation?batchId=71#progress'])
})

test('empty legacy menu events do not navigate', () => {
  const { page, pushes } = layout()
  for (const item of [null, undefined, {}, { path: '' }]) page.onMenuSelect(item)
  assert.equal(pushes.length, 0)
})

test('batch URL synchronization cannot mutate another module after leaving Graduation', async () => {
  for (const path of ['/admin/internship', '/admin/student-affairs', '/workbench', '/admin/graduation-other']) {
    const { page, replaces } = layout({ path, query: { panel: 'list', batchId: '88' } })
    await page.syncBatchToUrl()
    assert.equal(replaces.length, 0, path)
  }
})

test('same-module synchronization retains the established batch repair contract', async () => {
  const { page, replaces } = layout({ path: '/admin/graduation/finals', query: { tab: 'PENDING_REVIEW', page: '2' } })
  await page.syncBatchToUrl()
  assert.deepEqual(plain(replaces), [{ query: { tab: 'PENDING_REVIEW', page: '2', batchId: '71' } }])
})

test('same batch or no selected batch does not generate redundant URL repairs', async () => {
  const current = layout({ query: { batchId: '71' } })
  await current.page.syncBatchToUrl()
  assert.equal(current.replaces.length, 0)
  const empty = layout({ batchId: '' })
  await empty.page.syncBatchToUrl()
  assert.equal(empty.replaces.length, 0)
})

test('a pending missing-batch repair cannot follow the user into a different center', async () => {
  let finish
  const loading = new Promise(resolve => { finish = resolve })
  const { page, options, replaces } = layout({ loading })
  options.watch['$route.query.batchId'].handler.call(page, undefined)
  page.$route = { path: '/admin/internship', fullPath: '/admin/internship?batchId=88', query: { batchId: '88' } }
  finish()
  await flushTasks()
  assert.equal(replaces.length, 0)
})

test('a delayed repair is discarded when a newer explicit Graduation link wins', async () => {
  let finish
  const loading = new Promise(resolve => { finish = resolve })
  const { page, options, replaces } = layout({ loading })
  options.watch['$route.query.batchId'].handler.call(page, undefined)
  page.$route = { path: '/admin/graduation/finals', fullPath: '/admin/graduation/finals?batchId=99', query: { batchId: '99' } }
  finish()
  await flushTasks()
  assert.equal(replaces.length, 0, 'old pending work must not rewrite a newer deep link')
})

test('the current missing-batch route is still repaired after loading completes', async () => {
  let finish
  const loading = new Promise(resolve => { finish = resolve })
  const { page, options, replaces } = layout({ loading })
  options.watch['$route.query.batchId'].handler.call(page, undefined)
  finish()
  await flushTasks()
  assert.deepEqual(plain(replaces), [{ query: { batchId: '71' } }])
})
