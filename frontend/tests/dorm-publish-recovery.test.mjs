import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'

const source = fs.readFileSync(new URL('../src/modules/studentAffairs/views/dorm/DormAllocationView.vue', import.meta.url), 'utf8')
function method(name, api) {
  const start = source.indexOf(`    async ${name}(`)
  const end = source.indexOf('\n    },', start)
  const body = source.slice(start, end + 6).trim().replace(`async ${name}(`, `async function ${name}(`)
  return new Function('studentAffairsApi', `return ${body}`)(api)
}
for (const state of ['PENDING', 'NONE', 'OFFLINE']) {
  test(`lost enqueue response reads ${state}, never submits twice`, async () => {
    let submits = 0
    const api = { async queueDormAllocationPublish(id, version) { assert.equal(id, '17'); assert.equal(version, 4); submits++; throw Error('连接中断') } }
    const vm = { actioning: false, publishReady: true, deskActive: true, selectedId: '17', detail: { batch: { version: 4 } }, publishConfirm: { visible: true },
      unwrap(r) { return r.data }, async refreshPublishJob(id) { assert.equal(id, '17'); this.publishJob = state === 'PENDING' ? { status: state, version: 4 } : null } }
    await method('confirmPublishBatch', api).call(vm)
    assert.equal(submits, 1); assert.equal(vm.actioning, false)
    assert.equal(vm.publishConfirm.visible, state !== 'PENDING')
    if (state !== 'PENDING') assert.match(vm.errorMessage, /刷新/)
  })
}
test('job response from a former page does not replace current plan', async () => {
  let resolve
  const api = { getDormAllocationPublishJob: () => new Promise(r => { resolve = r }) }
  const vm = { selectedId: '17', jobRequest: 0, deskActive: true, unwrap: r => r.data }
  const pending = method('refreshPublishJob', api).call(vm, '17')
  vm.selectedId = '18'; vm.jobRequest++
  resolve({ data: { status: 'SUCCESS' } }); await pending
  assert.equal(vm.publishJob, undefined)
})
