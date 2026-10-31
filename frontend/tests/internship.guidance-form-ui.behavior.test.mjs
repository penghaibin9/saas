import { componentFactory } from './internship-test-dependencies.mjs'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'
import { parse, compileTemplate } from '@vue/compiler-sfc'
const filename = new URL('../src/modules/internship/views/GuidanceRecordFormView.vue', import.meta.url)
const { descriptor } = parse(fs.readFileSync(filename, 'utf8'))
const script = descriptor.script.content.replace(/^import[\s\S]*?from ['"][^'"]+['"]\r?\n/gm, '')
  .replace(/ {2}components: \{[\s\S]*?AppTemplateChips \},/, '').replace('export default', 'return')
function setup(api) {
  const targets = []
  let saved = false
  const def = componentFactory('guidanceVisitApi', 'VISIT_STATUS', 'VISIT_GUIDANCE', 'VISIT_ISSUE', 'toast', 'window', script)(api, [], [], [], { success() {} }, { __SAAS_DIRTY_FORM_GUARD__: { markSaved() { saved = true } } })
  const vm = { ...def.data(), batchStore: { selectedBatchId: '1', withBatchQuery: q => ({ ...q, batchId: '1' }) },
    $route: { query: { type: 'guidance', batchId: '1' } }, $router: { push: t => targets.push(t), options: { history: { state: {} } } } }
  for (const [name, fn] of Object.entries(def.methods)) vm[name] = fn.bind(vm)
  return { vm, def, targets, saved: () => saved }
}
test('guidance form template compiles', () => {
  assert.deepEqual(compileTemplate({ source: descriptor.template.content, filename: String(filename), id: 'guidance-form' }).errors, [])
})
test('upload completion from a previous batch cannot attach a file to a new draft', async () => {
  let finish
  const { vm, def } = setup({ uploadAttachment: () => new Promise(resolve => { finish = resolve }) })
  vm.type='visit'; vm.$route.query.type='visit'
  const old = vm.onFilePick({ target: { files: [{ name: '材料.pdf' }], value: 'file' } })
  def.watch['batchStore.selectedBatchId'].call(vm)
  finish({ code: 0, data: { fileId: '8' } }); await old
  assert.equal(vm.form.fileId, ''); assert.equal(vm.uploadingFile, false)
})
test('uploading blocks save; failed save preserves draft and does not mark it saved', async () => {
  let calls = 0
  const state = setup({ createGuidancesBatch: async () => { calls++; return { code: 1, message: '暂时无法保存' } } })
  const vm = state.vm
  vm.form.internshipIds = ['9007199254740999']; vm.form.guidanceDate='2026-10-29'; vm.form.content = '继续跟进岗位适应'
  vm.uploadingFile = true; await vm.doSubmit(); assert.equal(calls, 0)
  vm.uploadingFile = false; await vm.doSubmit()
  assert.equal(vm.form.content, '继续跟进岗位适应'); assert.equal(vm.submitError, '暂时无法保存')
  assert.equal(state.saved(), false); assert.equal(state.targets.length, 0)
})
test('successful guidance save retains its student receipt and opens that exact record', async () => {
  const state = setup({ createGuidancesBatch: async body => ({ code: 0, data: { batchId:body.batchId,items:body.items.map(item=>({...item,id:'9007199254740999',success:true})) } }) })
  state.vm.form.internshipIds = ['8']; state.vm.form.guidanceDate='2026-10-29'; state.vm.form.content = '跟进岗位适应'
  await state.vm.doSubmit()
  assert.equal(state.saved(), true)
  assert.equal(state.vm.guidanceResults[0].id, '9007199254740999'); state.vm.viewGuidance(state.vm.guidanceResults[0])
  assert.deepEqual(state.targets[0].query, { batchId: '1', panel: 'guidance', id: '9007199254740999' })
})
test('direct-link return preserves batch context', () => {
  const state = setup({}); state.vm.backToList()
  assert.deepEqual(JSON.parse(JSON.stringify(state.targets[0].query)), { panel: 'guidance', batchId: '1' })
})
