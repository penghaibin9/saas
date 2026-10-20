import assert from 'node:assert/strict'
import { createHash } from 'node:crypto'
import fs from 'node:fs'
import test from 'node:test'
import vm from 'node:vm'

const source = fs.readFileSync(new URL('../src/modules/graduation/views/_shared/GraduationBatchStrip.vue', import.meta.url), 'utf8').replace(/\r\n/g, '\n')
const business = source.split('<style scoped>')[0]
const style = source.match(/<style scoped>([\s\S]*?)<\/style>/)?.[1] || ''
const block = selector => style.slice(style.indexOf(`${selector} {`)).split('}')[0]

function loadStrip() {
  const calls = { select: [], replace: [], load: [] }
  const store = {
    availableBatches: [], batchStatus: '',
    selectBatch: id => calls.select.push(id),
    ensureLoaded: options => { calls.load.push(options); return Promise.resolve() }
  }
  const script = source.match(/<script>([\s\S]*?)<\/script>/)[1]
  const options = vm.runInNewContext(
    script.replace(/^import .+\n/gm, '').replace('export default', 'globalThis.options ='),
    { StatusTag: {}, useGraduationBatchStore: () => store }, { timeout: 1000 }
  )
  const target = {
    ...options.setup(), $route: { query: {} },
    $router: { replace: async value => { calls.replace.push(JSON.parse(JSON.stringify(value))) } }
  }
  return { options, target, calls }
}

test('UI-only batch repair freezes the template and script at the audited parent', () => {
  // eb2dd76: visual adaptation must not rewrite batch selection, loading or branch conditions.
  assert.equal(createHash('sha256').update(business).digest('hex'),
    '93beef0f20c0c0a0a7cd3fc54fb2e1152e0efbdb02dde93abe50226b7eb90cfc')
})

test('batch field consumes shared theme tokens instead of forcing white', () => {
  assert.match(block('.gbs__select'), /background:\s*var\(--field-bg,\s*var\(--bg-card,\s*#fff\)\)/)
  assert.match(block('.gbs__select'), /color:\s*var\(--text-primary/)
  assert.match(block('.gbs'), /background:\s*var\(--bg-subtle/)
  assert.doesNotMatch(style, /(?:^|\n)\s*(?::root|body|\.tw-|\.bpl-)/)
  assert.doesNotMatch(style, /display:\s*none|visibility:\s*hidden|!important/)
})

test('batch states wrap long text rather than hiding the error or retry action', () => {
  assert.match(block('.gbs'), /min-width:\s*0/)
  assert.match(block('.gbs'), /max-width:\s*100%/)
  assert.match(block('.gbs__text'), /overflow-wrap:\s*anywhere/)
  assert.match(block('.gbs__text'), /min-width:\s*0/)
  assert.match(block('.gbs__meta'), /overflow-wrap:\s*anywhere/)
})

test('batch controls retain readable text, click targets and visible keyboard focus', () => {
  for (const selector of ['.gbs__select', '.mp-link']) {
    assert.match(block(selector), /min-height:\s*34px/)
    assert.match(block(selector), /font-size:\s*13px/)
  }
  assert.match(style, /\.gbs__select:focus-visible,[\s\S]*\.mp-link:focus-visible\s*\{[\s\S]*outline:\s*2px solid var\(--pri/)
})

test('selecting a batch preserves the existing URL context without mutating the input query', async () => {
  const { options, target, calls } = loadStrip()
  const query = Object.freeze({ batchId: '71', panel: 'archive', page: '2', studentId: '9', keyword: 'A+B' })
  target.$route.query = query
  options.methods.onSelect.call(target, '82')
  await Promise.resolve()
  assert.deepEqual(calls.select, ['82'])
  assert.deepEqual(calls.replace, [{ query: { ...query, batchId: '82' } }])
  assert.equal(query.batchId, '71')
})

test('clearing the selection removes only batchId', async () => {
  const { options, target, calls } = loadStrip()
  target.$route.query = { batchId: '71', tab: 'PENDING_REVIEW', selected: '9' }
  options.methods.onSelect.call(target, '')
  await Promise.resolve()
  assert.deepEqual(calls.select, [''])
  assert.deepEqual(calls.replace, [{ query: { tab: 'PENDING_REVIEW', selected: '9' } }])
})

test('retry still reloads the real batch store using the explicit URL batch', () => {
  const { options, target, calls } = loadStrip()
  target.$route.query = { batchId: '82', panel: 'risk' }
  options.methods.reload.call(target)
  assert.deepEqual(JSON.parse(JSON.stringify(calls.load)), [{ batchIdFromUrl: '82', force: true }])
  assert.deepEqual(calls.replace, [])
})

test('batch counts and labels remain derived from the store', () => {
  const { options, target } = loadStrip()
  target.store.availableBatches = [{ status: 'RUNNING' }, { status: 'DRAFT' }, { status: 'RUNNING' }]
  assert.equal(options.computed.runningCount.call(target), 2)
  for (const [status, label] of [['DRAFT', '草稿'], ['RUNNING', '进行中'], ['CLOSED', '已关闭'], ['ARCHIVED', '已归档'], ['CUSTOM', 'CUSTOM'], ['', '—']]) {
    target.store.batchStatus = status
    assert.equal(options.computed.statusLabel.call(target), label)
  }
})
