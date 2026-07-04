/**
 * 审批中心 API（mock 实现，待办/审批闭环）。
 * 契约：所有方法返回 Promise<{ code, data, message }>，code=0 成功。
 * 真实后端阶段仅替换实现，方法签名冻结不变（与 internship 等模块同约定）。
 * 页面禁止直接 import mocks，必须经本文件获取数据；写操作真实变更内存数据并写入审计留痕。
 */
import {
  tenantBrandConfig,
  roleProfiles,
  statusOptions,
  filterOptions,
  batchActions,
  todoSummary,
  approvalList,
  approvalDetailMap,
  approvalTimelineMap,
  returnedItems,
  doneItems,
  ccItems,
  transferTargets,
  approvalTemplates,
  auditLogs
} from '@/mocks/approval/approval.mock'

const DELAY = 120
const URGENCY_WEIGHT = { OVERDUE: 0, URGENT: 1, NORMAL: 2 }

/** 演示默认角色：学院管理员（可通过 switchRole 切换体验其余 4 个角色） */
let activeRoleCode = 'COLLEGE_ADMIN'
let seq = 500

function ok(data) {
  return new Promise((resolve) => {
    setTimeout(() => resolve({ code: 0, data, message: 'ok' }), DELAY)
  })
}

function fail(message) {
  return Promise.resolve({ code: 1, data: null, message })
}

function clone(value) {
  return JSON.parse(JSON.stringify(value))
}

function paginate(list, { page = 1, pageSize = 10 } = {}) {
  const total = list.length
  const start = (page - 1) * pageSize
  return { list: list.slice(start, start + pageSize), total, page, pageSize }
}

function profile() {
  return roleProfiles[activeRoleCode]
}

function pushAudit(action, target, detail) {
  auditLogs.unshift({
    id: 'al-' + ++seq,
    who: profile().currentRole.userName,
    roleName: profile().currentRole.roleName,
    time: '刚刚',
    action,
    target,
    detail
  })
}

/** 当前角色数据范围内的在办待办（业务类型口径 + 未转交 + 待审批） */
function scopedTodos() {
  const p = profile()
  return approvalList.filter(
    (t) => t.status === 'PENDING_REVIEW' && !t.transferred && p.todoBizTypes.includes(t.bizType)
  )
}

function timelineOf(taskId) {
  if (!approvalTimelineMap[taskId]) approvalTimelineMap[taskId] = []
  return approvalTimelineMap[taskId]
}

function findPendingTask(taskId) {
  const task = approvalList.find((t) => t.taskId === taskId)
  if (!task) return { error: '审批任务不存在或已被撤销' }
  if (task.status !== 'PENDING_REVIEW') return { error: '该任务已办结，请勿重复操作' }
  if (task.transferred) return { error: '该任务已转交他人办理，不可重复操作' }
  if (!profile().todoBizTypes.includes(task.bizType)) {
    return { error: '该任务不在当前角色的数据范围内' }
  }
  return { task }
}

function operatorLabel() {
  const role = profile().currentRole
  return role.userName + ' · ' + role.roleName
}

function appendDone(task, result, resultLabel, comment, node) {
  doneItems.unshift({
    id: 'dn-' + ++seq,
    taskId: task.taskId,
    bizTypeLabel: task.bizTypeLabel,
    title: task.title,
    applicantName: task.applicant.name,
    className: task.applicant.className,
    node: node || task.currentNode,
    result,
    resultLabel,
    finishTime: '刚刚',
    comment: comment || '',
    roleCode: activeRoleCode
  })
}

function doApprove(task, comment) {
  task.status = 'APPROVED'
  task.statusLabel = '已通过'
  task.finishTime = '刚刚'
  timelineOf(task.taskId).push({
    who: operatorLabel(),
    action: '审批通过',
    time: '刚刚',
    comment: comment ? comment.trim() : '',
    tone: 'success'
  })
  appendDone(task, 'APPROVED', '已通过', comment && comment.trim())
}

function doReturn(task, reason) {
  const handledNode = task.currentNode
  task.status = 'RETURNED'
  task.statusLabel = '已退回'
  task.currentNode = '已退回申请人'
  task.finishTime = '刚刚'
  timelineOf(task.taskId).push({
    who: operatorLabel(),
    action: '退回申请',
    time: '刚刚',
    comment: reason.trim(),
    tone: 'danger'
  })
  appendDone(task, 'RETURNED', '已退回', reason.trim(), handledNode)
  returnedItems.unshift({
    id: 'rt-' + ++seq,
    taskId: task.taskId,
    bizTypeLabel: task.bizTypeLabel,
    title: task.title,
    applicantName: task.applicant.name,
    className: task.applicant.className,
    reason: reason.trim(),
    returnedBy: profile().currentRole.userName,
    returnTime: '刚刚',
    rectifyStatus: 'PENDING_RESUBMIT',
    rectifyStatusLabel: '待整改重报',
    roleCode: activeRoleCode
  })
}

function doTransfer(task, target, note) {
  task.transferred = true
  task.transferHint = '已转交 ' + target.userName + '（' + target.roleName + '）办理'
  timelineOf(task.taskId).push({
    who: operatorLabel(),
    action: '转交给 ' + target.userName + '（' + target.roleName + '）',
    time: '刚刚',
    comment: note ? note.trim() : '',
    tone: 'warning'
  })
}

function findTransferTarget(targetUserId) {
  return transferTargets.find((t) => t.userId === targetUserId)
}

function validateTemplatePayload(payload = {}) {
  if (!payload.name || !payload.name.trim()) return '模板名称必填'
  if (!payload.bizType) return '请选择适用业务类型'
  const nodes = Array.isArray(payload.nodes) ? payload.nodes : []
  if (!nodes.length) return '至少配置 1 个审批节点'
  for (let i = 0; i < nodes.length; i++) {
    if (!nodes[i].name || !nodes[i].name.trim()) return '第 ' + (i + 1) + ' 个节点名称必填'
    if (!nodes[i].role) return '第 ' + (i + 1) + ' 个节点须指定办理角色'
    if (!Number(nodes[i].sla) || Number(nodes[i].sla) <= 0) {
      return '第 ' + (i + 1) + ' 个节点时限须为大于 0 的小时数'
    }
  }
  return ''
}

function normalizeTemplateNodes(nodes) {
  return nodes.map((n) => {
    const roleOption = filterOptions.templateNodeRoles.find((r) => r.value === n.role)
    return {
      name: n.name.trim(),
      role: n.role,
      roleLabel: roleOption ? roleOption.label : n.role,
      sla: Number(n.sla)
    }
  })
}

function bizTypeLabelOf(bizType) {
  const hit = filterOptions.bizTypes.find((b) => b.value === bizType)
  return hit ? hit.label : bizType
}

/* P2 · 真实后端桥（失败自动回退本文件 mock 实现） */
import { withFallback, shouldTryReal } from '@/services/http/client'
import * as realApi from '@/services/http/adapters'

export const approvalApi = {
  /** 品牌 / 当前角色 / 数据范围 / 权限动作 / 字典 / 可切换角色（页面初始化统一获取） */
  getContext() {
    return this._mockGetContext().then((res) => {
      if (!shouldTryReal()) return res
      return realApi.enrichContext(res).catch(() => res)
    })
  },

  _mockGetContext() {
    const p = profile()
    return ok({
      tenantBrandConfig: clone(tenantBrandConfig),
      currentRole: clone(p.currentRole),
      dataScope: clone(p.dataScope),
      permissionActions: clone(p.permissionActions),
      statusOptions: clone(statusOptions),
      filterOptions: clone(filterOptions),
      batchActions: clone(batchActions),
      availableRoles: Object.values(roleProfiles).map((r) => ({
        roleCode: r.currentRole.roleCode,
        roleName: r.currentRole.roleName,
        userName: r.currentRole.userName
      })),
      transferTargets: clone(
        transferTargets.filter((t) => t.userId !== p.currentRole.userId)
      ),
      todoCount: scopedTodos().length
    })
  },

  /** 切换演示角色（切换后由调用方重新 getContext 刷新上下文） */
  switchRole(roleCode) {
    const target = roleProfiles[roleCode]
    if (!target) return fail('角色不存在或未授权，无法切换')
    activeRoleCode = roleCode
    return ok({
      roleCode: target.currentRole.roleCode,
      roleName: target.currentRole.roleName,
      userName: target.currentRole.userName
    })
  },

  /** 待办统计（按当前角色数据范围实时重算，业务类型 / 紧急度 / 超时联动写操作） */
  getTodoSummary() {
    return withFallback('approvals.summary', () => realApi.getTodoSummary(), () => this._mockGetTodoSummary())
  },

  _mockGetTodoSummary() {
    const p = profile()
    const list = scopedTodos()
    const byBizType = p.todoBizTypes.map((bizType) => {
      const items = list.filter((t) => t.bizType === bizType)
      const earliest = items.length
        ? items.map((t) => t.submitTime).sort((a, b) => a.localeCompare(b))[0]
        : ''
      return {
        bizType,
        label: bizTypeLabelOf(bizType),
        count: items.length,
        earliest,
        overdue: items.filter((t) => t.urgency === 'OVERDUE').length
      }
    })
    const overdueList = list
      .filter((t) => t.urgency === 'OVERDUE')
      .map((t) => ({
        taskId: t.taskId,
        title: t.title,
        bizTypeLabel: t.bizTypeLabel,
        applicantName: t.applicant.name,
        className: t.applicant.className,
        deadline: t.deadline
      }))
    return ok({
      todayTag: todoSummary.todayTag,
      total: list.length,
      todayNew: list.filter((t) => t.submitTime.startsWith(todoSummary.todayTag)).length,
      nearDeadline: list.filter((t) => t.urgency === 'URGENT').length,
      overdue: list.filter((t) => t.urgency === 'OVERDUE').length,
      byBizType,
      overdueList
    })
  },

  /** 我的待办（按角色数据范围过滤业务类型，支持筛选 + 分页，超时/临期置顶） */
  getTodos(params = {}) {
    return withFallback('approvals.todos', () => realApi.getApprovalTodos(params), () => this._mockGetTodos(params))
  },

  _mockGetTodos(params = {}) {
    let list = [...scopedTodos()]
    if (params.bizType) list = list.filter((t) => t.bizType === params.bizType)
    if (params.urgency) list = list.filter((t) => t.urgency === params.urgency)
    if (params.keyword) {
      const kw = params.keyword.trim()
      list = list.filter(
        (t) =>
          t.title.includes(kw) ||
          t.applicant.name.includes(kw) ||
          t.applicant.studentNo.includes(kw) ||
          t.taskId.includes(kw)
      )
    }
    if (params.submitDate) {
      const md = params.submitDate.slice(5)
      list = list.filter((t) => t.submitTime.startsWith(md))
    }
    list.sort((a, b) => {
      const w = URGENCY_WEIGHT[a.urgency] - URGENCY_WEIGHT[b.urgency]
      return w !== 0 ? w : a.submitTime.localeCompare(b.submitTime)
    })
    return ok(paginate(clone(list), params))
  },

  /** 审批详情（业务字段 + 时间线 + 加签建议；taskId 不存在返回失败供页面 ErrorState） */
  getApprovalDetail(taskId) {
    if (/^\d+$/.test(String(taskId))) {
      return withFallback('approvals.detail', () => realApi.getApprovalDetail(taskId), () => this._mockGetApprovalDetail(taskId))
    }
    return this._mockGetApprovalDetail(taskId)
  },

  _mockGetApprovalDetail(taskId) {
    const task = approvalList.find((t) => t.taskId === taskId)
    if (!task) return fail('审批任务不存在或已被撤销，请返回列表刷新后重试')
    const detail = approvalDetailMap[taskId] || {
      taskId,
      fields: [],
      applyNote: '',
      attachments: [],
      suggestions: []
    }
    return ok({
      task: clone(task),
      detail: clone(detail),
      timeline: clone(timelineOf(taskId)),
      suggestions: clone(detail.suggestions || [])
    })
  },

  /** 通过（意见选填；更新状态 + 时间线 + 已办 + 审计，待办统计随之联动） */
  approveTask(taskId, { comment } = {}) {
    if (/^\d+$/.test(String(taskId))) {
      return withFallback('approvals.approve', () => realApi.approveTask(taskId, comment), () => this._mockApproveTask(taskId, { comment }))
    }
    return this._mockApproveTask(taskId, { comment })
  },

  _mockApproveTask(taskId, { comment } = {}) {
    const { task, error } = findPendingTask(taskId)
    if (error) return fail(error)
    doApprove(task, comment)
    pushAudit(
      '审批通过',
      task.taskId + ' ' + task.title,
      (comment && comment.trim() ? '审批意见：' + comment.trim() + '；' : '') + '结果已同步申请人'
    )
    return ok({ taskId, status: 'APPROVED', statusLabel: '已通过' })
  },

  /** 退回（原因必填 ≥5 字；写入退回记录并留痕，结果同步申请人） */
  returnTask(taskId, { reason } = {}) {
    if (!reason || reason.trim().length < 5) return fail('退回原因必填且不少于 5 个字')
    if (/^\d+$/.test(String(taskId))) {
      return withFallback('approvals.return', () => realApi.returnTask(taskId, reason), () => this._mockReturnTask(taskId, { reason }))
    }
    return this._mockReturnTask(taskId, { reason })
  },

  _mockReturnTask(taskId, { reason } = {}) {
    if (!reason || reason.trim().length < 5) return fail('退回原因必填且不少于 5 个字')
    const { task, error } = findPendingTask(taskId)
    if (error) return fail(error)
    doReturn(task, reason)
    pushAudit('退回审批', task.taskId + ' ' + task.title, '退回原因：' + reason.trim() + '；已同步申请人整改')
    return ok({ taskId, status: 'RETURNED', statusLabel: '已退回' })
  },

  /** 转交（校验目标存在且非本人；状态不变、办理人转移并留痕） */
  transferTask(taskId, { targetUserId, note } = {}) {
    const target = findTransferTarget(targetUserId)
    if (!target) return fail('转交对象不存在或不在可选范围内')
    if (target.userId === profile().currentRole.userId) return fail('不能将任务转交给本人')
    const { task, error } = findPendingTask(taskId)
    if (error) return fail(error)
    doTransfer(task, target, note)
    pushAudit(
      '转交任务',
      task.taskId + ' ' + task.title,
      '转交给 ' + target.userName + '（' + target.roleName + '）' + (note && note.trim() ? '；说明：' + note.trim() : '')
    )
    return ok({ taskId, transferredTo: target.userName })
  },

  /** 批量通过（逐条应用单条校验，返回成功 / 跳过数量） */
  batchApprove(ids = []) {
    if (!ids.length) return fail('请先勾选需要批量通过的待办')
    let succeeded = 0
    const skipped = []
    ids.forEach((id) => {
      const { task, error } = findPendingTask(id)
      if (error) {
        skipped.push(id)
        return
      }
      doApprove(task, '')
      succeeded++
    })
    if (!succeeded) return fail('所选任务均不可操作（已办结、已转交或不在数据范围内）')
    pushAudit('批量通过', succeeded + ' 条待办', '逐条通过并留痕' + (skipped.length ? '；跳过 ' + skipped.length + ' 条不可操作任务' : ''))
    return ok({ succeeded, skipped: skipped.length })
  },

  /** 批量退回（原因必填 ≥5 字，逐条应用同校验） */
  batchReturn(ids = [], { reason } = {}) {
    if (!ids.length) return fail('请先勾选需要批量退回的待办')
    if (!reason || reason.trim().length < 5) return fail('退回原因必填且不少于 5 个字')
    let succeeded = 0
    const skipped = []
    ids.forEach((id) => {
      const { task, error } = findPendingTask(id)
      if (error) {
        skipped.push(id)
        return
      }
      doReturn(task, reason)
      succeeded++
    })
    if (!succeeded) return fail('所选任务均不可操作（已办结、已转交或不在数据范围内）')
    pushAudit('批量退回', succeeded + ' 条待办', '统一退回原因：' + reason.trim() + (skipped.length ? '；跳过 ' + skipped.length + ' 条' : ''))
    return ok({ succeeded, skipped: skipped.length })
  },

  /** 批量转交（校验目标存在，逐条应用同校验） */
  batchTransfer(ids = [], { targetUserId, note } = {}) {
    if (!ids.length) return fail('请先勾选需要批量转交的待办')
    const target = findTransferTarget(targetUserId)
    if (!target) return fail('转交对象不存在或不在可选范围内')
    if (target.userId === profile().currentRole.userId) return fail('不能将任务转交给本人')
    let succeeded = 0
    const skipped = []
    ids.forEach((id) => {
      const { task, error } = findPendingTask(id)
      if (error) {
        skipped.push(id)
        return
      }
      doTransfer(task, target, note)
      succeeded++
    })
    if (!succeeded) return fail('所选任务均不可操作（已办结、已转交或不在数据范围内）')
    pushAudit(
      '批量转交',
      succeeded + ' 条待办',
      '转交给 ' + target.userName + '（' + target.roleName + '）' + (skipped.length ? '；跳过 ' + skipped.length + ' 条' : '')
    )
    return ok({ succeeded, skipped: skipped.length, transferredTo: target.userName })
  },

  /** 已办记录（当前角色经手，支持结果 / 业务类型 / 关键词筛选 + 分页） */
  getDoneItems(params = {}) {
    let list = doneItems.filter((d) => d.roleCode === activeRoleCode)
    if (params.result) list = list.filter((d) => d.result === params.result)
    if (params.bizType) {
      const label = bizTypeLabelOf(params.bizType)
      list = list.filter((d) => d.bizTypeLabel === label)
    }
    if (params.keyword) {
      const kw = params.keyword.trim()
      list = list.filter((d) => d.title.includes(kw) || d.applicantName.includes(kw))
    }
    return ok(paginate(clone(list), params))
  },

  /** 抄送记录（当前角色名下） */
  getCcItems(params = {}) {
    let list = ccItems.filter((c) => c.roleCode === activeRoleCode)
    if (params.readStatus) list = list.filter((c) => c.readStatus === params.readStatus)
    if (params.keyword) {
      const kw = params.keyword.trim()
      list = list.filter((c) => c.title.includes(kw) || c.applicantName.includes(kw))
    }
    return ok(paginate(clone(list), params))
  },

  /** 退回记录（当前角色发起的退回，含整改状态） */
  getReturnedItems(params = {}) {
    let list = returnedItems.filter((r) => r.roleCode === activeRoleCode)
    if (params.rectifyStatus) list = list.filter((r) => r.rectifyStatus === params.rectifyStatus)
    if (params.keyword) {
      const kw = params.keyword.trim()
      list = list.filter((r) => r.title.includes(kw) || r.applicantName.includes(kw))
    }
    return ok(paginate(clone(list), params))
  },

  /** 审批模板列表（查看权限由页面按 permissionActions 控制，此处做兜底校验） */
  getTemplates(params = {}) {
    const pa = profile().permissionActions
    if (!pa.viewTemplates.allowed) return fail(pa.viewTemplates.reason || '当前角色无权查看审批模板')
    let list = [...approvalTemplates]
    if (params.bizType) list = list.filter((t) => t.bizType === params.bizType)
    if (params.status) list = list.filter((t) => t.status === params.status)
    if (params.keyword) list = list.filter((t) => t.name.includes(params.keyword.trim()))
    return ok(paginate(clone(list), params))
  },

  /** 新增模板（名称 / 业务类型 / 节点校验，初始版本 V1） */
  createTemplate(payload = {}) {
    const pa = profile().permissionActions
    if (!pa.createTemplate.allowed) return fail(pa.createTemplate.reason || '当前角色无权新增审批模板')
    const invalid = validateTemplatePayload(payload)
    if (invalid) return fail(invalid)
    const tpl = {
      id: 'tpl-' + ++seq,
      name: payload.name.trim(),
      bizType: payload.bizType,
      bizTypeLabel: bizTypeLabelOf(payload.bizType),
      nodes: normalizeTemplateNodes(payload.nodes),
      status: 'ENABLED',
      statusLabel: '启用中',
      version: 'V1',
      updatedBy: profile().currentRole.userName,
      updatedAt: '刚刚',
      voidReason: ''
    }
    approvalTemplates.unshift(tpl)
    pushAudit('新增审批模板', tpl.name, '适用业务：' + tpl.bizTypeLabel + '，节点数 ' + tpl.nodes.length + '，初始版本 V1')
    return ok(clone(tpl))
  },

  /** 编辑模板（已作废模板不可编辑，版本号自动 +1） */
  updateTemplate(id, payload = {}) {
    const pa = profile().permissionActions
    if (!pa.editTemplate.allowed) return fail(pa.editTemplate.reason || '当前角色无权编辑审批模板')
    const tpl = approvalTemplates.find((t) => t.id === id)
    if (!tpl) return fail('模板不存在或已被删除')
    if (tpl.status === 'VOIDED') return fail('已作废模板不可编辑，如需启用请新建模板')
    const invalid = validateTemplatePayload(payload)
    if (invalid) return fail(invalid)
    const prevVersion = tpl.version
    tpl.name = payload.name.trim()
    tpl.bizType = payload.bizType
    tpl.bizTypeLabel = bizTypeLabelOf(payload.bizType)
    tpl.nodes = normalizeTemplateNodes(payload.nodes)
    tpl.version = 'V' + (Number(String(tpl.version).replace('V', '')) + 1)
    tpl.updatedBy = profile().currentRole.userName
    tpl.updatedAt = '刚刚'
    pushAudit('更新审批模板', tpl.name, '版本 ' + prevVersion + ' → ' + tpl.version + '，节点数 ' + tpl.nodes.length)
    return ok(clone(tpl))
  },

  /** 作废模板（逻辑作废留痕，原因必填 ≥5 字，历史单据可追溯） */
  voidTemplate(id, { reason } = {}) {
    const pa = profile().permissionActions
    if (!pa.voidTemplate.allowed) return fail(pa.voidTemplate.reason || '当前角色无权作废审批模板')
    if (!reason || reason.trim().length < 5) return fail('作废原因必填且不少于 5 个字')
    const tpl = approvalTemplates.find((t) => t.id === id)
    if (!tpl) return fail('模板不存在或已被删除')
    if (tpl.status === 'VOIDED') return fail('该模板已是作废状态')
    tpl.status = 'VOIDED'
    tpl.statusLabel = '已作废'
    tpl.voidReason = reason.trim()
    tpl.updatedBy = profile().currentRole.userName
    tpl.updatedAt = '刚刚'
    pushAudit('作废审批模板', tpl.name, '作废原因：' + reason.trim() + '；历史单据保留可追溯')
    return ok({ id, status: 'VOIDED', statusLabel: '已作废' })
  },

  /** 导出（默认脱敏 + 水印，生成审计编号并留痕） */
  exportRecords({ scope, purpose } = {}) {
    const scopeLabels = {
      TODO: '待办清单',
      DONE: '已办记录',
      CC: '抄送记录',
      RETURNED: '退回记录',
      TEMPLATE: '审批模板'
    }
    const label = scopeLabels[scope] || '审批记录'
    const auditId = 'AUD-' + String(++seq).padStart(4, '0')
    pushAudit(
      '导出记录',
      label,
      '字段已脱敏、文件含水印，审计编号 ' + auditId + (purpose ? '；导出用途：' + purpose : '')
    )
    return ok({ taskId: 'EXP-' + seq, masked: true, watermark: true, auditId })
  },

  /** 审计留痕（队首最新） */
  getAuditLogs() {
    return ok(clone(auditLogs))
  }
}

export default approvalApi
