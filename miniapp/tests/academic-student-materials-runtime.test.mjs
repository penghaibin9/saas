import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'
import test from 'node:test'

function mount(fileSdk) {
  const session = { generation: 1 }, events = []
  const context = vm.createContext({ fileSdk, currentSessionGeneration: () => session.generation })
  const source = readFileSync(new URL('../src/pages/student/academic-affairs/AcademicMaterials.vue', import.meta.url), 'utf8')
    .match(/<script>([\s\S]*?)<\/script>/)[1].replace(/^import .*$/gm, '').replace('export default', 'component =')
  vm.runInContext(source, context)
  const page = { ...context.component.data(), files: [], purpose: 'AA_RECOGNITION', disabled: false, $emit: (name, value) => events.push([name, value]) }
  for (const [name, fn] of Object.entries(context.component.methods)) page[name] = fn.bind(page)
  return { page, events, session, unmount: () => context.component.beforeUnmount.call(page) }
}

test('material selection returning after page leaves never starts upload', async () => {
  let resolve, uploads = 0
  const { page, unmount } = mount({ choose: () => new Promise(done => { resolve = done }), upload: async () => { uploads++ } })
  const pending = page.add(); unmount(); resolve({ size: 10 }); await pending
  assert.equal(uploads, 0)
})

test('material upload is locked while in flight and an old identity cannot receive it', async () => {
  let resolve, uploads = 0
  const { page, session, events } = mount({ choose: async () => ({ size: 10 }), upload: () => { uploads++; return new Promise(done => { resolve = done }) } })
  const pending = page.add(); await Promise.resolve(); await page.add()
  assert.equal(uploads, 1)
  session.generation++; resolve({ fileId: 'old', readyForBusiness: true }); await pending
  assert.equal(events.filter(([name]) => name === 'update:files').length, 0)
})

test('file metadata is rechecked explicitly; size policy stays on the formal upload service', async () => {
  let uploads = 0, reads = 0
  const { page, events } = mount({ choose: async () => ({ size: 11 * 1024 * 1024 }), upload: async () => { uploads++; return { fileId: '40', readyForBusiness: false } }, metadata: async fileId => { reads++; return { fileId, readyForBusiness: true } } })
  await page.add(); assert.equal(uploads, 1)
  page.files = [{ fileId: '41', readyForBusiness: false }]
  await page.refresh(); assert.equal(reads, 1)
  assert.equal(events.filter(([name]) => name === 'update:files').at(-1)[1][0].readyForBusiness, true)
})
