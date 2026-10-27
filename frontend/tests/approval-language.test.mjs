import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'
import test from 'node:test'
import * as Vue from 'vue'
import { compile } from '@vue/compiler-dom'
import { renderToString } from 'vue/server-renderer'
import { NODE_LABEL, STATUS_LABEL as STATUS_CHANGE_LABELS } from '../src/modules/academicAffairs/constants/status-change.js'
import { ACADEMIC_STUDENT_STATUS_LABELS, ACADEMIC_STATUS_CHANGE_LABELS } from '../src/modules/academicAffairs/config/academicStudentLabels.js'
import { MESSAGE_CAMPAIGN_STATUS_LABELS, MESSAGE_CATEGORY_LABELS } from '../src/modules/messageCenter/constants/message-center.constants.js'
import { safeLocalizedText } from '../src/utils/presentationSafety.js'
import { formatDateTime } from '../src/utils/dateUtils.js'

const source = readFileSync(new URL('../src/modules/approval/api/approval.api.js', import.meta.url), 'utf8')
  .replace(/^import .*$/gm, '').replace(/^export /gm, '')
const scheduleSource = readFileSync(new URL('../src/modules/academicAffairs/api/academic-schedule-change.api.js', import.meta.url), 'utf8')
const scheduleLabels = new Function(scheduleSource.slice(scheduleSource.indexOf('export const CHANGE_TYPES'), scheduleSource.indexOf('export const scheduleChangeApi')).replaceAll('export ', '') + '\nreturn { CHANGE_TYPES, CHANGE_STATUS }')()
const leaveLabels = JSON.parse(readFileSync(new URL('../../shared/contracts/leave-presentation.json', import.meta.url), 'utf8'))
const presentation = { NODE_LABEL, safeLocalizedText, formatDateTime, STATUS_CHANGE_LABELS, ACADEMIC_STUDENT_STATUS_LABELS, ACADEMIC_STATUS_CHANGE_LABELS, MESSAGE_CAMPAIGN_STATUS_LABELS, MESSAGE_CATEGORY_LABELS, leaveLabels, ...scheduleLabels }
vm.runInNewContext(source, presentation)

test('业务字段按所属业务翻译，原代码和敏感内容不被改写', () => {
  const show = (label, value, type) => presentation.contextField({ label, value }, type)
  assert.equal(show('请假类型', 'SICK', 'LEAVE').displayValue, '病假')
  assert.equal(show('当前状态', 'CLOSED', 'LEAVE').displayValue, '已销假')
  assert.equal(show('当前状态', 'SUBMITTED', 'AA_SCHEDULE_CHANGE').displayValue, '待学院审')
  assert.equal(show('目标学籍状态', 'PRESERVED', 'AA_STATUS_CHANGE').displayValue, '保留学籍')
  assert.equal(show('目标学籍状态', 'RETAINED', 'AA_STATUS_CHANGE').displayValue, '留级')
  assert.equal(show('当前状态', 'PARTIAL_FAILED', 'MESSAGE_CAMPAIGN').displayValue, '部分失败')
  assert.equal(show('当前状态', 'PUBLISHED', 'AA_GRADE_TASK').displayValue, '已发布')
  const time = '2026-09-13T16:00:00Z'
  assert.equal(show('开始时间', time, 'LEAVE').displayValue, formatDateTime(time))
  assert.equal(show('开始时间', time, 'LEAVE').value, time)
  assert.equal(show('当前状态', 'NEW_STATUS', 'LEAVE').displayValue, '其他状态')
  assert.equal(show('当前状态', '待核验', 'LEAVE').displayValue, '待核验')
  const field = { label: '处分类型', value: 'WARNING' }
  assert.equal(presentation.contextField(field, 'DISCIPLINE').displayValue, '警告')
  assert.equal(field.value, 'WARNING')
  assert.equal(show('更正理由', '请保留课程 CAD 编号和原意见', 'AA_GRADE_CHANGE').value, '请保留课程 CAD 编号和原意见')
  const masked = { label: '申请等级', value: '敏感内容不可查看', masked: true }
  assert.equal(presentation.contextField(masked, 'AID'), masked)
})

test('审批节点复用中文名称，未知节点不会回显代码', () => {
  assert.equal(presentation.taskRow({ nodeCode: 'COUNSELOR_REVIEW' }).currentNode, '辅导员审核')
  assert.equal(presentation.taskRow({ nodeCode: 'ACADEMIC_REVIEW' }).currentNode, '教务审核')
  assert.equal(presentation.taskRow({ nodeCode: 'NEW_NODE' }).currentNode, '其他环节')
  assert.equal(presentation.taskRow({ nodeCode: 'constructor' }).currentNode, '其他环节')
  assert.equal(presentation.taskRow({ nodeName: '专业负责人审核', nodeCode: 'CUSTOM' }).currentNode, '专业负责人审核')
})

test('未知状态只改变展示，不改返回的状态值、编号、权限动作和版本', () => {
  const original = { taskId: '1000000000000000007', status: 'NEW_STATUS', urgency: 'NEW_URGENCY', version: 9, allowedActions: ['TRANSFER'] }
  const row = presentation.taskRow(original)
  assert.equal(row.statusLabel, '其他状态')
  assert.equal(row.urgencyLabel, '其他状态')
  assert.equal(row.status, original.status)
  assert.equal(row.urgency, original.urgency)
  assert.equal(row.taskId, original.taskId)
  assert.equal(row.version, 9)
  assert.deepEqual(row.allowedActions, ['TRANSFER'])
  assert.equal(presentation.returnedRow({ rectifyStatus: 'NEW_STATE' }).rectifyStatusLabel, '其他状态')
})

test('审批记录和模板缺少中文时不外露人员编号或内部代码', () => {
  const history = presentation.timelineRow({ action: 'NEW_ACTION', assigneeId: '1000000000000000007' })
  assert.equal(history.who, '办理人姓名未提供')
  assert.equal(history.action, '其他操作')
  const template = presentation.templateRow({ id: '1', status: 'NEW_STATUS', nodes: [{ role: 'NEW_ROLE' }] })
  assert.equal(template.status, 'NEW_STATUS')
  assert.equal(template.statusLabel, '其他状态')
  assert.equal(template.nodes[0].role, 'NEW_ROLE')
  assert.equal(template.nodes[0].roleLabel, '其他业务角色')
})

test('详情正文隐藏内部业务记录号，学号和申请单号仍可见', async () => {
  const view = readFileSync(new URL('../src/views/admin/approval/ApprovalDetailView.vue', import.meta.url), 'utf8')
  const snippet = view.match(/<div v-for="\(f, i\)[\s\S]*?<\/div>/)[0]
  const render = new Function('Vue', compile(snippet, { mode: 'function', prefixIdentifiers: true }).code)(Vue)
  const fields = [{ label: '业务记录', value: '1000000000000000007' }, { label: '学号', value: 'S20260001' }, { label: '申请单号', value: 'SQ20260001' }, { label: '处分单ID', value: '1000000000000000008' }, { label: '学生ID', value: '1000000000000000009' }, { label: '当前状态', value: 'PENDING_REVIEW', displayValue: '待审核' }]
  const html = await renderToString(Vue.createSSRApp({ data: () => ({ detail: { fields } }), render }))
  assert.doesNotMatch(html, /1000000000000000007/)
  assert.doesNotMatch(html, /1000000000000000008|1000000000000000009|PENDING_REVIEW/)
  assert.match(html, /待审核/)
  assert.match(html, /S20260001/)
  assert.match(html, /SQ20260001/)
  assert.equal(fields.length, 6)
})

test('身份列表缺少中文名称时不显示角色码或内部身份编号', () => {
  const view = readFileSync(new URL('../src/components/common/AppUserChip.vue', import.meta.url), 'utf8')
  const body = view.match(/contextTitle\(c\) \{([\s\S]*?)\n {4}\}/)[1]
  const title = new Function('c', 'ROLE_LABEL', body)
  const labels = { SCHOOL_ADMIN: '学校管理员' }
  assert.equal(title({ roleCode: 'NEW_ROLE', contextId: '1000000000000000007' }, labels), '其他身份')
  assert.equal(title({ roleCode: 'SCHOOL_ADMIN' }, labels), '学校管理员')
  assert.equal(title({ contextName: '本校教学负责人', roleCode: 'NEW_ROLE' }, labels), '本校教学负责人')
})

test('工作台尚未读取审批字典时也显示服务端权威业务名称', () => {
  assert.equal(presentation.taskRow({ sourceBizType: 'AA_GRADE_TASK', sourceBizTypeLabel: '成绩审核' }).bizTypeLabel, '成绩审核')
})
