import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import { employmentView } from '../src/modules/internship/services/employmentPresentation.mjs'

const batchId = '9007199254740993001'
const initial = () => ({ batchId, version: '1', expectedVersion: 3, nodes: [{ type: 'GUIDE', roleCode: 'INTERN_MENTOR', userId: '' }] })
const options = { roles: [{ code: 'INTERN_MENTOR', name: '实习指导教师', baseRole: 'INTERN_MENTOR' }, { code: 'SCHOOL_ADMIN', name: '学校管理员', baseRole: 'SCHOOL_ADMIN' }], assignees: [{ id: '9007199254740993002', name: '合成承办人', roleCodes: ['SCHOOL_ADMIN'] }] }
const deferred = () => { let resolve; const promise = new Promise(done => { resolve = done }); return { promise, resolve } }
function page(overrides = {}) {
  const source = fs.readFileSync(new URL('../src/modules/internship/views/InternshipLeavePolicyView.vue', import.meta.url), 'utf8')
  const script = source.match(/<script>([\s\S]*?)<\/script>/)[1].replace(/^import[^\n]+\n/gm, '').replace('export default', 'return')
  const store = { selectedBatchId: batchId }
  const api = { options: async () => options, read: async () => initial(), preview: async () => ({ total: 1, errorCount: 0, canPublish: true, items: [] }), publish: async () => ({ version: '2', expectedVersion: 4, checkedStudents: 1 }), ...overrides }
  const names = [...script.matchAll(/components: \{([^}]+)\}/g)][0][1].split(',').map(value => value.trim())
  const deps = { ...Object.fromEntries(names.map(name => [name, {}])), leavePolicyApi: api, useInternshipBatchStore: () => store, canCode: (ctx, code) => !(ctx.denied || []).includes(code), normalizeUiError: () => ({ userMessage: '操作未完成，请重试' }) }
  const component = new Function(...Object.keys(deps), script)(...Object.values(deps))
  const vm = { ...component.data(), ctx: { ctxKey: 'school:role', denied: [] } }
  for (const [name, method] of Object.entries(component.methods)) vm[name] = method.bind(vm)
  for (const [name, getter] of Object.entries(component.computed)) Object.defineProperty(vm, name, { get: getter.bind(vm) })
  return { vm, component, store, api }
}

test('请假规则使用当前批次与大整数标识，校级承办人只从授权选项选择', async () => {
  const requested = [], p = page({ read: async id => { requested.push(id); return initial() } })
  await p.vm.load()
  assert.deepEqual(requested, [batchId]); assert.equal(p.vm.policy.expectedVersion, 3)
  assert.equal(p.vm.rolesFor({ type: 'SCHOOL' })[0].code, 'SCHOOL_ADMIN')
  assert.equal(p.vm.assigneesFor({ roleCode: 'SCHOOL_ADMIN' })[0].id, '9007199254740993002')
  assert.deepEqual(p.vm.assigneesFor({ roleCode: 'UNAUTHORIZED' }), [])
})

test('未选批次或缺少读取权限时不请求配置', async () => {
  let calls = 0; const p = page({ read: async () => { calls++; return initial() } })
  p.store.selectedBatchId = ''; await p.vm.load(); assert.equal(calls, 0)
  p.store.selectedBatchId = batchId; p.vm.ctx.denied = ['internship.leave.policy.view']; await p.vm.load(); assert.equal(calls, 0)
})

test('只读身份不能预览或发布，未完成责任人核对也不能发布', async () => {
  let checks = 0, writes = 0; const p = page({ preview: async () => { checks++ }, publish: async () => { writes++ } })
  await p.vm.load(); p.vm.reason = '合成规则调整原因'; await p.vm.publish(); assert.equal(writes, 0)
  p.vm.ctx.denied = ['internship.leave.policy.manage']; p.vm.preview = { canPublish: true }; await p.vm.check(); await p.vm.publish()
  assert.equal(checks, 0); assert.equal(writes, 0)
})

test('配置切批次后迟到读取不能覆盖新规则', async () => {
  const wait = deferred(), p = page({ read: id => id === batchId ? wait.promise : Promise.resolve({ ...initial(), batchId: id, version: '5' }) })
  const old = p.vm.load(); p.store.selectedBatchId = '9007199254740993009'; await p.vm.load()
  wait.resolve(initial()); await old; assert.equal(p.vm.policy.batchId, p.store.selectedBatchId); assert.equal(p.vm.policy.version, '5')
})

test('审批步骤变化废弃旧责任人预览，不能使用旧核对结果发布', async () => {
  const wait = deferred(), p = page({ preview: () => wait.promise }); await p.vm.load()
  const checking = p.vm.check(); p.vm.nodes.push({ type: 'SCHOOL', roleCode: 'SCHOOL_ADMIN', userId: '9007199254740993002' }); p.vm.invalidatePreview()
  wait.resolve({ total: 1, errorCount: 0, canPublish: true, items: [] }); await checking
  assert.equal(p.vm.preview, null); assert.equal(p.vm.checking, false)
})

test('发布传原版本并防重复，成功后要求下次重新核对', async () => {
  const wait = deferred(), writes = [], p = page({ publish: (...args) => { writes.push(args); return wait.promise } })
  await p.vm.load(); await p.vm.check(); p.vm.reason = '合成审批责任调整'
  const work = p.vm.publish(); await p.vm.publish(); assert.equal(writes.length, 1)
  assert.deepEqual(writes[0], [batchId, { nodes: initial().nodes, expectedVersion: 3, reason: '合成审批责任调整' }])
  wait.resolve({ version: '2', expectedVersion: 4, checkedStudents: 1 }); await work
  assert.equal(p.vm.policy.expectedVersion, 4); assert.match(p.vm.receipt, /1 位学生/); assert.equal(p.vm.preview, null)
})

test('规则冲突保留输入，显式核对新版并重做预览后才能继续', async () => {
  const p = page({ publish: async () => { throw { httpStatus: 409 } } })
  await p.vm.load(); await p.vm.check(); p.vm.reason = '本次未保存的发布原因'; p.vm.nodes.push({ type: 'SCHOOL', roleCode: 'SCHOOL_ADMIN', userId: '9007199254740993002' })
  const draft = JSON.stringify(p.vm.nodes); p.api.read = async () => ({ ...initial(), expectedVersion: 8, version: '6' })
  await p.vm.publish()
  assert.equal(JSON.stringify(p.vm.nodes), draft); assert.equal(p.vm.reason, '本次未保存的发布原因'); assert.equal(p.vm.policy.expectedVersion, 3); assert.equal(p.vm.conflict.expectedVersion, 8)
  p.vm.acknowledgeConflict(); assert.equal(p.vm.policy.expectedVersion, 8); assert.equal(p.vm.preview, null); assert.equal(JSON.stringify(p.vm.nodes), draft)
})

test('就业实习预审通过不冒充正式就业审批完成', () => {
  assert.equal(employmentView({ status: 'APPROVED' }).statusLabel, '待就业老师审批')
  assert.equal(employmentView({ status: 'APPROVED', formalSubmission: { status: 'PENDING' } }).statusLabel, '待就业老师审批')
  assert.equal(employmentView({ status: 'APPROVED', formalSubmission: { status: 'APPROVED', empStudentId: '9007199254740993010' } }).statusLabel, '就业审批已通过')
  assert.equal(employmentView({ status: 'APPROVED', formalSubmission: { status: 'RETURNED' } }).statusLabel, '就业审批已退回')
  assert.equal(employmentView({ status: 'APPROVED', formalSubmission: { status: 'REJECTED' } }).statusLabel, '就业审批未通过')
})

test('未取得身份权限时操作关闭，包括开发环境', () => {
  const source = fs.readFileSync(new URL('../src/modules/internship/composables/permission.js', import.meta.url), 'utf8').replace(/^import[^\n]+\n/gm, '').replace(/export default[^\n]*/g, '').replace(/export /g, '')
  const { allowByPatterns } = new Function('matchPermission', source + '\nreturn {allowByPatterns}')((patterns, code) => patterns.includes(code))
  for (const permissions of [null, undefined, {}]) assert.equal(allowByPatterns(permissions, 'internship.leave.policy.manage'), false)
  assert.equal(allowByPatterns(['internship.leave.policy.view'], 'internship.leave.policy.manage'), false)
  assert.equal(allowByPatterns(['internship.leave.policy.manage'], 'internship.leave.policy.manage'), true)
})
