import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import { parse } from '@vue/compiler-sfc'

const source = parse(fs.readFileSync(new URL('../src/pages/student-internship/volunteer-result/index.vue', import.meta.url), 'utf8')).descriptor.script.content.replace(/^import[^\n]+\n/gm, '').replace('export default', 'return')
function fixture(request) {
  const options = new Function('internshipSelectionApi', source)({ volunteerResult: request })
  const page = options.data()
  for (const [key, fn] of Object.entries(options.methods)) page[key] = fn.bind(page)
  for (const [key, fn] of Object.entries(options.computed)) Object.defineProperty(page, key, { get: () => fn.call(page) })
  return { page, options }
}
test('mobile original group and old message state stay distinct', async () => {
  const calls = []
  const { page } = fixture(async id => { calls.push(id); return { id, version: 3, status: 'APPROVED', items: [] } })
  page.groupId = '17'; page.messageVersion = '2'; await page.load()
  assert.deepEqual(calls, ['17']); assert.equal(page.updatedSinceMessage, true)
  assert.equal(page.statusLabel, '学校已确认岗位'); assert.match(page.guidance, /上岗核验/)
})
test('missing or duplicate group parameter fails before request', async () => {
  for (const groupId of [undefined, '0', '-1', ['1','2']]) {
    const { page, options } = fixture(() => assert.fail('must not request'))
    options.onLoad.call(page, { groupId })
    assert.equal(page.state, 'error'); assert.equal(page.result, null)
  }
})
test('unload and retry prevent older result from becoming visible', async () => {
  let resolve
  const first = new Promise(r => { resolve = r })
  let count = 0
  const { page, options } = fixture(() => ++count === 1 ? first : Promise.resolve({ id: '1', version: 4 }))
  page.groupId = '1'; const old = page.load(); await page.load()
  resolve({ id: '1', version: 1 }); await old; assert.equal(page.result.version, 4)
  options.onUnload.call(page); await page.load(); assert.equal(page.result, null)
})
test('wrong object is never shown and valid retry recovers', async () => {
  let id = '2'; const { page } = fixture(async () => ({ id, version: 1 }))
  page.groupId = '1'; await page.load(); assert.equal(page.state, 'error'); assert.equal(page.result, null)
  id = '1'; await page.load(); assert.equal(page.state, 'ready'); assert.equal(page.error, '')
})
test('reused H5 route clears previous result when new group is denied', async () => {
  const { page, options } = fixture(async id => {
    if (id === '2') throw new Error('不属于本人')
    return { id, version: 1 }
  })
  await page.applyQuery({ groupId: '1' }); assert.equal(page.result.id, '1')
  page.$route = { path: '/pages/student-internship/volunteer-result/index', query: { groupId: '2' } }
  options.watch['$route.fullPath'].call(page)
  assert.equal(page.result, null)
  await new Promise(resolve => setImmediate(resolve))
  assert.equal(page.state, 'error'); assert.match(page.error, /不属于本人/)
})
