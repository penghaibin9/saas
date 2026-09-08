import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import { parse } from '@vue/compiler-sfc'

const source = parse(fs.readFileSync(new URL('../src/views/internship/InternshipVolunteerResultView.vue', import.meta.url), 'utf8')).descriptor.scriptSetup.content.replace(/^import[^\n]+\n/gm, '')
const deferred = () => { let resolve; const promise = new Promise(r => { resolve = r }); return { promise, resolve } }
function fixture(request, query = { groupId: '1', groupVersion: '2' }) {
  let dispose
  const route = { query }
  const deps = { ref: value => ({ value }), computed: getter => ({ get value() { return getter() } }),
    watch() {}, onBeforeUnmount: fn => { dispose = fn }, useRoute: () => route, useRouter: () => ({ push() {} }),
    internshipSelectionApi: { volunteerResult: request } }
  const page = new Function(...Object.keys(deps), source + '\nreturn {load,result,error,loading,updatedSinceMessage}')(...Object.values(deps))
  return { page, route, dispose: () => dispose() }
}
test('result is pinned to original group and marks an older message', async () => {
  const calls = []
  const { page } = fixture(async id => { calls.push(id); return { id, version: 4, items: [] } })
  await page.load()
  assert.deepEqual(calls, ['1'])
  assert.equal(page.result.value.id, '1')
  assert.equal(page.updatedSinceMessage.value, true)
})
test('invalid or repeated group query never requests a guessed record', async () => {
  for (const groupId of ['', '0', '-1', ['1', '2']]) {
    const { page } = fixture(() => { assert.fail('must not request') }, { groupId })
    await page.load(); assert.match(page.error.value, /编号/)
  }
})
test('late response cannot overwrite a different group or disposed page', async () => {
  const first = deferred()
  const { page, route, dispose } = fixture(id => id === '1' ? first.promise : Promise.resolve({ id, version: 1 }))
  const old = page.load()
  route.query.groupId = '2'; await page.load()
  first.resolve({ id: '1', version: 2 }); await old
  assert.equal(page.result.value.id, '2')
  dispose(); await page.load(); assert.equal(page.result.value, null)
})
test('mismatched authority response fails closed and retry can recover', async () => {
  let id = '2'
  const { page } = fixture(async () => ({ id, version: 2 }))
  await page.load(); assert.equal(page.result.value, null); assert.match(page.error.value, /不一致/)
  id = '1'; await page.load(); assert.equal(page.error.value, ''); assert.equal(page.updatedSinceMessage.value, false)
})
