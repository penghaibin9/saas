import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'
import { parse, compileTemplate } from '@vue/compiler-sfc'

const { descriptor } = parse(readFileSync(new URL('../src/modules/system/views/SystemRoleAssignmentView.vue', import.meta.url), 'utf8'))
function view(read, mutations = {}, candidates = async () => ({ code: 0, data: { items: [], total: 0 } })) {
  const env = { schoolIamApi: { roleMemberCandidates: candidates }, systemApi: { listRoleAssignments: read, ...mutations }, roleDisplayLabel: value => value, toast: { success() {}, error() {} },
    ModulePageShell: {}, ModuleToolbar: {}, DataTable: {}, StatusTag: {}, LoadingState: {}, ErrorState: {}, EmptyState: {}, AppConfirmDialog: {} }
  vm.runInNewContext(descriptor.script.content.replace(/^import .*$/gm, '').replace('export default', 'globalThis.component ='), env)
  const component = env.component
  const ctx = { ...component.data(), ctx: {} }
  for (const [key, value] of Object.entries(component.methods)) ctx[key] = value.bind(ctx)
  for (const [key, value] of Object.entries(component.computed)) Object.defineProperty(ctx, key, { get: value.bind(ctx) })
  ctx.loading = false
  return ctx
}
const result = (id, total = 102) => ({ code: 0, data: { list: [{ assignmentId: id }], total, summary: {} } })

test('assignment pagination template compiles', () => {
  assert.deepEqual(compileTemplate({ source: descriptor.template.content, filename: 'Assignments.vue', id: 'assignments' }).errors, [])
})
test('later pages load from the server and preserve the selected category', async () => {
  let requested
  const ctx = view(async params => { requested = params; return result('second-page') })
  ctx.total = 102; ctx.bucket = 'UNKNOWN_SOURCE'
  await ctx.changePage(2)
  assert.equal(requested.page, 2); assert.equal(requested.pageSize, 50)
  assert.equal(requested.bucket, 'UNKNOWN_SOURCE')
  assert.equal(ctx.rows[0].assignmentId, 'second-page'); assert.equal(ctx.pageCount, 3)
})
test('custom role uses its school-maintained name instead of an unknown code label', () => {
  assert.match(descriptor.template.content, /row\.roleName \|\| roleLabel\(row\.roleCode\)/)
})
test('failed page leaves no stale actionable rows and retries the same page', async () => {
  let fail = true
  const ctx = view(async () => { if (fail) throw new Error('网络中断'); return result('recovered') })
  ctx.total = 102; ctx.rows = [{ assignmentId: 'old-page' }]
  await ctx.changePage(2)
  assert.equal(ctx.rows.length, 0); assert.match(ctx.error, /网络中断/); assert.equal(ctx.loading, false)
  fail = false; await ctx.load()
  assert.equal(ctx.page, 2); assert.equal(ctx.rows[0].assignmentId, 'recovered')
})
test('late old-category response cannot replace the new first page', async () => {
  let finish
  const ctx = view(() => new Promise(resolve => { finish = resolve }))
  ctx.page = 3
  const old = ctx.load(); const finishOld = finish
  ctx.pickBucket('EXPIRING_SOON')
  finish(result('new-category')); await Promise.resolve(); await Promise.resolve()
  finishOld(result('old-category')); await old
  assert.equal(ctx.page, 1); assert.equal(ctx.rows[0].assignmentId, 'new-category')
})
test('invalid page results fail explicitly and mutation blocks navigation', async () => {
  let calls = 0
  const ctx = view(async () => { calls++; return { code: 0, data: { list: [] } } })
  ctx.total = 102; ctx.submitting = true
  await ctx.changePage(2); ctx.pickBucket('UNKNOWN_SOURCE'); ctx.switchTab('identities')
  assert.equal(calls, 0); assert.equal(ctx.page, 1); assert.equal(ctx.tab, 'members')
  ctx.submitting = false; await ctx.load()
  assert.match(ctx.error, /分页信息不完整/)
})

test('legacy registration submits the exact link ID/version without granting permissions', async () => {
  let sent
  const ctx = view(async () => result('registered'), { registerLegacyRoleAssignment: async (id, payload) => {
    sent = { id, payload }; return { code: 0, data: { id: '81' } }
  } })
  ctx.ctx = { permissionPatterns: ['systemAdmin.user.assign'] }
  ctx.ask('register', { userRoleId: '9007199254740999', version: 7, roleCode: 'STAFF' })
  await ctx.submit({ reason: '核对既有职责后补登记' })
  assert.equal(sent.id, '9007199254740999'); assert.equal(sent.payload.expectedVersion, 7)
  assert.equal(sent.payload.permissionCodes, undefined)
  assert.equal(ctx.dialogOpen, false); assert.equal(ctx.submitting, false)
})

test('conflict retains the dialog, recipient and original version, and prevents stale resubmission', async () => {
  let calls = 0
  const ctx = view(async () => result('latest'), { transferRoleAssignment: async () => { calls++; return { code: 1, bizCode: 'DATA_CONFLICT' } } })
  ctx.ctx = { permissionPatterns: ['systemAdmin.user.assign'] }
  ctx.ask('transfer', { assignmentId: '18', version: 3, realName: '测试老师' })
  await Promise.resolve(); await Promise.resolve()
  ctx.recipientsError = ''; ctx.recipientsLoading = false
  ctx.recipient = { id: '9007199254740999' }; ctx.transferTo = '9007199254740999'
  await ctx.submit({ reason: '工作安排转交' })
  assert.equal(ctx.dialogOpen, true); assert.equal(ctx.pendingRow.version, 3)
  assert.equal(ctx.transferTo, '9007199254740999'); assert.equal(ctx.submitting, false)
  assert.match(ctx.mutationError, /核对最新结果/)
  await ctx.submit({ reason: '工作安排转交' }); assert.equal(calls, 1)
  await ctx.returnToLatest(); assert.equal(ctx.dialogOpen, false); assert.equal(ctx.rows[0].assignmentId, 'latest')
})

test('request interruption releases busy state but requires a read before repeating the action', async () => {
  let calls = 0
  const ctx = view(async () => result('latest'), { revokeRoleAssignment: async () => { calls++; throw new Error('连接中断') } })
  ctx.ctx = { permissionPatterns: ['systemAdmin.user.assign'] }
  ctx.ask('revoke', { assignmentId: '18', version: 3 })
  await ctx.submit({ reason: '本学期职责结束' })
  assert.equal(ctx.submitting, false); assert.equal(ctx.dialogOpen, true)
  assert.equal(ctx.requiresRecheck, true); assert.match(ctx.mutationError, /连接中断/)
  await ctx.submit({ reason: '本学期职责结束' }); assert.equal(calls, 1)
})

test('in-flight operation blocks cancel and duplicate submission; validation rejection keeps editable draft', async () => {
  let finish, calls = 0
  const ctx = view(async () => result('latest'), { reviewRoleAssignment: () => { calls++; return new Promise(resolve => { finish = resolve }) } })
  ctx.ask('review', { assignmentId: '18', version: 3 }); ctx.reviewTerm = '2026-2027-1'
  const running = ctx.submit({ reason: '继续承担相应工作' })
  ctx.setDialogVisible(false); await ctx.submit({ reason: '继续承担相应工作' })
  assert.equal(ctx.dialogOpen, true); assert.equal(calls, 1)
  finish({ code: 1, bizCode: 'VALIDATION_ERROR', message: '请核对学期' }); await running
  assert.equal(ctx.requiresRecheck, false); assert.equal(ctx.reviewTerm, '2026-2027-1')
  assert.equal(ctx.mutationError, '请核对学期'); assert.equal(ctx.submitting, false)
})


test('recipient search uses paged role candidates and selected string ID in the transfer', async () => {
  let query, sent
  const person = { id: '9007199254740999', name: '接手老师', loginName: 'test_teacher', status: 'ACTIVE' }
  const ctx = view(async () => result('latest'), { transferRoleAssignment: async (id, payload) => { sent = { id, payload }; return { code: 0 } } }, async (roleId, params) => {
    query = { roleId, params }; return { code: 0, data: { items: [person], total: 1 } }
  })
  ctx.ctx = { permissionPatterns: ['systemAdmin.user.assign'] }
  ctx.ask('transfer', { assignmentId: '18', roleId: '109', userId: '21', version: 3 })
  ctx.recipientKeyword = 'test_teacher'; await ctx.searchRecipients()
  assert.equal(query.roleId, '109'); assert.equal(query.params.keyword, 'test_teacher'); assert.equal(query.params.pageSize, 10)
  ctx.selectRecipient(ctx.recipients[0]); await ctx.submit({ reason: '职责交接测试原因' })
  assert.equal(sent.payload.toUserId, person.id); assert.equal(sent.payload.expectedVersion, 3)
})

test('new recipient search clears selection and ignores an older late result', async () => {
  const pending = []
  const ctx = view(async () => result('latest'), {}, () => new Promise(resolve => pending.push(resolve)))
  ctx.dialogOpen = true; ctx.pendingRow = { roleId: '109', userId: '21' }
  const older = ctx.loadRecipients(2)
  ctx.recipient = { id: '45' }; ctx.transferTo = '45'; ctx.recipientKeyword = '新老师'
  const newer = ctx.searchRecipients()
  pending[1]({ code: 0, data: { items: [{ id: '46', status: 'ACTIVE' }], total: 1 } }); await newer
  pending[0]({ code: 0, data: { items: [{ id: '47', status: 'ACTIVE' }], total: 20 } }); await older
  assert.equal(ctx.recipient, null); assert.equal(ctx.transferTo, '')
  assert.equal(ctx.recipients[0].id, '46'); assert.equal(ctx.recipientPage, 1)
})

test('candidate lookup failure exposes error and never allows a typed ID to transfer', async () => {
  let sent = false
  const ctx = view(async () => result('latest'), { transferRoleAssignment: async () => { sent = true } }, async () => ({ code: 1, message: '候选查询无权限' }))
  ctx.ctx = { permissionPatterns: ['systemAdmin.user.assign'] }
  ctx.dialogOpen = true; ctx.pendingAction = 'transfer'; ctx.pendingRow = { roleId: '109' }
  await ctx.loadRecipients(1); ctx.transferTo = '45'
  await ctx.submit({ reason: '职责交接测试原因' })
  assert.equal(ctx.recipientsError, '候选查询无权限'); assert.equal(sent, false)
})
