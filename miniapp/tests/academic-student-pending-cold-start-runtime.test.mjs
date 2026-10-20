import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'
import test from 'node:test'

const directory = new URL('../src/pages/student/academic-affairs/', import.meta.url)
const sessionKey = 'gx_session_v1'
const pendingKey = 'gx_academic_pending_commands_v1'

function setIdentity(storage, user = 'student-a') {
  storage.set(sessionKey, JSON.stringify({
    logged: true,
    currentRole: 'student',
    identity: {
      tenantId: 'tenant-1', userId: user, roleCode: 'STUDENT',
      activeContextId: user + '-context', studentId: user + '-student'
    }
  }))
}

function source(name) {
  return readFileSync(new URL(name, directory), 'utf8')
    .replace(/^import .*$/gm, '')
    .replace(/export (const|function) /g, '$1 ')
}

function runtime(storage, options = {}) {
  let generation = 1
  const uni = {
    getStorageSync: key => storage.get(key) || '',
    setStorageSync: (key, value) => {
      if (options.failPendingWrite && key === pendingKey) throw new Error('storage full')
      storage.set(key, value)
    },
    removeStorageSync: key => storage.delete(key)
  }
  const context = vm.createContext({
    uni,
    currentSessionGeneration: () => generation,
    modalConfirm: async () => ({ confirm: true }),
    isUncertainWriteError: () => false
  })
  for (const helper of ['pending-ledger.js', 'read-page.js', 'application-page.js']) vm.runInContext(source(helper), context)
  const api = vm.runInContext('({ canUpdatePendingCommand, createPendingCommand, readPending, redactPendingCommand, savePending, academicApplicationPage })', context)
  const page = { ...api.academicApplicationPage.data(), applicationScope: 'recognition', state: 'ready', readEpoch: 0, readHidden: false, readIdentity: generation, load: async () => {} }
  for (const [name, method] of Object.entries(api.academicApplicationPage.methods)) page[name] = method.bind(page)
  return { api, page, advanceGeneration: () => { generation += 1 } }
}

test('an unreadable existing ledger cannot be treated as an empty ledger and allow POST', async () => {
  const storage = new Map()
  setIdentity(storage)
  storage.set(pendingKey, JSON.stringify({ version: 99, owners: {} }))
  const run = runtime(storage)
  let writes = 0
  await run.page.sendApplication({ title: '提交申请', body: {}, rows: [], idKey: 'recognitionId', send: async () => { writes += 1 } })
  assert.equal(writes, 0)
  assert.match(run.page.applicationNotice, /未发送申请/)
  assert.equal(JSON.parse(storage.get(pendingKey)).version, 99)
})

test('403 redaction keeps the original blocker and removes private memory even if storage fails', () => {
  const storage = new Map(), options = {}
  setIdentity(storage)
  const run = runtime(storage, options)
  const original = run.api.createPendingCommand('recognition', { idKey: 'recognitionId', body: { reason: '私密原因', materials: ['私密文件'] }, returnedId: '55' })
  assert.equal(run.api.savePending('recognition', original), true)
  run.page.pendingApplication = original
  options.failPendingWrite = true
  assert.equal(run.page.protectPendingReference(), true)
  assert.equal(run.page.pendingApplication.returnedId, '55')
  assert.equal(run.page.pendingApplication.recoveryOnly, true)
  assert.doesNotMatch(JSON.stringify(run.page.pendingApplication), /私密/)
  assert.doesNotMatch(JSON.stringify(run.api.readPending('recognition')), /私密/)
})

test('cold receipt identity and boolean proof remain exact', () => {
  const storage = new Map()
  setIdentity(storage)
  const run = runtime(storage)
  run.page.applicationScope = 'registration'
  run.page.finishApplication = () => {}
  const original = run.api.createPendingCommand('registration', { existingId: '901', recordKey: 'batchId', receiptKey: 'registrationId', returnedId: '901', recovery: { field: 'registrationStatus', equals: 'REGISTERED' } })
  assert.equal(run.api.savePending('registration', original), true)
  run.page.pendingApplication = run.api.redactPendingCommand('registration', original)
  run.page.acceptApplication([{ batchId: '901', registrationId: '902', registrationStatus: 'REGISTERED' }], 'registrationId', () => true)
  assert.ok(run.page.pendingApplication)
  run.page.acceptApplication([{ batchId: '901', registrationId: '901', registrationStatus: 'REGISTERED' }], 'registrationId', () => true)
  assert.equal(run.page.pendingApplication, null)

  run.page.applicationScope = 'evaluation'
  const evaluation = run.api.createPendingCommand('evaluation', { existingId: '71', recordKey: 'taskId', receiptKey: 'taskId', returnedId: '71', recovery: { field: 'submitted', equals: true } })
  assert.equal(run.api.savePending('evaluation', evaluation), true)
  run.page.pendingApplication = run.api.redactPendingCommand('evaluation', evaluation)
  run.page.acceptApplication([{ taskId: '71', submitted: 'true' }], 'taskId', () => true)
  assert.ok(run.page.pendingApplication)
  run.page.acceptApplication([{ taskId: '71', submitted: true }], 'taskId', () => true)
  assert.equal(run.page.pendingApplication, null)
})

test('cold start keeps only a minimal command reference for the same real student identity', async () => {
  const storage = new Map()
  setIdentity(storage)
  const first = runtime(storage)
  const command = first.api.createPendingCommand('recognition', {
    action: 'RECOGNITION_SUBMIT', title: '私密成绩认定标题',
    body: { sourceCourseName: '私密原课程', reason: '私密申请理由', attachmentFileIds: ['机密材料.pdf'] },
    existingId: '', idKey: 'recognitionId', recordKey: 'recognitionId', receiptKey: 'recognitionId', returnedId: 'recognition-9'
  })
  assert.ok(command)
  assert.equal(first.api.savePending('recognition', command), true)
  const selection = first.api.createPendingCommand('selection', {
    operation: 'ENROLL', selectionCourseId: 'course-9', selectionRecordId: '', batchId: 'batch-9',
    returnedId: 'record-9', courseName: '不应落盘的课程名称'
  })
  const major = first.api.createPendingCommand('major-split', {
    batchId: 'batch-major', choices: ['major-1', 'major-2'], volunteerId: '', title: '不应落盘的志愿标题'
  })
  assert.equal(first.api.savePending('selection', { 'batch-9:course-9': selection }), true)
  assert.equal(first.api.savePending('major-split', { 'batch-major': major }), true)
  const raw = storage.get(pendingKey)
  assert.doesNotMatch(raw, /私密成绩认定标题|私密原课程|私密申请理由|机密材料\.pdf|attachmentFileIds|不应落盘的课程名称|不应落盘的志愿标题/)

  const restarted = runtime(storage)
  const cold = restarted.api.readPending('recognition')
  assert.deepEqual(JSON.parse(JSON.stringify(cold)), {
    commandId: command.commandId, action: 'RECOGNITION_SUBMIT', kind: '', recordKey: 'recognitionId', receiptKey: 'recognitionId',
    objectId: '', returnedId: 'recognition-9', recovery: null, recoveryOnly: true, _pendingOwner: cold._pendingOwner
  })
  const coldSelection = restarted.api.readPending('selection')['batch-9:course-9']
  assert.equal(coldSelection.returnedId, 'record-9')
  assert.equal(coldSelection.courseName, undefined)
  assert.equal(coldSelection.recoveryOnly, true)
  const coldMajor = restarted.api.readPending('major-split')['batch-major']
  assert.deepEqual(Array.from(coldMajor.choices), ['major-1', 'major-2'])
  assert.equal(coldMajor.title, undefined)
  restarted.page.pendingApplication = cold
  let writes = 0
  await restarted.page.sendApplication({ title: '不得自动重放', body: { sourceCourseName: '新内容' }, send: async () => { writes += 1 }, rows: [], idKey: 'recognitionId' })
  assert.equal(writes, 0)

  setIdentity(storage, 'student-b')
  assert.equal(restarted.api.readPending('recognition'), null)
  assert.equal(restarted.api.canUpdatePendingCommand('recognition', command), false)
  command.returnedId = 'late-ack-from-a'
  assert.equal(restarted.api.savePending('recognition', command), false)
  setIdentity(storage, 'student-a')
  const returned = restarted.api.readPending('recognition')
  assert.equal(returned.returnedId, 'recognition-9')
})

test('a storage failure prevents the POST before it leaves the application page', async () => {
  const storage = new Map()
  setIdentity(storage)
  const run = runtime(storage, { failPendingWrite: true })
  let writes = 0
  await run.page.sendApplication({
    title: '提交成绩认定申请', body: { sourceCourseName: '电工基础' }, rows: [], idKey: 'recognitionId',
    send: async () => { writes += 1; return { recognitionId: 'new-1' } }
  })
  assert.equal(writes, 0)
  assert.match(run.page.applicationNotice, /未发送申请/)
  assert.equal(storage.get(pendingKey), undefined)
})
