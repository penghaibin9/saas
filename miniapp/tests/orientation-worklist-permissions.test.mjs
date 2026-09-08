import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'

const source = fs.readFileSync(new URL('../src/pages/teacher/orientation/worklist/index.vue', import.meta.url), 'utf8')
const script = source.match(/<script>([\s\S]*?)<\/script>/)[1]
  .replace(/^import .*$/gm, '').replace('export default', 'return')

function setup(context) {
  const requests = []
  const page = new Function('realRequest', 'toast', 'FilePreviewer', script)(async (url) => {
    requests.push(url)
    if (context instanceof Error) throw context
    return context
  }, () => {}, {})
  const vm = { ...page.data(), ...page.methods }
  return { vm, requests }
}

test('orientation writes require current management permission and a writable healthy tenant', async () => {
  for (const context of [
    { permissionPatterns: ['studentAffairs.orientation.view'] },
    { permissionPatterns: ['*'], readonlyTenant: true },
    { permissionPatterns: ['*'], moduleAccessHealthy: false },
    new Error('offline'),
  ]) {
    const { vm, requests } = setup(context)
    vm.canManage = true
    await vm.loadPermissions()
    assert.equal(vm.canManage, false)
    vm.detail = { student: { version: 1 } }
    await vm.perform('verify')
    assert.deepEqual(requests, ['/rbac/current-context'])
  }
})

test('orientation manager and matching wildcard permissions enable the same worklist', async () => {
  for (const pattern of ['studentAffairs.orientation.manage', 'studentAffairs.orientation.*', 'studentAffairs.*', '*']) {
    const { vm } = setup({ permissionPatterns: [pattern] })
    await vm.loadPermissions()
    assert.equal(vm.canManage, true)
  }
})

test('orientation worklist loads the exact student materials and keeps review on the same sheet', () => {
  assert.match(source, /orientationStudentId: row\.id/)
  assert.match(source, /<FilePreviewer/)
  assert.match(source, /reviewMaterial\(material, 'return'\)/)
  assert.match(source, /reviewMaterial\(material, 'approve'\)/)
  assert.match(source, /reason\.length < 5/)
})
