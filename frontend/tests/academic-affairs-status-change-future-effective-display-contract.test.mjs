import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'
import { createSSRApp, h } from 'vue'
import { renderToString } from 'vue/server-renderer'
import { parse } from '@vue/compiler-sfc'
import { CHANGE_FLOW_NODES, TYPE_LABEL, STATUS_LABEL, NODE_LABEL } from '../src/modules/academicAffairs/constants/status-change.js'
import { ACADEMIC_STUDENT_STATUS_LABELS } from '../src/modules/academicAffairs/config/academicStudentLabels.js'
import { decisionVersion, nodePermission, sameDecision, matchesDecisionResult } from '../src/modules/academicAffairs/views/parallel-c/status-change-review.js'

const constantsUrl = new URL('../src/modules/academicAffairs/constants/status-change.js', import.meta.url)
const detailUrl = new URL('../src/modules/academicAffairs/views/AaStatusChangeDetailView.vue', import.meta.url)
const reviewUrl = new URL('../src/modules/academicAffairs/views/parallel-c/StatusChangeReview.vue', import.meta.url)

async function renderReview(change) {
  const { descriptor } = parse(await readFile(reviewUrl, 'utf8'))
  const script = descriptor.script.content.replace(/^import .*$/gm, '')
    .replace(/components\s*:\s*\{[^}]*\},?/, '').replace('export default', 'return')
  const deps = { TYPE_LABEL, STATUS_LABEL, NODE_LABEL, ACADEMIC_STUDENT_STATUS_LABELS,
    decisionVersion, nodePermission, sameDecision, matchesDecisionResult,
    currentUserFromToken: () => ({}), matchPermission: () => true }
  const component = new Function(...Object.keys(deps), script)(...Object.values(deps))
  const app = createSSRApp({ ...component, template: descriptor.template.content,
    components: { AppConfirmDialog: { render: () => h('div') } } }, {
    change, ctx: { currentRole: {}, dataScope: {}, permissionPatterns: ['*'] }
  })
  return renderToString(app)
}

async function detailState(change) {
  const { descriptor } = parse(await readFile(detailUrl, 'utf8'))
  const script = descriptor.script.content.replace(/^import .*$/gm, '')
    .replace(/components\s*:\s*\{[^}]*\},?/, '').replace('export default', 'return')
  const component = new Function('CHANGE_FLOW_NODES', 'NODE_LABEL', script)(CHANGE_FLOW_NODES, NODE_LABEL)
  const state = { ...component.data(), change, ctx: { currentRole: {}, dataScope: {}, permissionPatterns: ['*'] }, $route: { params: { id: change.changeId } } }
  for (const [name, method] of Object.entries(component.methods)) state[name] = method
  for (const [name, getter] of Object.entries(component.computed)) Object.defineProperty(state, name, { get: () => getter.call(state) })
  return state
}

const baseChange = { changeId: '1000000000000063661', changeType: 'SUSPEND', realName: '测试学生',
  fromStatus: 'REGISTERED', toStatus: 'SUSPENDED', decisionVersion: 1, currentNode: '', currentTaskId: '' }

test('D3-U exposes the canonical pending-effective status as a first-class display state', async () => {
  const source = await readFile(constantsUrl, 'utf8')

  assert.match(source, /APPROVED_PENDING_EFFECTIVE: '已通过·待生效'/)
  assert.match(source, /case 'APPROVED_PENDING_EFFECTIVE': return 'warning'/)
})

test('D3-U pending-effective detail shows approval complete without reopening review or claiming student status changed', async () => {
  // The temporal guard closes the approval task but leaves the student unchanged until execution.
  const html = await renderReview({ ...baseChange, status: 'APPROVED_PENDING_EFFECTIVE', effectiveDate: '2099-09-01T00:00:00' })
  assert.match(html, /已通过·待生效/)
  assert.match(html, /终审已通过，当前学籍尚未改变/)
  assert.doesNotMatch(html, /通过本节点|退回补充|驳回申请|本异动已正式生效/)
  const source = await readFile(detailUrl, 'utf8')
  assert.match(source, /路径顺序不代表历史节点已全部审核通过/)

  const pending = await detailState({ ...baseChange, status: 'APPROVED_PENDING_EFFECTIVE', effectiveDate: '2099-09-01T00:00:00' })
  assert.deepEqual(pending.flowNodes.map((_, index) => pending.nodeStateText(index)), pending.flowNodes.map(() => '流程已结束·节点供参考'))
  const pendingWithoutDate = await detailState({ ...baseChange, status: 'APPROVED_PENDING_EFFECTIVE', effectiveDate: null })
  assert.match(pendingWithoutDate.reviewHint, /正式计划生效时间缺失/)
  assert.match(pendingWithoutDate.reviewHint, /当前学籍尚未变更/)
  assert.doesNotMatch(pendingWithoutDate.reviewHint, /立即生效/)
  const effective = await detailState({ ...baseChange, status: 'EFFECTIVE', effectiveDate: null })
  assert.deepEqual(effective.flowNodes.map((_, index) => effective.nodeStateText(index)), effective.flowNodes.map(() => '流程已结束·节点供参考'))
  const current = await detailState({ ...baseChange, status: 'IN_REVIEW', currentNode: pending.flowNodes[1] })
  assert.deepEqual(current.flowNodes.map((_, index) => current.nodeStateText(index)), ['历史状态待核对', '当前审批', '后续路径参考'])
  for (const [status, label] of [['RETURNED', '已退回·路径供参考'], ['REJECTED', '已驳回·路径供参考']]) {
    const closed = await detailState({ ...baseChange, status, currentNode: pending.flowNodes[1] })
    assert.deepEqual(closed.flowNodes.map((_, index) => closed.nodeStateText(index)), closed.flowNodes.map(() => label))
    assert.deepEqual(closed.flowNodes.map((_, index) => closed.nodeState(index)), closed.flowNodes.map(() => 'is-reference'))
    const closedHtml = await renderReview({ ...baseChange, status, currentNode: pending.flowNodes[1] })
    assert.match(closedHtml, new RegExp(status === 'RETURNED' ? '已退回' : '已驳回'))
    assert.match(closedHtml, /审批路径节点/)
    assert.doesNotMatch(closedHtml, /通过本节点|退回补充|驳回申请/)
  }
  const missing = await detailState({ ...baseChange, status: 'SUBMITTED', currentNode: '' })
  assert.deepEqual(missing.flowNodes.map((_, index) => missing.nodeStateText(index)), missing.flowNodes.map(() => '节点状态待核对'))
})

test('D3-U formal status, rather than a missing or elapsed planned date, determines effective result', async () => {
  const effective = await renderReview({ ...baseChange, status: 'EFFECTIVE', effectiveDate: null })
  assert.match(effective, /已生效/)
  assert.match(effective, /本异动已正式生效/)

  for (const effectiveDate of [null, '2000-01-01T00:00:00']) {
    const pending = await renderReview({ ...baseChange, status: 'APPROVED_PENDING_EFFECTIVE', effectiveDate })
    assert.match(pending, /当前学籍尚未改变/)
    assert.doesNotMatch(pending, /本异动已正式生效|终审通过立即生效/)
  }
})
