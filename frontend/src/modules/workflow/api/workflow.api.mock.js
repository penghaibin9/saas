/**
 * 11 权限与流程中心 — mock API 实现（默认模式）
 * 与 workflow.contract.js 逐接口对齐；所有写操作真实变更 mock 状态并追加审计。
 * 页面禁止直接 import 本文件（必须经 provider）。
 */
import { WORKFLOW_ERROR_CODES as E } from './workflow.contract'
import {
  TASK_STATUS,
  PROCESS_STATUS,
  PROCESS_INSTANCE_STATUS,
  AUDIT_TARGET_TYPE,
  APPROVAL_ACTION,
  REJECT_REASON_MIN_LENGTH,
  LICENSE_VIEW_STATE
} from '../constants/workflow.constants'
import * as db from '../mock/workflow.mock'
import { isTaskFinished } from '../helpers/approval.helpers'

const delay = (ms = 180) => new Promise((r) => setTimeout(r, ms))
let reqSeq = 1

function envelope(data, code = E.OK, message = 'ok') {
  return { code, message, data, timestamp: Date.now(), requestId: `mock-${Date.now()}-${reqSeq++}` }
}

function fail(code, message) {
  return envelope(null, code, message)
}

function guardFlags() {
  if (db.mockFlags.forceError) return fail(E.SERVER_ERROR, '模拟服务端错误（mockFlags.forceError）')
  return null
}

function guardWritable() {
  // licenseContext 预留：到期只读 / 未授权时写操作统一拒绝（优先级见 mock 注释）
  if (db.licenseState.viewState === LICENSE_VIEW_STATE.READONLY) {
    return fail(E.MODULE_READONLY, '模块已到期只读，写操作被拒绝')
  }
  if (db.licenseState.viewState === LICENSE_VIEW_STATE.NO_LICENSE) {
    return fail(E.MODULE_NO_LICENSE, '模块未授权')
  }
  return null
}

const clone = (v) => JSON.parse(JSON.stringify(v))

function paginate(list, { page = 1, pageSize = 20 } = {}) {
  const total = list.length
  const start = (page - 1) * pageSize
  return { list: clone(list.slice(start, start + pageSize)), total }
}

const kw = (text, keyword) => !keyword || String(text || '').toLowerCase().includes(String(keyword).toLowerCase())

/* ============ 1. 概览 ============ */
export async function getWorkflowOverview() {
  await delay()
  const err = guardFlags()
  if (err) return err
  const pending = db.approvalTasks.filter((t) => t.status === TASK_STATUS.PENDING)
  const enabled = db.processTemplates.filter((t) => t.status === PROCESS_STATUS.ENABLED)
  const moduleCodes = [...new Set(db.processTemplates.map((t) => t.moduleCode))]
  const moduleUsage = moduleCodes.map((mc) => ({
    moduleCode: mc,
    enabledTemplates: db.processTemplates.filter((t) => t.moduleCode === mc && t.status === PROCESS_STATUS.ENABLED).length,
    totalTemplates: db.processTemplates.filter((t) => t.moduleCode === mc).length,
    pendingTasks: pending.filter((t) => t.businessModule === mc).length
  }))
  const recentRecords = db.approvalTasks
    .flatMap((t) => t.records.map((r) => ({ ...r, taskId: t.taskId, taskTitle: t.title, businessModule: t.businessModule })))
    .sort((a, b) => (a.time < b.time ? 1 : -1))
    .slice(0, 6)
  const abnormalHints = []
  const rejected = db.approvalTasks.filter((t) => t.status === TASK_STATUS.REJECTED)
  if (rejected.length) abnormalHints.push({ type: 'REJECTED_PENDING_RESUBMIT', level: 'warning', text: `${rejected.length} 个业务被退回，等待发起人重新提交` })
  const draft = db.processTemplates.filter((t) => t.status === PROCESS_STATUS.DRAFT)
  if (draft.length) abnormalHints.push({ type: 'DRAFT_TEMPLATE', level: 'info', text: `${draft.length} 个流程模板处于草稿状态，尚未发布` })
  return envelope({
    pendingTaskCount: pending.length,
    templateCount: db.processTemplates.length,
    enabledTemplateCount: enabled.length,
    roleCount: db.roles.length,
    permissionCount: db.permissions.length,
    moduleUsage,
    recentRecords,
    abnormalHints
  })
}

/* ============ 2/3/4. 流程模板 ============ */
export async function getProcessTemplates(params = {}) {
  await delay()
  const err = guardFlags()
  if (err) return err
  if (db.mockFlags.forceEmpty) return envelope({ list: [], total: 0 })
  let list = db.processTemplates
  if (params.moduleCode) list = list.filter((t) => t.moduleCode === params.moduleCode)
  if (params.status) list = list.filter((t) => t.status === params.status)
  if (params.keyword) list = list.filter((t) => kw(t.templateName, params.keyword) || kw(t.templateCode, params.keyword))
  return envelope(paginate(list, params))
}

export async function getProcessTemplateDetail(id) {
  await delay()
  const t = db.processTemplates.find((x) => x.templateId === id)
  if (!t) return fail(E.NOT_FOUND, '流程模板不存在')
  return envelope(clone(t))
}

export async function updateProcessTemplateStatus(id, status) {
  await delay()
  const err = guardFlags() || guardWritable()
  if (err) return err
  const t = db.processTemplates.find((x) => x.templateId === id)
  if (!t) return fail(E.NOT_FOUND, '流程模板不存在')
  if (![PROCESS_STATUS.ENABLED, PROCESS_STATUS.DISABLED].includes(status)) {
    return fail(E.INVALID_PARAM, '非法的模板状态')
  }
  const before = t.status
  t.status = status
  t.updatedAt = db.nowText()
  t.updatedBy = db.currentPermissionContext.userName
  if (status === PROCESS_STATUS.ENABLED && !t.publishedAt) t.publishedAt = db.nowText()
  db.appendAuditLog({
    operator: db.currentPermissionContext.userName,
    targetType: AUDIT_TARGET_TYPE.PROCESS_TEMPLATE,
    targetId: id,
    action: status === PROCESS_STATUS.ENABLED ? '启用模板' : '停用模板',
    before,
    after: status
  })
  return envelope(clone(t))
}

/* ============ 5/6. 审批任务 ============ */
export async function getApprovalTasks(params = {}) {
  await delay()
  const err = guardFlags()
  if (err) return err
  if (db.mockFlags.forceEmpty) return envelope({ list: [], total: 0 })
  let list = db.approvalTasks
  const tab = params.tab || 'ALL'
  if (tab === 'MINE_PENDING') {
    list = list.filter((t) => t.status === TASK_STATUS.PENDING)
  } else if (tab !== 'ALL') {
    list = list.filter((t) => t.status === tab)
  }
  if (params.moduleCode) list = list.filter((t) => t.businessModule === params.moduleCode)
  if (params.keyword) {
    list = list.filter((t) => kw(t.title, params.keyword) || kw(t.initiator, params.keyword) || kw(t.businessId, params.keyword))
  }
  list = [...list].sort((a, b) => (a.updatedAt < b.updatedAt ? 1 : -1))
  return envelope(paginate(list, params))
}

export async function getApprovalTaskDetail(id) {
  await delay()
  const t = db.approvalTasks.find((x) => x.taskId === id)
  if (!t) return fail(E.NOT_FOUND, '审批任务不存在')
  return envelope(clone(t))
}

function findTaskForWrite(id) {
  const t = db.approvalTasks.find((x) => x.taskId === id)
  if (!t) return { err: fail(E.NOT_FOUND, '审批任务不存在') }
  if (isTaskFinished(t)) return { err: fail(E.TASK_ALREADY_FINISHED, '任务已处于终态，不可重复处理') }
  return { task: t }
}

function pushRecord(task, action, comment, nodeName) {
  task.records.push({
    recordId: `rec-${Date.now()}-${Math.floor(Math.random() * 1000)}`,
    time: db.nowText(),
    operator: db.currentPermissionContext.userName,
    action,
    comment: comment || '',
    nodeName: nodeName || task.currentNode
  })
  task.updatedAt = db.nowText()
}

function syncInstance(task, status) {
  const ins = db.processInstances.find((i) => i.businessId === task.businessId)
  if (ins) {
    ins.status = status
    ins.currentNode = task.currentNode
    if (status !== PROCESS_INSTANCE_STATUS.RUNNING) ins.endedAt = db.nowText()
  }
}

/* 7. 通过 */
export async function approveTask(id, payload = {}) {
  await delay()
  const err = guardFlags() || guardWritable()
  if (err) return err
  const { task, err: terr } = findTaskForWrite(id)
  if (terr) return terr
  pushRecord(task, APPROVAL_ACTION.APPROVE, payload.comment)
  task.status = TASK_STATUS.APPROVED
  task.currentNode = '结束'
  task.currentAssignee = ''
  syncInstance(task, PROCESS_INSTANCE_STATUS.APPROVED)
  db.appendAuditLog({
    operator: db.currentPermissionContext.userName,
    targetType: AUDIT_TARGET_TYPE.APPROVAL_TASK,
    targetId: id,
    action: '通过',
    before: TASK_STATUS.PENDING,
    after: TASK_STATUS.APPROVED
  })
  return envelope(clone(task))
}

/* 8. 退回（原因必填 ≥5 字，原因写入 timeline，业务回到可编辑） */
export async function rejectTask(id, payload = {}) {
  await delay()
  const err = guardFlags() || guardWritable()
  if (err) return err
  const reason = String(payload.reason || '').trim()
  if (reason.length < REJECT_REASON_MIN_LENGTH) {
    return fail(E.REJECT_REASON_TOO_SHORT, `退回原因不能少于 ${REJECT_REASON_MIN_LENGTH} 个字`)
  }
  const { task, err: terr } = findTaskForWrite(id)
  if (terr) return terr
  pushRecord(task, APPROVAL_ACTION.REJECT, reason)
  task.status = TASK_STATUS.REJECTED
  task.currentNode = task.records[0]?.nodeName || '发起节点'
  task.currentAssignee = task.initiator // 回到发起人，业务恢复可编辑
  syncInstance(task, PROCESS_INSTANCE_STATUS.REJECTED)
  db.appendAuditLog({
    operator: db.currentPermissionContext.userName,
    targetType: AUDIT_TARGET_TYPE.APPROVAL_TASK,
    targetId: id,
    action: '退回',
    before: TASK_STATUS.PENDING,
    after: TASK_STATUS.REJECTED
  })
  return envelope(clone(task))
}

/* 9. 撤回 */
export async function withdrawTask(id, payload = {}) {
  await delay()
  const err = guardFlags() || guardWritable()
  if (err) return err
  const { task, err: terr } = findTaskForWrite(id)
  if (terr) return terr
  const tpl = db.processTemplates.find((x) => x.templateId === task.templateId)
  const startNode = tpl?.nodes.find((n) => n.nodeType === 'START')
  if (startNode && !startNode.allowWithdraw) {
    return fail(E.TASK_NOT_WITHDRAWABLE, '该流程不允许发起人撤回')
  }
  pushRecord(task, APPROVAL_ACTION.WITHDRAW, payload.reason)
  task.status = TASK_STATUS.WITHDRAWN
  task.currentNode = startNode?.nodeName || '发起节点'
  task.currentAssignee = task.initiator
  syncInstance(task, PROCESS_INSTANCE_STATUS.WITHDRAWN)
  db.appendAuditLog({
    operator: db.currentPermissionContext.userName,
    targetType: AUDIT_TARGET_TYPE.APPROVAL_TASK,
    targetId: id,
    action: '撤回',
    before: TASK_STATUS.PENDING,
    after: TASK_STATUS.WITHDRAWN
  })
  return envelope(clone(task))
}

/* ============ 10/11. 流程实例 ============ */
export async function getProcessInstances(params = {}) {
  await delay()
  const err = guardFlags()
  if (err) return err
  let list = db.processInstances
  if (params.moduleCode) list = list.filter((i) => i.businessModule === params.moduleCode)
  if (params.status) list = list.filter((i) => i.status === params.status)
  return envelope(paginate(list, params))
}

export async function getProcessInstanceDetail(id) {
  await delay()
  const ins = db.processInstances.find((x) => x.instanceId === id)
  if (!ins) return fail(E.NOT_FOUND, '流程实例不存在')
  return envelope(clone(ins))
}

/* ============ 12/13/14. 角色 ============ */
export async function getRoles(params = {}) {
  await delay()
  const err = guardFlags()
  if (err) return err
  let list = db.roles
  if (params.keyword) list = list.filter((r) => kw(r.roleName, params.keyword) || kw(r.roleCode, params.keyword))
  return envelope({ list: clone(list), total: list.length })
}

export async function getRoleDetail(id) {
  await delay()
  const r = db.roles.find((x) => x.roleId === id)
  if (!r) return fail(E.NOT_FOUND, '角色不存在')
  return envelope(clone(r))
}

export async function updateRolePermissions(id, payload = {}) {
  await delay()
  const err = guardFlags() || guardWritable()
  if (err) return err
  const r = db.roles.find((x) => x.roleId === id)
  if (!r) return fail(E.NOT_FOUND, '角色不存在')
  const before = `${r.permissionKeys.length} 项 / ${r.dataScope}`
  if (Array.isArray(payload.permissionKeys)) r.permissionKeys = [...payload.permissionKeys]
  if (payload.dataScope) r.dataScope = payload.dataScope
  db.appendAuditLog({
    operator: db.currentPermissionContext.userName,
    targetType: AUDIT_TARGET_TYPE.ROLE,
    targetId: id,
    action: '更新角色权限',
    before,
    after: `${r.permissionKeys.length} 项 / ${r.dataScope}`
  })
  return envelope(clone(r))
}

/* ============ 15/16. 权限点 ============ */
export async function getPermissions(params = {}) {
  await delay()
  const err = guardFlags()
  if (err) return err
  if (db.mockFlags.forceEmpty) return envelope({ list: [], total: 0 })
  let list = db.permissions
  if (params.moduleCode) list = list.filter((p) => p.moduleCode === params.moduleCode)
  if (params.type) list = list.filter((p) => p.type === params.type)
  if (params.keyword) list = list.filter((p) => kw(p.permissionKey, params.keyword) || kw(p.permissionName, params.keyword))
  return envelope(paginate(list, params))
}

export async function updatePermissionStatus(id, status) {
  await delay()
  const err = guardFlags() || guardWritable()
  if (err) return err
  const p = db.permissions.find((x) => x.permissionId === id)
  if (!p) return fail(E.NOT_FOUND, '权限点不存在')
  const before = p.status
  p.status = status
  db.appendAuditLog({
    operator: db.currentPermissionContext.userName,
    targetType: AUDIT_TARGET_TYPE.PERMISSION,
    targetId: p.permissionKey,
    action: status === 'ENABLED' ? '启用权限点' : '停用权限点',
    before,
    after: status
  })
  return envelope(clone(p))
}

/* ============ 17. 审计 ============ */
export async function getAuditLogs(params = {}) {
  await delay()
  let list = db.auditLogs
  if (params.targetType) list = list.filter((l) => l.targetType === params.targetType)
  return envelope(paginate(list, params))
}

/* ============ 18. permissionContext ============ */
export async function getPermissionContext() {
  await delay(60)
  return envelope(clone(db.currentPermissionContext))
}

/* ============ mock 专用（dev 演示） ============ */
export function setLicenseViewState(state) {
  db.setLicenseViewState(state)
}
export function getLicenseViewState() {
  return db.licenseState.viewState
}
export function setMockFlags(flags) {
  db.setMockFlags(flags)
}
