import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import vm from 'node:vm'

function deferred() {
  let resolve
  let reject
  const promise = new Promise((yes, no) => { resolve = yes; reject = no })
  return { promise, resolve, reject }
}

function storageStub() {
  let value = ''
  return {
    getStorageSync: () => value,
    setStorageSync: (_key, next) => { value = next }
  }
}

function loadWriteContract(storage = storageStub()) {
  const source = fs.readFileSync(new URL('./write-result.js', import.meta.url), 'utf8')
    .replace(/export function/g, 'function')
    .replace(/export const/g, 'const')
  const sandbox = { uni: storage }
  vm.runInNewContext(`${source}
globalThis.contract = { isExplicitWriteRejection, isForbiddenResponse, teacherWriteContext, listPersistentWrites, getPersistentWrite, beginPersistentWrite, persistWriteAck, clearPersistentWrite }`, sandbox)
  return { ...sandbox.contract, storage }
}

function createPage(dependencies = {}) {
  const pageSource = fs.readFileSync(new URL('./grade-entry.vue', import.meta.url), 'utf8')
  const source = pageSource
    .split('<script>')[1].split('</script>')[0]
    .replace(/^import .*$/gm, '')
    .replace('export default', 'globalThis.options =')
  const writeContract = dependencies.writeContract || loadWriteContract()
  // Inject only bindings actually imported by the page, so missing imports fail here too.
  const writeImports = pageSource.match(/import\s*\{([^}]+)\}\s*from\s*['"]\.\/write-result['"]/)[1]
    .split(',').map(name => name.trim())
  const sandbox = {
    teacherApi: {},
    academicGradeEntryApi: {},
    normalizeError: () => ({ text: '请求失败' }),
    toast() {},
    useSessionStore: () => ({ identity: { tenantId: '1', userId: '2', activeContextId: 'A' }, currentRole: 'teacher' }),
    ...Object.fromEntries(writeImports.map(name => [name, writeContract[name]])),
    ...dependencies,
    uni: {
      getStorageSync: writeContract.storage.getStorageSync,
      setStorageSync: writeContract.storage.setStorageSync
    }
  }
  vm.runInNewContext(source, sandbox)
  const options = sandbox.options
  const instance = options.data()
  for (const [name, method] of Object.entries(options.methods)) instance[name] = method.bind(instance)
  for (const [name, getter] of Object.entries(options.computed || {})) {
    Object.defineProperty(instance, name, { get: () => getter.call(instance) })
  }
  instance._pageActive = true
  if (options.onHide) instance.onHide = options.onHide.bind(instance)
  return { instance, writeContract }
}

function roster(overrides = {}) {
  const base = {
    gradeTaskId: '8',
    taskVersion: 1,
    courseName: 'PLC',
    status: 'INPUTTING',
    passLine: 60,
    entryMode: 'COMPONENTS',
    canWriteComponents: true,
    scheme: {
      schemeId: '3',
      schemeVersion: 2,
      components: [
        { code: 'PROJECT', name: 'Project', weight: 60, required: true },
        { code: 'LAB', name: 'Lab', weight: 40, required: true }
      ]
    },
    rosterIdentity: { rosterVersionId: '5', rosterVersionNo: 1, rosterHash: 'a'.repeat(64), memberCount: 2 },
    total: 2,
    page: 1,
    pageSize: 30,
    hasMore: false,
    items: [
      { studentId: '11', studentNo: 'S11', realName: 'Student 11', scores: { PROJECT: 80, LAB: 90 }, totalScore: 84, exceptionFlag: 'NORMAL', recordId: '21', rowVersion: 4 },
      { studentId: '12', studentNo: 'S12', realName: 'Student 12', scores: { PROJECT: 70, LAB: 80 }, totalScore: 74, exceptionFlag: 'NORMAL', recordId: '22', rowVersion: 4 }
    ]
  }
  return {
    ...base,
    ...overrides,
    scheme: overrides.scheme || base.scheme,
    rosterIdentity: overrides.rosterIdentity || base.rosterIdentity,
    items: overrides.items || base.items
  }
}

function dynamicPage(dependencies = {}, initial = roster()) {
  const created = createPage(dependencies)
  const instance = created.instance
  instance.active = { gradeTaskId: '8', courseName: 'PLC', status: 'INPUTTING', passLine: 60 }
  instance._rosterEpoch = 1
  instance.applyDynamicRoster(instance.active, initial)
  instance.rosterState = 'ready'
  return created
}

function flush() {
  return new Promise((resolve) => setImmediate(resolve))
}

test('single-row readback keeps another student draft and a newer edit on the submitted student', async () => {
  const post = deferred()
  const formal = roster({
    taskVersion: 2,
    items: [
      { studentId: '11', studentNo: 'S11', realName: 'Student 11', scores: { PROJECT: 82, LAB: 90 }, totalScore: 87, exceptionFlag: 'NORMAL', recordId: '21', rowVersion: 5 },
      { studentId: '12', studentNo: 'S12', realName: 'Student 12', scores: { PROJECT: 70, LAB: 80 }, totalScore: 74, exceptionFlag: 'NORMAL', recordId: '22', rowVersion: 4 }
    ]
  })
  const { instance } = dynamicPage({
    academicGradeEntryApi: {
      componentBatchSave: () => post.promise,
      componentRoster: async () => formal,
      componentCommandReceipt: async (_id, operation, key) => ({
        state: 'SUCCESS', operation, commandKey: key, result: { gradeTaskId: '8', taskVersion: 2, items: [{ studentId: '11', recordId: '21', rowVersion: 5 }] }
      })
    }
  })
  instance.scores['12'].components.PROJECT = '77'
  instance.markDirty('12')
  instance.scores['11'].components.PROJECT = '82'
  instance.markDirty('11')
  const saving = instance.saveScore(instance.roster[0])
  await flush()
  instance.scores['11'].components.PROJECT = '95'
  instance.markDirty('11')
  post.resolve({ gradeTaskId: '8', taskVersion: 2 })
  assert.equal(await saving, false)
  assert.equal(instance.scores['11'].components.PROJECT, '95')
  assert.equal(instance.scores['11'].rowVersion, 5)
  assert.equal(instance.dirty['11'], true)
  assert.equal(instance.scores['12'].components.PROJECT, '77')
  assert.equal(instance.dirty['12'], true)
})

test('unchanged submitted row clears alone and the remaining draft can be saved next', async () => {
  let version = 1
  const { instance } = dynamicPage({
    academicGradeEntryApi: {
      componentBatchSave: async () => ({ gradeTaskId: '8', taskVersion: ++version }),
      componentRoster: async () => roster({
        taskVersion: version,
        items: [
          { studentId: '11', studentNo: 'S11', realName: 'Student 11', scores: { PROJECT: 82, LAB: 90 }, totalScore: 87, exceptionFlag: 'NORMAL', recordId: '21', rowVersion: version + 3 },
          { studentId: '12', studentNo: 'S12', realName: 'Student 12', scores: { PROJECT: version === 2 ? 70 : 77, LAB: 80 }, totalScore: version === 2 ? 74 : 78, exceptionFlag: 'NORMAL', recordId: '22', rowVersion: version === 2 ? 4 : 5 }
        ]
      }),
      componentCommandReceipt: async (_id, operation, key) => ({
        state: 'SUCCESS', operation, commandKey: key, result: { gradeTaskId: '8', taskVersion: version, items: version === 2 ? [{ studentId: '11', recordId: '21', rowVersion: 5 }] : [{ studentId: '12', recordId: '22', rowVersion: 5 }] }
      })
    }
  })
  instance.scores['11'].components.PROJECT = '82'
  instance.markDirty('11')
  instance.scores['12'].components.PROJECT = '77'
  instance.markDirty('12')
  assert.equal(await instance.saveScore(instance.roster[0]), true)
  assert.equal(instance.dirty['11'], false)
  assert.equal(instance.dirty['12'], true)
  assert.equal(instance.hasGradePending, false)
  assert.equal(await instance.saveScore(instance.roster[1]), true)
  assert.equal(instance.dirty['12'], false)
  assert.equal(instance.scores['12'].rowVersion, 5)
})

test('roster version mismatch never replaces drafts or clears the acknowledged command', async () => {
  const { instance, writeContract } = dynamicPage({
    academicGradeEntryApi: {
      componentBatchSave: async () => ({ gradeTaskId: '8', taskVersion: 2 }),
      componentRoster: async () => roster({
        taskVersion: 2,
        rosterIdentity: { rosterVersionId: '6', rosterVersionNo: 2, rosterHash: 'b'.repeat(64), memberCount: 2 }
      })
    }
  })
  instance.scores['11'].components.PROJECT = '93'
  instance.markDirty('11')
  assert.equal(await instance.saveScore(instance.roster[0]), false)
  assert.equal(instance.scores['11'].components.PROJECT, '93')
  assert.equal(instance.scores['11'].rowVersion, 4)
  assert.equal(instance.dirty['11'], true)
  assert.equal(writeContract.getPersistentWrite(instance.contextKey(), 'GRADE_COMPONENT_BATCH_SAVE', '8').record.state, 'ACK')
})

test('late receipt cannot rewrite a newer page pending state', async () => {
  const receipt = deferred()
  const session = { identity: { tenantId: '1', userId: '2', activeContextId: 'A' }, currentRole: 'teacher' }
  const { instance, writeContract } = dynamicPage({
    useSessionStore: () => session,
    academicGradeEntryApi: {
      componentBatchSave: async () => ({ gradeTaskId: '8', taskVersion: 2 }),
      componentRoster: async () => roster({ taskVersion: 2 }),
      componentCommandReceipt: () => receipt.promise
    }
  })
  instance.markDirty('11')
  const saving = instance.saveScore(instance.roster[0])
  await flush()
  const contextA = instance.contextKey()
  instance.onHide()
  session.identity.activeContextId = 'B'
  instance.gradePendingWrites = { sentinel: 'B' }
  receipt.resolve({ state: 'SUCCESS', operation: 'GRADE_COMPONENT_BATCH_SAVE', commandKey: 'unused', result: { gradeTaskId: '8', taskVersion: 2 } })
  assert.equal(await saving, false)
  assert.deepEqual(instance.gradePendingWrites, { sentinel: 'B' })
  assert.equal(writeContract.getPersistentWrite(contextA, 'GRADE_COMPONENT_BATCH_SAVE', '8').record.state, 'ACK')
})

test('receipt 403 clears the private roster and preserves the minimal command reference', async () => {
  const { instance, writeContract } = dynamicPage({
    academicGradeEntryApi: {
      componentBatchSave: async () => ({ gradeTaskId: '8', taskVersion: 2 }),
      componentRoster: async () => roster({ taskVersion: 2 }),
      componentCommandReceipt: async () => { throw { code: 403002, httpStatus: 403 } }
    }
  })
  const context = instance.contextKey()
  instance.markDirty('11')
  assert.equal(await instance.saveScore(instance.roster[0]), false)
  assert.equal(instance.roster.length, 0)
  assert.equal(Object.keys(instance.scores).length, 0)
  assert.equal(instance.dynamicReadDenied, true)
  const pending = writeContract.getPersistentWrite(context, 'GRADE_COMPONENT_BATCH_SAVE', '8').record
  assert.equal(pending.state, 'ACK')
  assert.ok(pending.requestKey)
})

test('page navigation reconciles an unknown command before showing the next formal page', async () => {
  const contract = loadWriteContract()
  const second = roster({
    taskVersion: 2,
    page: 2,
    total: 31,
    hasMore: false,
    items: [{ studentId: '31', studentNo: 'S31', realName: 'Student 31', scores: { PROJECT: 71, LAB: 81 }, totalScore: 75, exceptionFlag: 'NORMAL', recordId: '31', rowVersion: 1 }]
  })
  const { instance } = dynamicPage({
    writeContract: contract,
    academicGradeEntryApi: {
      componentRoster: async () => second,
      componentCommandReceipt: async (_id, operation, key) => ({
        state: 'SUCCESS', operation, commandKey: key, result: { gradeTaskId: '8', taskVersion: 2 }
      })
    }
  }, roster({ total: 31, hasMore: true }))
  const context = instance.contextKey()
  contract.beginPersistentWrite(context, 'GRADE_COMPONENT_BATCH_SAVE', '8', { requestKey: 'gmp_pending_1' })
  contract.persistWriteAck(context, 'GRADE_COMPONENT_BATCH_SAVE', '8', { ackId: 'gmp_pending_1', parentId: '8' })
  instance.syncGradePending(context, '8')
  assert.equal(await instance.showMoreRoster(), undefined)
  assert.equal(instance.rosterPage, 2)
  assert.equal(instance.roster[0].studentId, '31')
  assert.equal(instance.hasGradePending, false)
})

for (const targetId of ['11', '12']) {
  test(`another write to student ${targetId} cannot silently advance a retained draft version`, async () => {
    let writes = 0
    const formal = roster({ taskVersion: 3 })
    formal.items[0].rowVersion = targetId === '11' ? 6 : 5
    formal.items[1].rowVersion = targetId === '12' ? 5 : 4
    formal.items.find(row => row.studentId === targetId).scores.PROJECT = 91
    const { instance } = dynamicPage({ academicGradeEntryApi: {
      componentBatchSave: async () => { writes++; return { gradeTaskId: '8', taskVersion: 2 } },
      componentRoster: async () => formal,
      componentCommandReceipt: async (_id, operation, commandKey) => ({ state: 'SUCCESS', operation, commandKey,
        result: { gradeTaskId: '8', taskVersion: 2, items: [{ studentId: '11', recordId: '21', rowVersion: 5 }] } })
    } })
    instance.scores[targetId].components.PROJECT = '77'
    instance.markDirty(targetId)
    instance.markDirty('11')
    await instance.saveScore(instance.roster[0])
    const score = instance.scores[targetId]
    assert.equal(score.components.PROJECT, '77')
    assert.equal(score.rowVersion, 4)
    assert.equal(score.conflictFormal.components.PROJECT, '91')
    assert.equal(instance.dirty[targetId], true)
    assert.equal(await instance.saveScore(instance.roster.find(row => row.studentId === targetId)), false)
    assert.equal(writes, 1)
    instance.confirmModal = async (_title, comparison) => { assert.match(comparison, /91/); assert.match(comparison, /77/); return false }
    assert.equal(await instance.reviewDynamicConflict(instance.roster.find(row => row.studentId === targetId)), false)
    assert.equal(score.rowVersion, 4)
    instance.confirmModal = async () => true
    assert.equal(await instance.reviewDynamicConflict(instance.roster.find(row => row.studentId === targetId)), true)
    assert.equal(score.rowVersion, targetId === '11' ? 6 : 5)
    assert.equal(score.components.PROJECT, '77')
    assert.equal(score.conflictFormal, null)
    assert.equal(writes, 1, 'reviewing a conflict does not write grades')
  })
}

test('a dynamic POST 403 scrubs private grades without waiting for a later roster read', async () => {
  const { instance } = dynamicPage({ academicGradeEntryApi: {
    componentBatchSave: async () => { throw { httpStatus: 403, code: '403002' } }
  } })
  instance.markDirty('11')
  assert.equal(await instance.saveScore(instance.roster[0]), false)
  assert.equal(instance.dynamicReadDenied, true)
  assert.equal(instance.roster.length, 0)
  assert.equal(Object.keys(instance.scores).length, 0)
})

test('409 keeps drafts for explicit comparison and a late confirmation cannot adopt new versions', async () => {
  const confirmation = deferred()
  const formal = roster({ taskVersion: 2 })
  formal.items[0].scores.PROJECT = 91
  formal.items[0].rowVersion = 5
  const { instance } = dynamicPage({ academicGradeEntryApi: {
    componentBatchSave: async () => { throw { httpStatus: 409, code: 'DATA_CONFLICT' } },
    componentRoster: async () => formal
  } })
  instance.scores['11'].components.PROJECT = '77'
  instance.markDirty('11')
  assert.equal(await instance.saveScore(instance.roster[0]), false)
  assert.equal(instance.dynamicNeedsReview, true)
  assert.equal(await instance.recheckDynamicState(), true)
  assert.equal(instance.scores['11'].rowVersion, 4)
  assert.equal(instance.scores['11'].components.PROJECT, '77')
  instance.confirmModal = () => confirmation.promise
  const review = instance.reviewDynamicConflict(instance.roster[0])
  instance.scores['11'].components.PROJECT = '78'
  instance.markDirty('11')
  confirmation.resolve(true)
  assert.equal(await review, false)
  assert.equal(instance.scores['11'].rowVersion, 4)
  assert.ok(instance.scores['11'].conflictFormal)
})

test('a permitted reread after 403 restores the formal roster without retaining private drafts', async () => {
  const { instance } = dynamicPage({ academicGradeEntryApi: { componentRoster: async () => roster() } })
  instance.scores['11'].components.PROJECT = '77'
  instance.markDirty('11')
  instance.clearDynamicPrivateState()
  assert.equal(await instance.recheckDynamicState(), true)
  assert.equal(instance.dynamicReadDenied, false)
  assert.equal(instance.rosterState, 'ready')
  assert.equal(instance.scores['11'].components.PROJECT, '80')
  assert.equal(instance.dirtyCount, 0)
})

test('an older receipt cannot clear a newer command reserved by another page', async () => {
  const receipt = deferred()
  const { instance, writeContract } = dynamicPage({ academicGradeEntryApi: { componentCommandReceipt: () => receipt.promise } })
  const context = instance.contextKey()
  const action = 'GRADE_COMPONENT_BATCH_SAVE'
  writeContract.beginPersistentWrite(context, action, '8', { requestKey: 'gmp_original_1' })
  const checking = instance.reconcileGradeCommands(roster({ taskVersion: 2 }))
  writeContract.clearPersistentWrite(context, action, '8')
  writeContract.beginPersistentWrite(context, action, '8', { requestKey: 'gmp_newer_2' })
  receipt.resolve({ state: 'SUCCESS', operation: action, commandKey: 'gmp_original_1', result: { gradeTaskId: '8', taskVersion: 2 } })
  await checking
  assert.equal(writeContract.getPersistentWrite(context, action, '8').record.requestKey, 'gmp_newer_2')
  assert.equal(instance.hasGradePending, true)
})

test('an older POST acknowledgement cannot update a newer reserved command', async () => {
  const post = deferred()
  const { instance, writeContract } = dynamicPage({ academicGradeEntryApi: { componentBatchSave: () => post.promise } })
  instance.markDirty('11')
  const saving = instance.saveScore(instance.roster[0])
  const context = instance.contextKey()
  const action = 'GRADE_COMPONENT_BATCH_SAVE'
  writeContract.clearPersistentWrite(context, action, '8')
  writeContract.beginPersistentWrite(context, action, '8', { requestKey: 'gmp_newer_2' })
  instance.onHide()
  post.resolve({ gradeTaskId: '8', taskVersion: 2 })
  await saving
  const pending = writeContract.getPersistentWrite(context, action, '8').record
  assert.equal(pending.requestKey, 'gmp_newer_2')
  assert.equal(pending.state, 'PENDING')
  assert.equal(pending.ackId, undefined)
})

test('dynamic scores accept exact two-decimal inputs despite binary floating-point representation', () => {
  const { instance } = dynamicPage()
  for (const score of ['0', '8.07', '99.99', '.5', '100']) {
    instance.scores['11'].components.PROJECT = score
    const built = instance.buildScoreBody(instance.roster[0])
    assert.equal(built.error, undefined, score)
    assert.equal(built.body.scores.PROJECT, Number(score))
  }
  for (const score of ['8.071', '1e1', '0x10', '100.01', '-1']) {
    instance.scores['11'].components.PROJECT = score
    assert.ok(instance.buildScoreBody(instance.roster[0]).error, score)
  }
})
