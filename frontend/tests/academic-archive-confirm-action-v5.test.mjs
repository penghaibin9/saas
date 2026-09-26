import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { compile } from '@vue/compiler-dom'
import * as Vue from 'vue'
import { renderToString } from 'vue/server-renderer'
import { page, deferred } from './academic-pc-parallel-b-harness.mjs'
import * as registry from '../src/modules/academicAffairs/config/academicFlowRegistry.js'
import { gradeError } from '../src/modules/academicAffairs/views/parallel-c/grade-review.js'

const domains = ['STUDENT_STATUS', 'REGISTRATION', 'STATUS_CHANGE', 'PROGRAM', 'TEACHING_TASK', 'SCHEDULE', 'SELECTION', 'EXAM', 'GRADE', 'MAKEUP', 'EVALUATION', 'TEXTBOOK', 'GRADUATION']
const ok = data => ({ code: 0, data })
const batch = (extra = {}) => ({ batchId: '9007199254740993', batchName: '本学期学校归档', status: 'READY', scopeType: 'TENANT_ALL', missingCount: 0, items: domains.map(domain => ({ domain, result: 'PASS' })), confirmAction: { allowed: true, reason: '' }, ...extra })
const deniedAction = { allowed: false, reason: '当前学校归档责任任职已失效，请联系校教务处核对。' }
function instance(api = {}) {
  const result = page('AaArchiveConsoleView', { ...registry, gradeError, academicAffairsArchiveApi: api }, {
    ctx: { currentRole: { roleCode: 'CUSTOM_SCHOOL_ROLE' }, dataScope: { scope: 'TENANT_ALL' }, permissionPatterns: ['academicAffairs.archive.manage'], permissionVersion: '1' }
  })
  result.state.current = batch(); result.state.items = result.state.current.items
  result.state.load = async () => {}
  return result
}

test('确认归档只消费服务端严格许可，角色名或管理权限本身不能代替责任许可', async () => {
  for (const confirmAction of [undefined, null, {}, deniedAction, { allowed: 'true' }, { allowed: 1 }]) {
    let reads = 0
    const { state } = instance({ getBatch: async () => { reads++; return ok(batch()) } })
    state.current = batch({ confirmAction })
    await state.doConfirm()
    assert.equal(state.canConfirmArchive, false); assert.equal(state.confirmVisible, false); assert.equal(reads, 0)
    assert.match(state.confirmError, /归档|任职/)
  }
  const { state } = instance()
  assert.equal(state.canConfirmArchive, true)
  state.ctx = { ...state.ctx, dataScope: { scope: 'COLLEGE' } }
  assert.equal(state.canConfirmArchive, false)
})

test('打开确认框前同单回读撤回许可或缺字段，只显示原因且不打开对话框', async () => {
  for (const confirmAction of [deniedAction, undefined]) {
    let writes = 0
    const { state } = instance({ getBatch: async id => { assert.equal(id, '9007199254740993'); return ok(batch({ confirmAction })) }, confirm: async () => { writes++ } })
    await state.doConfirm()
    assert.equal(state.confirmVisible, false); assert.equal(state.pendingAction, null); assert.equal(state.actionBusy, false)
    assert.equal(state.pendingCommand, null); assert.equal(writes, 0)
    assert.match(state.confirmError, confirmAction ? /责任任职已失效/ : /尚未取得/)
  }
})

test('打开确认框前网络错误或回读错单，丢弃缓存许可且保留可见错误', async () => {
  for (const outcome of ['error', 'wrong-object']) {
    const { state } = instance({ getBatch: async () => { if (outcome === 'error') throw new Error('读取中断'); return ok(batch({ batchId: 'another' })) } })
    await state.doConfirm()
    assert.equal(state.confirmVisible, false); assert.equal(state.canConfirmArchive, false)
    assert.ok(state.confirmError); assert.equal(state.actionBusy, false); assert.equal(state.pendingCommand, null)
  }
})

test('开框后发送前再次核验同单责任许可，撤权不写并使确认框停止确认', async () => {
  let reads = 0, writes = 0
  const { state } = instance({ getBatch: async () => ok(batch({ confirmAction: ++reads === 1 ? { allowed: true } : deniedAction })), confirm: async () => { writes++ } })
  await state.doConfirm()
  assert.equal(state.confirmVisible, true); assert.equal(reads, 1)
  const message = state.confirmMessage
  await state.onConfirm()
  assert.equal(reads, 2); assert.equal(writes, 0); assert.equal(state.canConfirmArchive, false)
  assert.equal(state.confirmVisible, true); assert.equal(state.confirmMessage, message)
  assert.match(state.confirmError, /责任任职已失效/); assert.equal(state.pendingCommand, null)
  await state.onConfirm(); assert.equal(reads, 2); assert.equal(writes, 0)
})

test('有效责任账号仍沿原确认命令，只有正式写回执及同单十三域归档回读才成功', async () => {
  let reads = 0, writes = 0
  const { state } = instance({
    getBatch: async id => { assert.equal(id, '9007199254740993'); reads++; return ok(batch(writes ? { status: 'ARCHIVED', confirmAction: { allowed: false, reason: '本批次已归档' } } : {})) },
    confirm: async (id, force) => { assert.equal(id, '9007199254740993'); assert.equal(force, false); writes++; return ok({ batchId: id }) }
  })
  await state.doConfirm(); await state.onConfirm()
  assert.equal(reads, 3); assert.equal(writes, 1); assert.equal(state.current.status, 'ARCHIVED')
  assert.equal(state.pendingCommand, null); assert.equal(state.confirmVisible, false); assert.equal(state.actionBusy, false)
  assert.equal(state.actionNotice, '已核对正式十三域归档状态。')
})

test('已发确认回执未知时保留原pendingCommand，刷新观察不当成功且不重放写', async () => {
  let writes = 0
  const { state } = instance({
    getBatch: async () => ok(batch(writes ? { status: 'ARCHIVED', confirmAction: { allowed: false, reason: '本批次已归档' } } : {})),
    confirm: async () => { writes++; throw new Error('确认回执连接中断') }
  })
  await state.doConfirm(); await state.onConfirm()
  assert.equal(writes, 1); assert.equal(state.pendingCommand.kind, 'confirm'); assert.equal(state.pendingCommand.sent, true)
  assert.match(state.actionNotice, /不能确认本次操作完成/)
  await state.selectAfterAction({ batchId: '9007199254740993' })
  assert.equal(state.current.status, 'ARCHIVED'); assert.ok(state.pendingCommand)
  await state.onConfirm(); await state.doConfirm(); assert.equal(writes, 1)
})

test('确认前正式拒绝清旧数据并保持可见拒绝原因，不误显示空批次成功', async () => {
  const { state } = instance({ getBatch: async () => ({ code: 403001, message: '当前账号无归档办理权限' }) })
  state.rows = [batch()]
  await state.doConfirm()
  assert.equal(state.current, null); assert.equal(state.rows.length, 0); assert.equal(state.confirmVisible, false)
  assert.match(state.confirmError, /无权办理/)
})

test('责任恢复后只读重新核对可清除旧拒绝提示，不发送归档命令', async () => {
  let reads = 0, writes = 0
  const { state } = instance({ getBatch: async () => { reads++; return ok(batch()) }, confirm: async () => { writes++ } })
  state.current.confirmAction = deniedAction; state.confirmError = deniedAction.reason
  await state.refreshCurrentFromServer()
  assert.equal(reads, 1); assert.equal(writes, 0); assert.equal(state.canConfirmArchive, true); assert.equal(state.confirmError, '')
})

test('身份、权限版本、路径和卸载失效后的迟到许可不打开确认框', async () => {
  for (const change of ['identity', 'permissions', 'route', 'unmount']) {
    const pending = deferred()
    const { state, definition } = instance({ getBatch: () => pending.promise })
    const opening = state.doConfirm()
    if (change === 'identity') { state.ctx = { ...state.ctx, currentRole: { roleCode: 'OTHER' } }; state.clearPrivate() }
    if (change === 'permissions') { state.ctx.permissionVersion = '2'; state.clearPrivate() }
    if (change === 'route') { state.$route.fullPath = '/other'; state.syncRoute() }
    if (change === 'unmount') definition.beforeUnmount.call(state)
    pending.resolve(ok(batch())); await opening
    assert.equal(state.confirmVisible, false); assert.equal(state.pendingAction, null); assert.equal(state.actionBusy, false)
  }
})

test('发送前读取失败不沿用缓存许可，原确认内容保持', async () => {
  let reads = 0, writes = 0
  const { state } = instance({ getBatch: async () => { if (++reads === 1) return ok(batch()); throw new Error('归档权限读取失败') }, confirm: async () => { writes++ } })
  await state.doConfirm(); const message = state.confirmMessage
  await state.onConfirm()
  assert.equal(writes, 0); assert.equal(state.canConfirmArchive, false); assert.ok(state.confirmError)
  assert.equal(state.confirmMessage, message); assert.equal(state.pendingCommand, null); assert.equal(state.actionBusy, false)
})

test('真实按钮与对话框模板缺许可时禁用，原因及重新核对入口可见', async () => {
  const source = readFileSync(new URL('../src/modules/academicAffairs/views/AaArchiveConsoleView.vue', import.meta.url), 'utf8')
  const template = source.match(/<div v-if="!isCollegeScope" class="aaar-head">[\s\S]*?(?=<div v-if="!isCollegeScope \|\| current.archivedAt")/)[0]
  const dialogTemplate = source.match(/<AppConfirmDialog[\s\S]*?<\/AppConfirmDialog>/)[0]
  for (const snippet of [template, dialogTemplate]) {
    const render = new Function('Vue', compile(snippet, { mode: 'function', prefixIdentifiers: true }).code)(Vue)
    const { state } = instance()
    state.current.confirmAction = deniedAction; state.confirmVisible = true; state.confirmKind = 'confirm'; state.confirmTitle = '确认归档'
    delete state.$route; delete state.$router
    const app = Vue.createSSRApp({ render, setup: () => state, components: {
      AppButton: { props: ['disabled'], setup: (props, { slots }) => () => Vue.h('button', { disabled: props.disabled }, slots.default?.()) },
      AppInlineAlert: { props: ['description'], setup: props => () => Vue.h('p', props.description) },
      AppConfirmDialog: { props: ['confirmDisabled'], setup: (props, { slots }) => () => Vue.h('section', [Vue.h('button', { disabled: props.confirmDisabled }, '确认归档'), slots.default?.()]) }
    } })
    const html = await renderToString(app)
    assert.match(html, /<button disabled[^>]*>确认归档/)
    assert.match(html, /当前学校归档责任任职已失效/)
    if (snippet === template) assert.match(html, /重新核对归档权限/)
  }
})
