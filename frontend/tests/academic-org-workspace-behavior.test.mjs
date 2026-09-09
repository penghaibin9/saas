import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'
import test from 'node:test'
import { matchPermission } from '../src/config/navPlan.js'
import { ACADEMIC_STUDENT_STATUS_LABELS } from '../src/modules/academicAffairs/config/academicStudentLabels.js'
import { formatDateTime } from '../src/utils/dateUtils.js'

function page(api = {}, extra = {}) {
  const source = readFileSync(new URL('../src/modules/academicAffairs/views/AaOrgConsole.vue', import.meta.url), 'utf8')
  const script = source.match(/<script>([\s\S]*?)<\/script>/)[1]
    .replace(/^import (.*?) from .*$/gm, (_, binding) => `const ${binding.replace(/ as /g, ': ')} = dependencies${binding.startsWith('{') ? '' : '.' + binding}`)
    .replace('export default', 'component =')
  const sandbox = { dependencies: { academicAffairsOrgApi: api, matchPermission, ACADEMIC_STUDENT_STATUS_LABELS, formatDateTime, toast: { success() {}, error() {}, warning() {} } } }
  vm.runInNewContext(script, sandbox)
  const definition = sandbox.component
  const state = Object.assign(definition.data(), definition.methods, {
    ctx: { permissionPatterns: ['academicAffairs.org.view', 'academicAffairs.org.manage'], currentRole: { roleName: '学校管理员' }, dataScope: { scope: 'SCHOOL', scopeName: '本校' } },
    $route: { query: {} }, $router: { replace() {} },
  }, extra)
  for (const [key, getter] of Object.entries(definition.computed)) Object.defineProperty(state, key, { get: () => getter.call(state) })
  return { state, definition }
}
const deferred = () => { let resolve; const promise = new Promise(done => { resolve = done }); return { promise, resolve } }

test('major editor retains input and releases saving after a rejected request', async () => {
  const { state } = page({ updateMajor: async () => { throw new Error('连接中断，请核对保存结果') } }, { tab: 'major' })
  state.openEdit({ id: 'major', collegeId: 'college', majorName: '原专业', version: 3 })
  state.form.model.majorName = '待保存名称'
  await state.submitForm()
  assert.equal(state.form.submitting, false)
  assert.equal(state.form.visible, true)
  assert.equal(state.form.model.majorName, '待保存名称')
  assert.match(state.form.error, /连接中断/)
  state.closeForm()
  assert.equal(state.form.visible, false)
})

test('major version conflicts preserve edits and require reopening current data', async () => {
  let writes = 0, reads = 0
  const { state } = page({
    updateMajor: async () => { writes++; return { code: 409001, bizCode: 'DATA_CONFLICT',
      details: { reason: 'VERSION_CONFLICT', currentVersion: 4 }, message: '专业已被修改' } },
    listMajors: async () => { reads++; return { code: 0, data: { list: [], total: 0 } } },
  }, { tab: 'major' })
  state.openEdit({ id: 'major', collegeId: 'college', majorName: '原专业', version: 3 })
  state.form.model.majorName = '我的修改'
  await state.submitForm()
  await state.submitForm()
  assert.equal(writes, 1); assert.equal(reads, 1)
  assert.equal(state.form.needsReload, true)
  assert.equal(state.form.model.majorName, '我的修改')
  assert.equal(state.form.model.version, 3)
  assert.match(state.form.error, /输入仍保留/)
  state.closeForm()
  state.openEdit({ id: 'major', collegeId: 'college', majorName: '最新专业', version: 4 })
  assert.equal(state.form.needsReload, false)
})

test('ordinary business conflicts remain correctable and late saves cannot close a replacement form', async () => {
  const pending = deferred()
  let calls = 0
  const { state } = page({ updateMajor: () => {
    calls++
    return calls === 1 ? Promise.resolve({ code: 409001, bizCode: 'DATA_CONFLICT', message: '编码冲突' }) : pending.promise
  } }, { tab: 'major' })
  state.openEdit({ id: 'major', collegeId: 'college', majorName: '专业', version: 3 })
  await state.submitForm()
  assert.equal(state.form.needsReload, false)
  const old = state.form
  const saving = state.submitForm()
  state.form = { visible: true, submitting: false, model: { majorName: '新表单' } }
  pending.resolve({ code: 0, data: {} }); await saving
  assert.equal(old.submitting, false)
  assert.equal(state.form.visible, true)
  assert.equal(state.form.model.majorName, '新表单')
})

test('college name ambiguity is correctable while a version conflict preserves the original secretary display', async () => {
  let attempts = 0
  const { state } = page({
    updateCollege: async () => (++attempts === 1
      ? { code: 409001, bizCode: 'DATA_CONFLICT', details: { reason: 'SCOPE_NAME_AMBIGUITY' }, message: '该名称会混淆学院管理范围，请核对后更名' }
      : { code: 409001, bizCode: 'DATA_CONFLICT', details: { reason: 'VERSION_CONFLICT' }, message: '学院记录已更新' }),
    listColleges: async () => ({ code: 0, data: { list: [], total: 0 } }),
  }, { tab: 'college' })
  state.openEdit({ id: 'college', collegeName: '原学院', version: 3, secretaryId: 'staff', secretaryName: '原秘书' })
  state.form.model.collegeName = '冲突名称'
  await state.submitForm()
  assert.equal(state.form.visible, true); assert.equal(state.form.needsReload, false)
  assert.match(state.form.error, /学院管理范围/)
  state.form.model.collegeName = '纠正后的名称'
  await state.submitForm()
  assert.equal(state.form.needsReload, true)
  assert.equal(state.form.model.collegeName, '纠正后的名称')
  assert.equal(state.form.model.secretaryId, 'staff')
  assert.equal(state.form.model.secretaryName, '原秘书')
  await state.submitForm(); assert.equal(attempts, 2)
})

test('secretary review discards replies after closing or selecting another person', async () => {
  const request = deferred()
  const { state, definition } = page({ listSecretaryCandidates: () => request.promise })
  state.openSecretary({ id: 'college-1', collegeName: '信息学院', version: 2 })
  state.secretary.secretaryId = 'staff-1'
  const reading = state.reviewSecretary()
  state.secretary.secretaryId = 'staff-2'
  definition.watch['secretary.secretaryId'].call(state)
  request.resolve({ code: 0, data: { list: [{ value: 'staff-1', label: '旧老师' }] } }); await reading
  assert.equal(state.secretary.review, null)
  assert.equal(state.secretary.reviewing, false)
  state.closeSecretary()
  assert.equal((await state.fetchSecretaryOptions({})).length, 0)
})

test('secretary editing resolves the exact bound name and keeps directory failures visible', async () => {
  const { state } = page({ listSecretaryCandidates: async () => ({ code: 503001, message: '目录暂不可用' }) })
  state.openSecretary({ id: 'college-1', collegeName: '信息学院', secretaryId: '999', secretaryName: '停用教师', secretaryStatus: 'DISABLED', version: 2 })
  const option = await state.resolveSecretaryCandidate('999')
  assert.equal(option.label, '停用教师'); assert.equal(option.disabled, true)
  state.secretary.secretaryId = 'other'
  await state.reviewSecretary()
  assert.equal(state.secretary.visible, true)
  assert.equal(state.secretary.error, '目录暂不可用')
  assert.equal(state.secretary.secretaryId, 'other')
  assert.equal(state.secretary.review, null)
})

test('secretary confirmation freezes the college and version, blocks duplicate writes, and shows the real receipt', async () => {
  const saving = deferred()
  let sent, count = 0
  const { state } = page({
    listSecretaryCandidates: async () => ({ code: 0, data: { list: [{ value: 'staff-1', label: '李老师' }] } }),
    bindSecretary: (id, secretaryId, version) => { sent = { id, secretaryId, version }; count++; return saving.promise },
    listColleges: async () => ({ code: 0, data: { list: [], total: 0 } }),
  })
  const row = { id: 'college-1', collegeName: '信息学院', secretaryId: 'old', secretaryName: '原教师', secretaryStatus: 'ACTIVE', version: 2 }
  state.openSecretary(row); state.secretary.secretaryId = 'staff-1'
  await state.submitSecretary(); assert.equal(count, 0)
  await state.reviewSecretary()
  assert.match(state.secretary.review.message, /信息学院：原教师 → 李老师/)
  row.id = 'other-college'; row.version = 90
  const pending = state.submitSecretary()
  state.closeSecretary(); await state.submitSecretary()
  assert.equal(state.secretary.visible, true)
  assert.equal(count, 1)
  assert.deepEqual(sent, { id: 'college-1', secretaryId: 'staff-1', version: 2 })
  saving.resolve({ code: 0, data: { id: 'college-1', collegeName: '信息学院', secretaryId: 'staff-1', secretaryName: '李老师', version: 3 } }); await pending
  assert.equal(state.secretary.receipt.version, 3)
  assert.equal(state.secretary.receipt.secretaryName, '李老师')
  assert.equal(state.secretary.visible, true)
  await state.submitSecretary(); assert.equal(count, 1)
})

test('secretary unbinding has an explicit review and a stale college requires reloading without dropping selection', async () => {
  let sent
  const { state } = page({
    bindSecretary: async (id, sid, version) => { sent = { id, sid, version }; return { code: 409001, bizCode: 'DATA_CONFLICT', message: '学院已更新' } },
    listColleges: async () => ({ code: 0, data: { list: [], total: 0 } }),
  })
  state.openSecretary({ id: 'c', collegeName: '信息学院', secretaryId: 'old', secretaryName: '原教师', secretaryStatus: 'ACTIVE', version: 2 })
  state.secretary.secretaryId = ''
  await state.reviewSecretary()
  assert.equal(state.secretary.review.secretaryId, null)
  assert.match(state.secretary.review.message, /解除学院绑定/)
  await state.submitSecretary()
  assert.deepEqual(sent, { id: 'c', sid: null, version: 2 })
  assert.equal(state.secretary.needsReload, true)
  assert.equal(state.secretary.secretaryId, '')
  assert.equal(state.secretary.review, null)
  assert.match(state.secretary.error, /重新打开/)
})

test('secretary no-change, unavailable candidates and read-only operators cannot submit', async () => {
  let writes = 0
  const { state } = page({
    listSecretaryCandidates: async () => ({ code: 0, data: { list: [] } }),
    bindSecretary: async () => { writes++; return { code: 0 } },
  })
  state.openSecretary({ id: 'c', collegeName: '信息学院', version: 0 })
  await state.reviewSecretary(); await state.submitSecretary()
  assert.equal(writes, 0)
  state.secretary.secretaryId = 'gone'; await state.reviewSecretary()
  assert.match(state.secretary.error, /已不可用/)
  state.ctx.permissionPatterns = ['academicAffairs.org.view']
  await state.submitSecretary(); assert.equal(writes, 0)
})

function directionPage(api = {}) {
  const result = page(api, { tab: 'direction', directionMajorId: 'major-1', majorOptions: [{ value: 'major-1', label: '软件技术' }] })
  Object.assign(result.state.directionToggle, { enabled: true, loaded: true, version: 4 })
  return result
}

test('direction settings failures remain unknown and an old request cannot restore an earlier setting', async () => {
  const old = deferred()
  let reads = 0
  const { state } = directionPage({ getMajorDirectionToggle: () => ++reads === 1 ? old.promise : Promise.resolve({ code: 503001, message: '读取失败' }) })
  const pending = state.loadDirectionToggle()
  await state.loadDirectionToggle()
  old.resolve({ code: 0, data: { enabled: true, version: 1 } }); await pending
  assert.equal(state.directionToggle.loaded, false)
  assert.equal(state.directionToggle.error, '读取失败')
  state.toggleMajorDirection(); state.openDirectionCreate()
  assert.equal(state.directionConfirm.visible, false)
  assert.equal(state.directionForm.visible, false)
})

test('direction lists discard previous majors and preserve real pagination totals', async () => {
  const old = deferred()
  let sent
  const { state } = directionPage({ listDirections: (major, params) => {
    sent = { major, ...params }
    return major === 'major-1' ? old.promise : Promise.resolve({ code: 0, data: { list: [{ id: 'new' }], total: 401 } })
  } })
  const pending = state.reloadDirections()
  state.directionMajorId = 'major-2'; state.directions.page = 3
  await state.reloadDirections()
  old.resolve({ code: 0, data: { list: [{ id: 'old' }], total: 1 } }); await pending
  assert.deepEqual(sent, { major: 'major-2', page: 3, pageSize: 20 })
  assert.equal(state.directions.rows[0].id, 'new')
  assert.equal(state.directions.total, 401)
  state.openDirectionCreate()
  state.changeDirectionMajor()
  assert.equal(state.directionForm.visible, false)
  assert.equal(state.directions.page, 1)
})

test('direction saves freeze the parent, normalize fields and retain errors without double writes', async () => {
  const pending = deferred()
  let sent, count = 0
  const { state } = directionPage({ updateDirection: (major, id, body) => { sent = { major, id, ...body }; count++; return pending.promise } })
  state.openDirectionEdit({ id: 'd1', majorId: 'major-1', status: 'ACTIVE', directionName: ' 软件开发 ', code: '   ', version: 2 })
  state.directionMajorId = 'major-2'
  const saving = state.submitDirectionForm()
  state.closeDirectionForm(); await state.submitDirectionForm()
  assert.equal(state.directionForm.visible, true)
  assert.equal(count, 1)
  assert.deepEqual(sent, { major: 'major-1', id: 'd1', directionName: '软件开发', code: null, expectedVersion: 2 })
  pending.resolve({ code: 409001, bizCode: 'DATA_CONFLICT', message: '方向编码已存在' }); await saving
  assert.equal(state.directionForm.error, '方向编码已存在')
  assert.equal(state.directionForm.model.directionName, ' 软件开发 ')
  assert.equal(state.directionForm.needsReload, false)
})

test('direction version conflicts require reopening the latest row and preserve entered changes', async () => {
  let writes = 0
  const { state } = directionPage({
    updateDirection: async () => { writes++; return { code: 409001, bizCode: 'DATA_CONFLICT', details: { reason: 'VERSION_CONFLICT' }, message: '版本已变化' } },
    listDirections: async () => ({ code: 0, data: { list: [], total: 0 } }),
  })
  state.openDirectionEdit({ id: 'd1', majorId: 'major-1', status: 'ACTIVE', directionName: '保留输入', version: 2 })
  await state.submitDirectionForm(); await state.submitDirectionForm()
  assert.equal(writes, 1)
  assert.equal(state.directionForm.needsReload, true)
  assert.equal(state.directionForm.model.directionName, '保留输入')
  assert.match(state.directionForm.error, /重新打开/)
})

test('direction disable requires a confirmation and submits the frozen row only once', async () => {
  const pending = deferred()
  let sent, count = 0
  const { state } = directionPage({ disableDirection: (major, id, body) => { sent = { major, id, ...body }; count++; return pending.promise } })
  const row = { id: 'd1', majorId: 'major-1', status: 'ACTIVE', directionName: '软件开发', version: 3 }
  state.disableDirection(row)
  assert.equal(count, 0)
  assert.match(state.directionConfirm.message, /软件开发.*历史/)
  row.id = 'wrong'; row.version = 900; state.directionMajorId = 'major-2'
  const saving = state.submitDirectionAction()
  state.closeDirectionAction(); await state.submitDirectionAction()
  assert.equal(state.directionConfirm.visible, true)
  assert.equal(count, 1)
  assert.deepEqual(sent, { major: 'major-1', id: 'd1', expectedVersion: 3 })
  pending.resolve({ code: 409001, bizCode: 'DATA_CONFLICT', message: '已经变化' }); await saving
  assert.equal(state.directionConfirm.needsReload, true)
  assert.match(state.directionConfirm.error, /已经变化/)
})

test('direction toggle confirms the reviewed target and version; disabled records are read only', async () => {
  let sent
  const { state } = directionPage({ setMajorDirectionToggle: async (enabled, version) => { sent = { enabled, version }; return { code: 0, data: { enabled, version: 5 } } } })
  state.toggleMajorDirection()
  assert.equal(sent, undefined)
  state.directionToggle.version = 8
  await state.submitDirectionAction()
  assert.deepEqual(sent, { enabled: false, version: 4 })
  assert.equal(state.directionToggle.enabled, false)
  assert.equal(state.directionConfirm.visible, false)
  Object.assign(state.directionToggle, { enabled: true, loaded: true })
  const row = { id: 'disabled', majorId: 'major-1', status: 'DISABLED' }
  state.openDirectionEdit(row); state.disableDirection(row)
  assert.equal(state.directionForm.visible, false)
  assert.equal(state.directionConfirm.visible, false)
})

test('deletion confirmation identifies the selected class, freezes its id and retains blocking feedback', async () => {
  let target, writes = 0
  const { state } = page({ deleteClass: async id => { target = id; writes++; return { code: 409, message: '仍有未归档教学任务' } } }, { tab: 'class' })
  const row = { id: 'class-1', collegeName: '上级学院', majorName: '软件专业', className: '实际删除班级' }
  state.openDelete(row)
  assert.match(state.del.message, /确认删除「实际删除班级」/)
  assert.doesNotMatch(state.del.message, /确认删除「软件专业」/)
  row.id = 'different-class'
  await state.submitDelete()
  assert.equal(target, 'class-1')
  assert.equal(state.del.visible, true)
  assert.equal(state.del.error, '仍有未归档教学任务')
  state.del.visible = false
  await state.submitDelete()
  assert.equal(writes, 1)
})

test('class state impact is discarded after changing the state or closing the editor', async () => {
  const request = deferred()
  const { state } = page({ previewClassState: () => request.promise }, { tab: 'class' })
  state.openEdit({ id: 'c', majorId: 'm', className: '验收班', classStatus: 'NORMAL', version: 3 })
  state.form.model.classStatus = 'DISBANDED'; state.form.model.reason = '班级停用原因说明'
  const pending = state.previewClassState()
  assert.equal(state.form.statePreviewing, true)
  state.closeForm()
  request.resolve({ code: 0, data: { classId: 'c', targetStatus: 'DISBANDED', blocked: false, snapshotHash: 'old' } })
  await pending
  assert.equal(state.form.statePreview, null)
  assert.equal(state.form.statePreviewing, false)
})

test('class state save requires an unblocked current impact and freezes the snapshot with the version', async () => {
  const saving = deferred()
  let sent, count = 0
  const { state } = page({
    previewClassState: async () => ({ code: 0, data: { classId: 'c', targetStatus: 'GRADUATED', blocked: false, snapshotHash: 'current' } }),
    updateClass: (id, body) => { sent = { id, body }; count++; return saving.promise },
  }, { tab: 'class' })
  state.openEdit({ id: 'c', majorId: 'm', className: '验收班', classStatus: 'NORMAL', version: 3 })
  state.form.model.classStatus = 'GRADUATED'; state.form.model.reason = '毕业结班原因说明'
  await state.submitForm()
  assert.equal(count, 0)
  await state.previewClassState()
  const pending = state.submitForm()
  state.closeForm(); await state.submitForm()
  assert.equal(state.form.visible, true)
  assert.equal(count, 1)
  assert.equal(sent.body.expectedVersion, 3)
  assert.equal(sent.body.expectedStateSnapshotHash, 'current')
  assert.equal(sent.body.reason, '毕业结班原因说明')
  saving.resolve({ code: 409, message: '班级引用已变化，请重新核对' })
  await pending
  assert.equal(state.form.visible, true)
  assert.equal(state.form.model.reason, '毕业结班原因说明')
  assert.equal(state.form.model.classStatus, 'GRADUATED')
  assert.equal(state.form.statePreview, null)
  assert.match(state.form.error, /重新核对/)
})

test('blocked impact or a mismatched target never enables saving and unchanged state needs no preview', async () => {
  let writes = 0
  const { state } = page({ updateClass: async () => { writes++; return { code: 409, message: '保留表单' } } }, { tab: 'class' })
  state.openEdit({ id: 'c', majorId: 'm', className: '验收班', classStatus: 'NORMAL', version: 3 })
  state.form.model.classStatus = 'DISBANDED'; state.form.model.reason = '停用原因验收说明'
  state.form.statePreview = { classId: 'c', targetStatus: 'DISBANDED', blocked: true, blockers: ['仍有学生'] }
  await state.submitForm()
  assert.equal(writes, 0)
  state.form.statePreview = { classId: 'c', targetStatus: 'GRADUATED', blocked: false }
  await state.submitForm()
  assert.equal(writes, 0)
  state.form.model.classStatus = 'NORMAL'
  assert.equal(state.classStateChanged, false)
  await state.submitForm()
  assert.equal(writes, 1)
})

test('organization UTC timestamps use the shared local display formatter without changing aware values', () => {
  const { state } = page()
  assert.equal(state.displayTime('2026-09-05T19:06:00'), formatDateTime('2026-09-05T19:06:00Z'))
  assert.equal(state.displayTime('2026-09-06T03:06:00+08:00'), formatDateTime('2026-09-06T03:06:00+08:00'))
  assert.equal(state.displayTime(null), '—')
})

test('teaching ledger sends the chosen term and keyword; task navigation checks permission', async () => {
  let sent, route
  const { state } = page({ listTeachingClasses: async params => { sent = params; return { code: 0, data: { list: [], total: 0 } } } }, {
    tab: 'teaching', $router: { push(value) { route = value } },
  })
  state.filters.termId = 'term-2'
  state.filters.keyword = '软件'
  await state.reload()
  assert.equal(sent.termId, 'term-2')
  assert.equal(sent.keyword, '软件')
  state.openTeachingBatch({ batchId: 'batch' })
  assert.equal(route, undefined)
  assert.equal(state.canViewTerms, false)
  state.ctx.permissionPatterns.push('academicAffairs.teachingTask.view', 'academicAffairs.term.view')
  state.openTeachingBatch({ batchId: 'batch' })
  assert.equal(route.name, 'aa-task-detail')
  assert.equal(route.params.batchId, 'batch')
  assert.equal(state.canViewTerms, true)
})

test('student list is paginated and an older class response cannot replace the new selection', async () => {
  const old = deferred()
  let params
  const { state } = page({ listClassStudents: async (id, query) => {
    if (id === 'old') return old.promise
    params = query
    return { code: 0, data: { list: [{ id: 'new-student' }], total: 241 } }
  } })
  state.studentsFilterClassId = 'old'
  const pending = state.reloadStudentsList()
  state.studentsFilterClassId = 'new'
  state.studentsList.page = 12
  await state.reloadStudentsList()
  old.resolve({ code: 0, data: { list: [{ id: 'old-student' }], total: 1 } })
  await pending
  assert.equal(params.page, 12)
  assert.equal(params.pageSize, 20)
  assert.equal(state.studentsList.total, 241)
  assert.equal(state.studentsList.rows[0].id, 'new-student')
  state.searchStudents()
  assert.equal(state.studentsList.page, 1)
  state.studentsFilterClassId = ''
  await state.reloadStudentsList()
  assert.equal(state.studentsList.total, 0)
  assert.equal(state.studentsList.rows.length, 0)
})

test('student drawer preserves read errors and discards a response for a closed or replaced class', async () => {
  const old = deferred()
  const { state } = page({ listClassStudents: async id => id === 'old' ? old.promise : { code: 500, message: '名册读取失败' } })
  const pending = state.openStudents({ id: 'old', className: '旧班' })
  await state.openStudents({ id: 'new', className: '新班' })
  old.resolve({ code: 0, data: { list: [{ id: 'private-old-student' }], total: 1 } })
  await pending
  assert.equal(state.students.className, '新班')
  assert.equal(state.students.rows.length, 0)
  assert.equal(state.students.error, '名册读取失败')
  assert.equal(state.students.loading, false)
})

test('leaving the page invalidates unfinished sensitive reads', async () => {
  const request = deferred()
  const { state, definition } = page({ listClassStudents: () => request.promise })
  state.studentsFilterClassId = 'class'
  const pending = state.reloadStudentsList()
  definition.beforeUnmount.call(state)
  request.resolve({ code: 0, data: { list: [{ id: 'late-student' }], total: 1 } })
  await pending
  assert.equal(state.studentsList.rows.length, 0)
})

test('write access uses permissions and school scope rather than the displayed role name', async () => {
  const { state } = page()
  state.ctx.permissionPatterns = ['academicAffairs.org.view']
  assert.equal(state.canManage, false)
  state.openCreate()
  state.openEdit({ id: 'a' })
  await state.submitForm()
  assert.equal(state.form.visible, false)
  state.ctx.permissionPatterns.push('academicAffairs.org.manage')
  state.ctx.dataScope.scope = 'COLLEGE'
  assert.equal(state.canManage, true)
  assert.equal(state.canCreate, false)
  state.tab = 'major'
  assert.equal(state.canCreate, true)
  assert.equal(state.canManageSchool, false)
  state.ctx.dataScope.scope = 'CLASS'
  assert.equal(state.canManage, false)
  assert.equal(state.canCreate, false)
})

test('same-parent edits omit a move and carry version plus explicit optional clears', async () => {
  let sent
  const { state } = page({ updateClass: async (...args) => { sent = args; return { code: 0 } } }, { tab: 'class' })
  state.loadOptions = state.reload = () => {}
  state.openEdit({ id: 'class', className: '测试班', majorId: 'major', capacity: 40, version: 7 })
  state.form.model.capacity = null
  await state.submitForm()
  assert.equal(sent[0], 'class')
  assert.equal(sent[1].expectedVersion, 7)
  assert.equal(sent[1].capacity, null)
  assert.equal(sent[1].majorId, undefined)
  assert.equal(sent[1].reason, undefined)
  assert.equal(state.form.visible, false)
})

test('changing parent requires a real reason; server conflict keeps all input and the editor open', async () => {
  let sent
  const { state } = page({ updateMajor: async (...args) => { sent = args; return { code: 409, message: '组织已被修改，请刷新' } } }, { tab: 'major' })
  state.openEdit({ id: 'major', collegeId: 'old', majorName: '测试专业', version: 3 })
  state.form.model.collegeId = 'new'
  await state.submitForm()
  assert.equal(sent, undefined)
  assert.match(state.form.error, /原因/)
  state.form.model.reason = '学院组织归属调整'
  await state.submitForm()
  assert.equal(sent[1].collegeId, 'new')
  assert.equal(sent[1].reason, '学院组织归属调整')
  assert.equal(state.form.visible, true)
  assert.equal(state.form.model.collegeId, 'new')
  assert.match(state.form.error, /刷新/)
})

test('switching entity tabs updates URL, closes editors and ignores an older list response', async () => {
  const old = deferred()
  let route
  const { state } = page({ listColleges: () => old.promise, listMajors: async () => ({ code: 0, data: { list: [{ id: 'major' }], total: 1 } }) }, { $router: { replace(value) { route = value } } })
  const pending = state.reload()
  state.openEdit({ id: 'college', collegeName: '旧学院' })
  state.switchTab('major')
  await Promise.resolve()
  old.resolve({ code: 0, data: { list: [{ id: 'college' }], total: 1 } })
  await pending
  assert.equal(route.query.tab, 'major')
  assert.equal(state.form.visible, false)
  assert.equal(state.rows[0].id, 'major')
})

test('a save cannot be double-submitted or redirected to another entity by navigation', async () => {
  const response = deferred()
  let calls = 0, accepted
  const { state, definition } = page({ updateCollege: () => { calls++; return response.promise } })
  state.reload = state.loadOptions = () => {}
  state.openEdit({ id: 'college', collegeName: '验收学院', version: 2 })
  const pending = state.submitForm()
  state.switchTab('class')
  state.closeForm()
  await state.submitForm()
  definition.beforeRouteLeave.call(state, {}, {}, value => { accepted = value })
  assert.equal(calls, 1)
  assert.equal(state.tab, 'college')
  assert.equal(state.form.visible, true)
  assert.equal(accepted, false)
  response.resolve({ code: 0 })
  await pending
  assert.equal(state.busy, false)
})

test('organization choices are not truncated to the first page and failed reads clear old choices', async () => {
  let failed = false
  const { state } = page({ orgTree: async () => failed ? { code: 500, message: '组织目录暂不可用' } : {
    code: 0, data: { colleges: [{ id: 'college', collegeName: '验收学院', majors: [
      { id: 'major', majorName: '验收专业', classes: Array.from({ length: 501 }, (_, i) => ({ id: String(i + 1), className: '班级' + (i + 1) })) },
    ] }] },
  } })
  await state.loadOptions()
  assert.equal(state.classOptions.length, 501)
  failed = true
  await state.loadOptions()
  assert.equal(state.classOptions.length, 0)
  assert.equal(state.optionsLoading, false)
  assert.equal(state.optionsError, '组织目录暂不可用')
  state.tab = 'major'
  state.openCreate()
  assert.equal(state.form.visible, false)
})

test('required names and invalid numeric inputs are rejected before a create request', async () => {
  const { state } = page()
  state.openCreate()
  await state.submitForm()
  assert.match(state.form.error, /学院名称/)
  state.form.model.collegeName = '验收学院'
  state.form.model.sortOrder = 1.5
  await state.submitForm()
  assert.match(state.form.error, /整数/)
})

const checkedAdjustment = (extra = {}) => ({
  id: 'request', version: 2, status: 'CHECKED', adjustType: 'DISBAND', fromClassNames: '验收班',
  checkResult: { blocked: false, snapshotHash: 'checked-snapshot' }, checkExpiresAt: '2099-09-06T09:00:00', ...extra,
})

test('adjustment paging and filters discard an older list response', async () => {
  const old = deferred()
  let sent
  const { state } = page({ listClassAdjustments: async query => {
    sent = query
    return query.page === 1 ? old.promise : { code: 0, data: { list: [{ id: 'page-2' }], total: 31 } }
  } })
  const pending = state.reloadAdjustments()
  state.adjustments.filters.status = 'CHECKED'
  await state.pageAdjustments({ page: 2, pageSize: 20 })
  old.resolve({ code: 0, data: { list: [{ id: 'page-1' }], total: 40 } })
  await pending
  assert.equal(sent.page, 2)
  assert.equal(sent.status, 'CHECKED')
  assert.equal(state.adjustments.rows[0].id, 'page-2')
  assert.equal(state.adjustments.total, 31)
  state.reloadAdjustments = () => {}
  state.searchAdjustments()
  assert.equal(state.adjustments.page, 1)
})

test('creating an adjustment retains rejected input, then opens the actual precheck result', async () => {
  let payload, prechecked, reject = true
  const { state } = page({
    createClassAdjustment: async body => { payload = body; return reject ? { code: 400, message: '班级已停用' } : { code: 0, data: { id: 'created', status: 'DRAFT', version: 0 } } },
    precheckClassAdjustment: async (id, version) => { prechecked = [id, version]; return { code: 0, data: checkedAdjustment({ id, checkResult: { blocked: true, refs: [{ activeStudentCount: 2 }] } }) } },
    listClassAdjustments: async () => ({ code: 0, data: { list: [], total: 0 } }),
  })
  state.openAdjustCreate()
  Object.assign(state.adjustCreateForm.model, { fromClassIds: ['class-1', 'class-1'], toClassId: 'class-1', reason: '  学期组织调整验收  ' })
  await state.submitAdjustCreate()
  assert.equal(payload, undefined)
  assert.match(state.adjustCreateForm.error, /目标班级/)
  state.adjustCreateForm.model.toClassId = 'class-2'
  await state.submitAdjustCreate()
  assert.equal(state.adjustCreateForm.visible, true)
  assert.equal(state.adjustCreateForm.model.reason, '  学期组织调整验收  ')
  assert.equal(state.adjustCreateForm.error, '班级已停用')
  assert.equal(payload.reason, '学期组织调整验收')
  assert.equal(payload.fromClassIds.length, 1)
  reject = false
  await state.submitAdjustCreate()
  assert.equal(prechecked[0], 'created')
  assert.equal(prechecked[1], 0)
  assert.equal(state.adjustCreateForm.visible, false)
  assert.equal(state.adjustCheckResult.visible, true)
  assert.equal(state.adjustCheckResult.row.checkResult.blocked, true)
  assert.equal(state.busy, false)
})

test('precheck blocks duplicate requests, closing and navigation until the response arrives', async () => {
  const response = deferred()
  let calls = 0, sentVersion, accepted
  const { state, definition } = page({ precheckClassAdjustment: (id, version) => { calls++; sentVersion = version; return response.promise } }, { tab: 'adjust' })
  state.reloadAdjustments = async () => {}
  state.adjustCheckResult.visible = true
  const pending = state.precheckAdjustment(checkedAdjustment())
  await state.precheckAdjustment(checkedAdjustment())
  state.switchTab('class')
  state.closeAdjustResult()
  definition.beforeRouteLeave.call(state, {}, {}, value => { accepted = value })
  assert.equal(calls, 1)
  assert.equal(sentVersion, 2)
  assert.equal(state.tab, 'adjust')
  assert.equal(state.adjustCheckResult.visible, true)
  assert.equal(accepted, false)
  response.resolve({ code: 0, data: checkedAdjustment({ version: 3 }) })
  await pending
  assert.equal(state.adjustCheckResult.row.version, 3)
  assert.equal(state.busy, false)
})

test('execute binds the confirmed version, submits once and requires a fresh check after conflict', async () => {
  const response = deferred()
  let sent, calls = 0
  const { state } = page({ executeClassAdjustment: (id, version) => { calls++; sent = [id, version]; return response.promise } })
  state.reloadAdjustments = async () => {}
  const row = checkedAdjustment()
  state.confirmAdjustAction(row, 'execute')
  row.version = 999
  const pending = state.submitAdjustAction()
  state.closeAdjustAction()
  await state.submitAdjustAction()
  assert.equal(sent[1], 2)
  assert.equal(calls, 1)
  assert.equal(state.adjustActionConfirm.visible, true)
  response.resolve({ code: 409, message: '班级信息已变化，请重新核对' })
  await pending
  assert.equal(state.adjustActionConfirm.needsRecheck, true)
  assert.match(state.adjustActionConfirm.error, /重新核对/)
  await state.submitAdjustAction()
  assert.equal(calls, 1)
  state.closeAdjustAction()
  assert.equal(state.adjustActionConfirm.visible, false)
})

test('executed receipts are shown and organization choices refresh after state changes', async () => {
  let refreshed = 0
  const receipt = checkedAdjustment({ status: 'EXECUTED', version: 3, checkResult: { execution: { changedClassCount: 1, studentMoveCount: 0, classStatus: 'DISBANDED' } } })
  const { state } = page({ executeClassAdjustment: async () => ({ code: 0, data: receipt }) })
  state.reloadAdjustments = async () => {}
  state.loadOptions = async () => { refreshed++ }
  state.confirmAdjustAction(checkedAdjustment(), 'execute')
  await state.submitAdjustAction()
  assert.equal(state.adjustActionConfirm.visible, false)
  assert.equal(state.adjustCheckResult.visible, true)
  assert.equal(state.adjustCheckResult.row.checkResult.execution.changedClassCount, 1)
  assert.match(state.adjustResultMessage(receipt), /已将 1 个来源班级设为已解散/)
  assert.doesNotMatch(state.adjustResultMessage(receipt), /请先处理/)
  assert.match(state.adjustResultMessage({ ...receipt, status: 'CANCELLED' }), /未执行班级变更/)
  assert.equal(refreshed, 1)
})

test('unverified, blocked and expired adjustments cannot execute; split confirmation describes registration only', () => {
  const { state } = page()
  for (const row of [checkedAdjustment({ checkResult: { blocked: false } }), checkedAdjustment({ checkExpiresAt: '2020-01-01T00:00:00Z' }), checkedAdjustment({ status: 'DRAFT' }), checkedAdjustment({ checkResult: { blocked: true, snapshotHash: 'x' } })]) {
    assert.equal(state.isAdjustBlocked(row), true)
    state.confirmAdjustAction(row, 'execute')
    assert.equal(state.adjustActionConfirm.visible, false)
  }
  state.confirmAdjustAction(checkedAdjustment({ adjustType: 'SPLIT' }), 'execute')
  assert.match(state.adjustActionConfirm.message, /仅记录拆班安排/)
  assert.doesNotMatch(state.adjustActionConfirm.message, /将变更相关行政班状态/)
})

test('read-only operators cannot launch, precheck or submit adjustment commands', async () => {
  const { state } = page()
  state.ctx.permissionPatterns = ['academicAffairs.org.view']
  state.openAdjustCreate()
  await state.submitAdjustCreate()
  await state.precheckAdjustment(checkedAdjustment())
  state.confirmAdjustAction(checkedAdjustment(), 'execute')
  await state.submitAdjustAction()
  assert.equal(state.adjustCreateForm.visible, false)
  assert.equal(state.adjustActionConfirm.visible, false)
  assert.equal(state.busy, false)
})

const transferPreview = (target = 'target') => ({
  student: { id: 'student', version: 4 }, fromClassId: 'source', fromClassName: '来源班',
  target: { id: target, version: 8, className: '目标班', studentCount: 21, afterStudentCount: 22, capacity: 20 },
  warnings: ['超出编制'], snapshotHash: 'current-organization-and-count',
})

test('transfer previews cannot apply to another target or a closed editor', async () => {
  const first = deferred(), second = deferred()
  const { state } = page({ previewClassTransfer: ({ targetClassId }) => targetClassId === 'first' ? first.promise : second.promise })
  state.openAdjust({ id: 'student', classId: 'source' })
  state.adjust.targetClassId = 'first'; state.adjust.reason = '同专业班级调整'
  const pending = state.previewTransfer()
  state.adjust.targetClassId = 'second'; state.invalidateTransferPreview()
  const current = state.previewTransfer()
  first.resolve({ code: 0, data: transferPreview('first') })
  await pending
  assert.equal(state.adjust.preview, null)
  assert.equal(state.adjust.previewing, true)
  state.closeAdjust()
  second.resolve({ code: 0, data: transferPreview('second') })
  await current
  assert.equal(state.adjust.visible, false)
  assert.equal(state.adjust.preview, null)
})

test('transfer freezes the confirmed versions, retains rejected input and prevents duplicate saving', async () => {
  const response = deferred()
  let calls = 0, sent
  const { state } = page({ adjustClass: body => { calls++; sent = body; return response.promise } })
  state.openAdjust({ id: 'student', classId: 'source', version: 0 })
  state.adjust.targetClassId = 'target'; state.adjust.reason = '  学期班级归属核对  '
  state.adjust.preview = transferPreview()
  const pending = state.submitAdjust()
  state.closeAdjust()
  await state.submitAdjust()
  assert.equal(calls, 1)
  assert.equal(state.adjust.visible, true)
  assert.equal(sent.expectedVersion, 4)
  assert.equal(sent.expectedTargetVersion, 8)
  assert.equal(sent.expectedSnapshotHash, 'current-organization-and-count')
  assert.equal(sent.reason, '学期班级归属核对')
  response.resolve({ code: 409, message: '目标班级人数已变化，请重新核对' })
  await pending
  assert.equal(state.adjust.preview, null)
  assert.equal(state.adjust.targetClassId, 'target')
  assert.equal(state.adjust.reason, '  学期班级归属核对  ')
  assert.match(state.adjust.error, /重新核对/)
  assert.equal(state.busy, false)
})

test('successful transfer shows server receipt and can open the destination roster', async () => {
  let opened, refreshed = 0
  const receipt = { toClassId: 'actual-target', toClassName: '正式目标班', studentVersion: 5 }
  const { state } = page({ adjustClass: async () => ({ code: 0, data: receipt }) })
  state.reload = () => { refreshed++ }
  state.openStudents = row => { opened = row }
  state.openAdjust({ id: 'student', classId: 'source' })
  state.adjust.targetClassId = 'target'; state.adjust.reason = '同专业班级调整'
  state.adjust.preview = transferPreview()
  await state.submitAdjust()
  assert.equal(state.adjust.receipt.studentVersion, 5)
  assert.equal(state.adjust.visible, true)
  assert.equal(refreshed, 1)
  state.viewTransferredClass()
  assert.equal(opened.id, 'actual-target')
  assert.equal(opened.className, '正式目标班')
  assert.equal(state.adjust.visible, false)
})

test('transfer needs a current preview and a real reason and never exposes a write to read-only users', async () => {
  const { state } = page()
  state.openAdjust({ id: 'student', classId: 'source' })
  state.adjust.targetClassId = 'target'
  await state.previewTransfer()
  assert.match(state.adjust.error, /调整原因/)
  await state.submitAdjust()
  assert.equal(state.adjust.submitting, false)
  state.adjust.preview = transferPreview('different')
  await state.submitAdjust()
  assert.equal(state.adjust.preview, null)
  state.adjust.preview = transferPreview()
  state.ctx.permissionPatterns = ['academicAffairs.org.view']
  await state.submitAdjust()
  await state.previewTransfer()
  assert.equal(state.adjust.submitting, false)
})
