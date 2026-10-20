import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'

function loadComponent(realRequest, getTeacherGraduationBatch = () => ({ id: 'batch-1' })) {
  const source = fs.readFileSync(new URL('../src/pages/teacher/components/MobileGraduationDelayQueue.vue', import.meta.url), 'utf8')
  const script = source.match(/<script>([\s\S]*?)<\/script>/)[1]
    .replace(/^import[^\n]+\n/gm, '')
    .replace('export default', 'return')
  return new Function('realRequest', 'normalizeError', 'getTeacherGraduationBatch', 'uni', 'getCurrentPages', script)(
    realRequest, error => ({ text: error.message || '加载失败' }), getTeacherGraduationBatch,
    { showToast() {}, showModal() {} }, () => [])
}

async function flush() {
  await Promise.resolve()
  await Promise.resolve()
  await Promise.resolve()
}

test('teacher graduation delay queue requests bounded pages and retains already loaded rows on page two', async () => {
  const requests = []
  const component = loadComponent(async (path) => {
    requests.push(path)
    if (path.includes('page=1')) return { items: [{ id: 'delay-1' }], page: 1, total: 21, hasMore: true }
    return { items: [{ id: 'delay-2' }], page: 2, total: 21, hasMore: false }
  })
  const vm = { ...component.data() }
  for (const [name, method] of Object.entries(component.methods)) vm[name] = (...args) => method.apply(vm, args)

  vm.load()
  await flush()
  assert.equal(requests[0], '/mobile/teacher/graduation/defense-delays/pending?page=1&pageSize=20')
  assert.deepEqual(vm.rows.map((row) => row.id), ['delay-1'])
  assert.equal(vm.hasMore, true)

  vm.loadMore()
  await flush()
  assert.equal(requests[1], '/mobile/teacher/graduation/defense-delays/pending?page=2&pageSize=20')
  assert.deepEqual(vm.rows.map((row) => row.id), ['delay-1', 'delay-2'])
  assert.equal(vm.hasMore, false)
})

test('changing the teacher graduation batch discards stale rows and unlocks the next request', () => {
  let batch = { id: 'batch-2' }
  const component = loadComponent(() => new Promise(() => {}), () => batch)
  const vm = { ...component.data(), lastBatchId: 'batch-1', rows: [{ id: 'old-delay' }], loading: true, loadingMore: true }
  for (const [name, method] of Object.entries(component.methods)) vm[name] = (...args) => method.apply(vm, args)

  vm.syncBatch()
  assert.deepEqual(vm.rows, [])
  assert.equal(vm.lastBatchId, 'batch-2')
  assert.equal(vm.loading, true, 'new batch request starts after stale request is invalidated')
  assert.equal(vm.loadingMore, false)
  batch = null
  vm.syncBatch()
  assert.equal(vm.loading, false)
  assert.equal(vm.loadingMore, false)
  assert.equal(vm.hasMore, false)
})
