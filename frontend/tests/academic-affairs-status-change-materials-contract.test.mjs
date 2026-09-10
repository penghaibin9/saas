import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'
import { CHANGE_FLOW_NODES, NODE_LABEL, TYPE_LABEL, TYPE_PATH_SEGMENT } from '../src/modules/academicAffairs/constants/status-change.js'
import { ACADEMIC_STUDENT_STATUS_LABELS } from '../src/modules/academicAffairs/config/academicStudentLabels.js'
import { gradeError } from '../src/modules/academicAffairs/views/parallel-c/grade-review.js'

const apiUrl = new URL(
  '../src/modules/academicAffairs/api/status-change-convenience.api.js',
  import.meta.url
)
const formUrl = new URL(
  '../src/modules/academicAffairs/views/AaStatusChangeFormView.vue',
  import.meta.url
)
const detailUrl = new URL(
  '../src/modules/academicAffairs/views/AaStatusChangeDetailView.vue',
  import.meta.url
)
const uploaderUrl = new URL('../src/components/file/FileUploader.vue', import.meta.url)

async function detail(api, files, materialsApi, document) {
  const source = await readFile(detailUrl, 'utf8')
  const script = source.match(/<script>([\s\S]*?)<\/script>/)[1].replace(/^import .*$/gm, '')
    .replace(/components\s*:\s*\{[^}]*\},?/, '').replace('export default', 'return')
  const deps = { api, fileSdk: files, statusChangeConvenienceApi: materialsApi, document,
    CHANGE_FLOW_NODES, NODE_LABEL, gradeError, currentUserFromToken: () => ({}) }
  const component = new Function(...Object.keys(deps), script)(...Object.values(deps))
  const state = { ...component.data(), ctx: { currentRole: {}, dataScope: {}, permissionPatterns: ['*'] },
    $route: { params: { id: '1000000000000063661' } } }
  for (const [name, method] of Object.entries(component.methods)) state[name] = method.bind(state)
  for (const [name, getter] of Object.entries(component.computed)) Object.defineProperty(state, name, { get: () => getter.call(state) })
  return state
}

async function formState() {
  const source = await readFile(formUrl, 'utf8')
  const script = source.match(/<script>([\s\S]*?)<\/script>/)[1].replace(/^import .*$/gm, '')
    .replace(/components\s*:\s*\{[^}]*\},?/, '').replace('export default', 'return')
  const deps = {
    TYPE_LABEL, TYPE_PATH_SEGMENT, ACADEMIC_STUDENT_STATUS_LABELS,
    currentUserFromToken: () => ({ userId: 'teacher-a' }), matchPermission: () => true,
    gradeError, rememberStatusChangeRecovery() {}, getStatusChangeRecovery() { return null }, clearStatusChangeRecovery() {},
    insertAtCursor() {}, applyInsertion() {}, hasGroupPhrases: () => false
  }
  const component = new Function(...Object.keys(deps), script)(...Object.values(deps))
  const state = { $route: { query: {} }, ctx: { currentRole: {}, dataScope: {}, permissionPatterns: ['*'] } }
  Object.assign(state, component.data.call(state), component.methods)
  for (const [name, getter] of Object.entries(component.computed)) Object.defineProperty(state, name, { get: () => getter.call(state) })
  return state
}

test('D3-U material API keeps one convenience submit and formal list/add routes', async () => {
  const source = await readFile(apiUrl, 'utf8')

  assert.match(source, /async submit\(body\)/)
  assert.match(source, /\$\{BASE\}\/convenience-submit/)
  assert.match(source, /async listMaterials\(changeId\)/)
  assert.match(source, /\$\{BASE\}\/\$\{encodeURIComponent\(changeId\)\}\/materials/)
  assert.match(source, /async addMaterials\(changeId, materialFileIds\)/)
  assert.match(source, /method: 'POST'/)
  assert.match(source, /body: \{ materialFileIds \}/)
})

test('D3-U form blocks active upload and unsafe scan before its single submit', async () => {
  const source = await readFile(formUrl, 'utf8')

  assert.match(source, /import FileUploader from '@\/components\/file\/FileUploader\.vue'/)
  assert.match(source, /import \{ fileSdk \} from '@\/services\/file\/fileSdk'/)
  assert.match(source, /materialFiles\.length >= 10/)
  assert.match(source, /@progress="onMaterialProgress"/)
  assert.match(source, /@cancelled="onMaterialUploadCancelled"/)
  assert.match(source, /materialUploadBusy/)
  assert.match(source, /hasPendingMaterial/)
  assert.match(source, /fileSdk\.metadata\(fileId\)/)
  assert.match(source, /materialFileIds: this\.materialFiles\.map/)
  assert.match(source, /body:this\.buildBody\(\)/)
  assert.match(source, /form:\{\.\.\.this\.form\}/)
  assert.match(source, /statusChangeConvenienceApi\.submit\(c\.body\)/)
  assert.doesNotMatch(source, /academicAffairsApi\.submitStatusChange\(/)
})

test('D3-U confirmation snapshots the exact student facts and scanned materials used by the single submit', async () => {
  const state = await formState()
  Object.assign(state.form, { studentId: '1001', name: '测试学生', studentVersion: 3, changeType: 'SUSPEND', reason: '因病申请休学', effectiveMode: 'IMMEDIATE', currentStatus: 'REGISTERED', currentCollegeId: '10', studentMajorId: '20', currentClassId: '30' })
  state.factsReady = true
  state.materialFiles = [{ fileId: '9007199254740993', readyForBusiness: true }]
  state.askSubmit()
  const command = state.command
  assert.equal(state.confirmVisible, true)
  state.form.reason = '被修改的说明'
  state.materialFiles[0].fileId = '9007199254740994'
  assert.equal(command.body.reason, '因病申请休学')
  assert.deepEqual([...command.body.materialFileIds], ['9007199254740993'])
  assert.equal(command.form.currentStatus, 'REGISTERED')
})

test('FileUploader emits progress=0 immediately when a real upload starts', async () => {
  const source = await readFile(uploaderUrl, 'utf8')
  const uploadingIndex = source.indexOf('uploading.value = true')
  const zeroIndex = source.indexOf("emit('progress', 0)")
  const sdkIndex = source.indexOf('activeTask = fileSdk.upload')

  assert.ok(uploadingIndex >= 0)
  assert.ok(zeroIndex > uploadingIndex)
  assert.ok(sdkIndex > zeroIndex)
})

test('D3-U detail lazily enumerates only formal bound materials and checks allowed actions before opening', async () => {
  const calls = [], normalized = []
  const file = { fileId: '1000000000000063681', fileName: '正式材料.pdf' }
  const state = await detail({ getStatusChange: async id => ({ code: 0, data: { changeId: id,
    attachmentFileIds: ['legacy-unbound-file'] } }) }, {
    normalize(value) { normalized.push(value.fileId); return { ...value } },
    metadata: async id => { calls.push(['metadata', id]); return { allowedActions: [] } },
    authorizedUrl: async () => { throw new Error('A denied file must never request a URL') }
  }, { listMaterials: async id => { calls.push(['materials', id]); return { code: 0, data: { items: [file] } } } })

  await state.load()
  assert.equal(calls.length, 0)
  assert.equal(state.materials.length, 0)
  await state.loadMaterials()
  assert.deepEqual(calls, [['materials', '1000000000000063661']])
  assert.deepEqual(normalized, [file.fileId])
  assert.deepEqual(state.materials.map(value => value.fileId), [file.fileId])
  await state.openFile({ fileId: 'legacy-unbound-file' }, 'preview')
  assert.equal(calls.length, 1)
  await state.openFile(state.materials[0], 'preview')
  assert.deepEqual(calls[1], ['metadata', file.fileId])
  assert.equal(state.change, null)
  assert.equal(state.materials.length, 0)
})

test('D3-U a late authorized material URL cannot open after the original application changes', async () => {
  let reply, opens = 0
  const response = new Promise(resolve => { reply = resolve })
  const file = { fileId: '1000000000000063681', fileName: '正式材料.pdf' }
  const state = await detail({}, {
    metadata: async () => ({ allowedActions: ['preview'] }), authorizedUrl: () => response
  }, {}, { createElement() { opens++; throw new Error('A stale file must never open') } })
  state.change = { changeId: state.changeId }; state.materials = [file]
  const pending = state.openFile(file, 'preview')
  await Promise.resolve()
  state.$route.params.id = '1000000000000063662'; state.clear()
  reply({ delivery: 'COS_PRESIGNED', url: 'https://example.invalid/private.pdf' })
  await pending
  assert.equal(opens, 0)
  assert.equal(state.materials.length, 0)
})
