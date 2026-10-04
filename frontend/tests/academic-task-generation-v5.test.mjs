import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { compile } from '@vue/compiler-dom'
import * as Vue from 'vue'
import { renderToString } from 'vue/server-renderer'
import { page, deferred } from './academic-pc-parallel-b-harness.mjs'
import * as teaching from '../src/modules/academicAffairs/constants/teaching.js'
import * as results from '../src/modules/academicAffairs/components/parallel-a/resultState.js'
import { matchPermission } from '../src/config/navPlan.js'
import { academicIdentity } from '../src/modules/academicAffairs/academicFlowContext.js'

const scope = (value = 'TENANT_ALL') => ({ currentRole: { roleCode: 'CUSTOM_ACADEMIC_ROLE' }, dataScope: { scope: value }, permissionPatterns: ['academicAffairs.teachingTask.manage'] })
const batch = { batchId: '9007199254740997', termId: '52', collegeId: '9007199254740993', batchName: '责任学院秋季教学任务', status: 'GENERATED', nextAction: { label: '由开课学院分配教师' } }
function instance(api = {}, extra = {}) {
  return page('AaTaskBatchListView', {
    ...teaching, ...results, matchPermission, academicIdentity,
    currentUserFromToken: () => ({ tenantId: 'school-one', userId: 'teacher-one', currentRoleCode: 'CUSTOM_ACADEMIC_ROLE' }),
    academicAffairsApi: { getTaskBatches: async () => ({ code: 0, data: { list: [], total: 0 } }), ...api },
    ...extra
  }, { ctx: scope() })
}

test('同一身份等值上下文刷新不丢正式回读且释放生成锁', async () => {
  const pending = deferred(); let readbacks = 0
  const { state } = instance({ generateTaskBatch: () => pending.promise }, { teachingTaskWorkbenchApi: { getBatch: async () => { readbacks++; return { code: 0, data: batch } } } })
  state.loading = false; state.gen = { termId: batch.termId, collegeId: batch.collegeId, batchName: batch.batchName }
  const key = state.generationContext, run = state.doGenerate()
  state.ctx = JSON.parse(JSON.stringify(state.ctx))
  assert.equal(state.generationContext, key)
  pending.resolve({ code: 0, data: { batchId: batch.batchId } })
  await run
  assert.equal(readbacks, 1); assert.equal(state.generating, false); assert.equal(state.receipt.pending, false)
})

test('学校和多院生成必须选开课责任学院，缺少学院不发送生成请求', async () => {
  for (const actualScope of ['TENANT_ALL', 'COLLEGE']) {
    let writes = 0
    const { state } = instance({ generateTaskBatch: async () => { writes++ } })
    state.ctx = scope(actualScope)
    state.gen.termId = '52'
    await state.doGenerate()
    assert.equal(writes, 0)
    assert.match(state.genError, /开课责任学院/)
    assert.equal(state.generating, false)
  }
})

test('实际表单复用学院选择器，缺学院禁用生成，办理中冻结学期和学院输入', async () => {
  const source = readFileSync(new URL('../src/modules/academicAffairs/views/AaTaskBatchListView.vue', import.meta.url), 'utf8')
  const template = source.match(/<AppSectionCard v-if="showGen && canManage"[\s\S]*?<\/AppSectionCard>/)[0]
  const render = new Function('Vue', compile(template, { mode: 'function', prefixIdentifiers: true }).code)(Vue)
  const field = { props: ['modelValue', 'disabled', 'placeholder'], setup: props => () => Vue.h('input', { value: props.modelValue, disabled: props.disabled, placeholder: props.placeholder }) }
  const renderForm = generating => renderToString(Vue.createSSRApp({
    data: () => ({ showGen: true, canManage: true, generating, genError: '', gen: { termId: '52', collegeId: '', batchName: '' } }),
    methods: { doGenerate() {} }, render,
    components: { AppSectionCard: { setup: (_, { slots }) => () => Vue.h('section', slots.default?.()) }, AppCollegePicker: field, AppClassPicker: field, AppTermEntityPicker: field, AppButton: { props: ['disabled'], setup: (props, { slots }) => () => Vue.h('button', { disabled: props.disabled }, slots.default?.()) }, AppInlineAlert: { render: () => null } }
  }))
  const idle = await renderForm(false)
  assert.match(idle, /开课责任学院/)
  assert.match(idle, /placeholder="选择负责开课与学院确认的学院"/)
  assert.match(idle, /<button disabled[^>]*>生成并检查/)
  const pending = await renderForm(true)
  assert.match(pending, /<input[^>]*disabled[^>]*placeholder="选择学期"/)
  assert.match(pending, /<input[^>]*disabled[^>]*placeholder="选择负责开课与学院确认的学院"/)
})

test('生成表单使用可选行政班选择器，学院变化清除旧班级', async () => {
  const source = readFileSync(new URL('../src/modules/academicAffairs/views/AaTaskBatchListView.vue', import.meta.url), 'utf8')
  const template = source.match(/<AppSectionCard v-if="showGen && canManage"[\s\S]*?<\/AppSectionCard>/)[0]
  const render = new Function('Vue', compile(template, { mode: 'function', prefixIdentifiers: true }).code)(Vue)
  const field = { props: ['modelValue', 'disabled', 'placeholder'], setup: props => () => Vue.h('input', { value: props.modelValue, disabled: props.disabled, placeholder: props.placeholder }) }
  const renderForm = (collegeId, generating) => renderToString(Vue.createSSRApp({
    data: () => ({ showGen: true, canManage: true, generating, genError: '', gen: { termId: '52', collegeId, classId: '', batchName: '' } }),
    methods: { doGenerate() {} }, render,
    components: { AppSectionCard: { setup: (_, { slots }) => () => Vue.h('section', slots.default?.()) }, AppCollegePicker: field, AppClassPicker: field, AppTermEntityPicker: field, AppButton: { props: ['disabled'], setup: (props, { slots }) => () => Vue.h('button', { disabled: props.disabled }, slots.default?.()) }, AppInlineAlert: { render: () => null } }
  }))
  const noCollege = await renderForm('', false)
  assert.match(noCollege, /行政班（可选）/)
  assert.match(noCollege, /留空按全院生成/)
  assert.match(noCollege, /<input[^>]*disabled[^>]*placeholder="选择行政班，仅补生成该班"/)
  const pending = await renderForm(batch.collegeId, true)
  assert.match(pending, /<input[^>]*disabled[^>]*placeholder="选择行政班，仅补生成该班"/)
  const { state, definition } = instance()
  state.gen.collegeId = batch.collegeId; state.gen.classId = '4666'
  definition.watch['gen.collegeId'].call(state, '99', batch.collegeId)
  assert.equal(state.gen.classId, '')
})

test('未选班保持全院合同，选班仅发送原样字符串，冲突保留班级输入', async () => {
  const writes = []
  const { state } = instance({ generateTaskBatch: async body => { writes.push(body); return { code: 409001, message: '目标批次已存在' } } })
  state.gen = { termId: '52', collegeId: batch.collegeId, classId: '', batchName: '全院任务' }
  await state.doGenerate()
  assert.equal(Object.hasOwn(writes[0], 'classId'), false)
  state.gen.classId = '9007199254740993'
  await state.doGenerate()
  assert.equal(writes[1].classId, '9007199254740993')
  assert.equal(state.gen.classId, '9007199254740993')
  assert.equal(state.receipt.status, '事实已变化，保留输入')
})

test('仅真实单院范围且正式分页确认唯一学院时回填，不从不完整候选猜归属', async () => {
  for (const [actualScope, total, rows, expected, calls] of [
    ['COLLEGE', 1, [{ id: batch.collegeId }], batch.collegeId, 1],
    ['COLLEGE', 2, [{ id: batch.collegeId }, { id: '9' }], '', 1],
    ['COLLEGE', undefined, [{ id: batch.collegeId }], '', 1],
    ['TENANT_ALL', 1, [{ id: batch.collegeId }], '', 0]
  ]) {
    let reads = 0
    const { state } = instance({}, { academicAffairsOrgApi: { listColleges: async params => { reads++; assert.equal(params.pageSize, 2); return { code: 0, data: { list: rows, total } } } } })
    state.ctx = scope(actualScope); state.showGen = true
    await state.prefillCollege()
    assert.equal(state.gen.collegeId, expected)
    assert.equal(reads, calls)
  }
})

test('学院回填迟到不得覆盖手动选择、变更身份或关闭后的表单', async () => {
  for (const change of ['selected', 'identity', 'closed']) {
    const response = deferred()
    const { state } = instance({}, { academicAffairsOrgApi: { listColleges: () => response.promise } })
    state.ctx = scope('COLLEGE'); state.showGen = true
    const load = state.prefillCollege()
    if (change === 'selected') state.gen.collegeId = '99'
    if (change === 'identity') state.ctx = scope('TENANT_ALL')
    if (change === 'closed') state.showGen = false
    response.resolve({ code: 0, data: { list: [{ id: batch.collegeId }], total: 1 } }); await load
    assert.equal(state.gen.collegeId, change === 'selected' ? '99' : '')
  }
})

test('生成提交字符串学期和学院，同一正式批次学院匹配才确认成功', async () => {
  let body, reloads = 0
  const { state } = instance({ generateTaskBatch: async value => { body = value; return { code: 0, data: { batchId: batch.batchId } } } }, { teachingTaskWorkbenchApi: { getBatch: async id => { assert.equal(id, batch.batchId); return { code: 0, data: batch } } } })
  state.gen = { termId: 52, collegeId: batch.collegeId, batchName: '正式学院任务' }; state.showGen = true
  state.load = async () => { reloads++ }
  await state.doGenerate()
  assert.equal(body.termId, '52')
  assert.equal(body.collegeId, batch.collegeId)
  assert.equal(body.batchName, '正式学院任务')
  assert.equal(state.receipt.pending, false)
  assert.equal(state.receipt.next, '由开课学院分配教师')
  assert.equal(state.showGen, false)
  assert.equal(state.generating, false)
  assert.equal(reloads, 1)
})

test('回读其他学院时不冒充生成成功，保留原学院选择与待核实回执', async () => {
  const { state } = instance({ generateTaskBatch: async () => ({ code: 0, data: { batchId: batch.batchId } }) }, { teachingTaskWorkbenchApi: { getBatch: async () => ({ code: 0, data: { ...batch, collegeId: '99' } }) } })
  state.gen = { termId: '52', collegeId: batch.collegeId, batchName: '' }; state.showGen = true
  await state.doGenerate()
  assert.equal(state.receipt.pending, true)
  assert.equal(state.gen.collegeId, batch.collegeId)
  assert.equal(state.showGen, true)
})

test('切身份后的迟到生成响应不触发新身份回读，也不恢复旧学院或成功回执', async () => {
  const response = deferred(); let reads = 0
  const { state, definition } = instance({ generateTaskBatch: () => response.promise }, { teachingTaskWorkbenchApi: { getBatch: async () => { reads++; return { code: 0, data: batch } } } })
  state.gen = { termId: '52', collegeId: batch.collegeId, batchName: '' }
  const generate = state.doGenerate()
  state.ctx = scope('COLLEGE'); definition.watch.generationContext.call(state)
  response.resolve({ code: 0, data: { batchId: batch.batchId } }); await generate
  assert.equal(reads, 0)
  assert.equal(state.receipt, null)
  assert.equal(state.gen.collegeId, '')
  assert.equal(state.generating, false)
})

test('切身份或卸载后的迟到正式回读不写入新表单', async () => {
  for (const change of ['identity', 'unmount']) {
    const readback = deferred(), started = deferred()
    const { state, definition } = instance({ generateTaskBatch: async () => ({ code: 0, data: { batchId: batch.batchId } }) }, { teachingTaskWorkbenchApi: { getBatch: () => { started.resolve(); return readback.promise } } })
    state.gen = { termId: '52', collegeId: batch.collegeId, batchName: '' }
    const generate = state.doGenerate(); await started.promise
    if (change === 'identity') { state.ctx = scope('COLLEGE'); definition.watch.generationContext.call(state) }
    else definition.beforeUnmount.call(state)
    state.receipt = null
    readback.resolve({ code: 0, data: batch }); await generate
    assert.equal(state.receipt, null)
  }
})
