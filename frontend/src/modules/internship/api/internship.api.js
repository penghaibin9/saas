/**
 * 岗位实习中心 API（P7：真实优先 + mock 兜底）。
 * 契约：所有方法返回 Promise<{ code, data, message }>，code=0 成功；方法签名冻结不变。
 * 真实接口 /api/v1/internship/*；后端不可达时自动回退 mock，页面不白屏。
 * 业务错误（如意见<5字 422001 / 已处理 409001）直接透出，不回退 mock。
 */
import { request, shouldTryReal } from '@/services/http/client'
import {
  tenantBrandConfig,
  currentRole,
  dataScope,
  permissionActions,
  statusOptions,
  dashboardSummary,
  internshipStudents,
  studentDetailMap,
  attendanceExceptions,
  attendanceExceptionDetailMap,
  weeklyReports,
  weeklyReportDetailMap,
  riskStudents,
  enterpriseList,
  enterpriseContactsMap,
  internshipBatches,
  internshipBatchDetailMap,
  defaultBatchStages,
  defaultBatchRules
} from '@/mocks/internship/internship.mock'

const COOP_META = {
  PENDING: { label: '待审核', tone: 'warning' }, ACTIVE: { label: '合作中', tone: 'success' },
  REJECTED: { label: '已驳回', tone: 'default' }, SUSPENDED: { label: '已暂停', tone: 'warning' },
  BLACKLIST: { label: '黑名单', tone: 'danger' }, ARCHIVED: { label: '已归档', tone: 'default' }
}

const DELAY = 120

function ok(data) {
  return new Promise((resolve) => {
    setTimeout(() => resolve({ code: 0, data, message: 'ok' }), DELAY)
  })
}

function fail(message) {
  return Promise.resolve({ code: 1, data: null, message })
}

function paginate(list, { page = 1, pageSize = 10 } = {}) {
  const total = list.length
  const start = (page - 1) * pageSize
  return { list: list.slice(start, start + pageSize), total, page, pageSize }
}

/** 真实优先：object 型返回。失败→mock；业务错误→透出 */
async function real(realFn, mockFn) {
  if (!shouldTryReal()) return mockFn()
  try {
    const data = await realFn()
    return { code: 0, data, message: 'ok' }
  } catch (e) {
    if (e.biz) return { code: e.code || 1, data: null, message: e.message }
    return mockFn()
  }
}

/** 真实优先：分页型返回，后端 items → 前端 list 映射 */
async function realList(path, params, mockFn) {
  if (!shouldTryReal()) return mockFn()
  try {
    const d = await request(path, { params })
    return { code: 0, message: 'ok',
      data: { list: d.items || [], total: d.total || 0, page: d.page || 1, pageSize: d.pageSize || 20 } }
  } catch (e) {
    if (e.biz) return { code: e.code || 1, data: null, message: e.message }
    return mockFn()
  }
}

export const internshipApi = {
  /** 品牌 / 角色 / 数据范围 / 权限动作 / 字典（页面初始化统一获取，走 mock 上下文） */
  getContext() {
    return ok({
      tenantBrandConfig: { ...tenantBrandConfig },
      currentRole: { ...currentRole },
      dataScope: { ...dataScope },
      permissionActions: JSON.parse(JSON.stringify(permissionActions)),
      statusOptions: JSON.parse(JSON.stringify(statusOptions))
    })
  },

  getDashboardSummary() {
    return real(() => request('/internship/dashboard'),
      () => ok(JSON.parse(JSON.stringify(dashboardSummary))))
  },

  // ═══════════ 实习批次（组织时间轴 + 规则骨架，状态机 DRAFT→RUNNING→CLOSED→ARCHIVED）═══════════
  getBatches(params = {}) {
    return realList('/internship/batches', params, () => this._mockBatches(params))
  },
  _mockBatches(params = {}) {
    let list = [...internshipBatches]
    if (params.keyword) {
      const kw = params.keyword.trim()
      list = list.filter((b) => b.batchName.includes(kw) || b.batchNo.includes(kw))
    }
    if (params.status) list = list.filter((b) => b.status === params.status)
    return ok(paginate(list, params))
  },

  getBatchDetail(id) {
    return real(() => request(`/internship/batches/${id}`), () => {
      const detail = internshipBatchDetailMap[id]
      if (!detail) return fail('实习批次不存在或不在当前数据范围内')
      return ok(JSON.parse(JSON.stringify(detail)))
    })
  },

  createBatch(body) {
    return real(() => request('/internship/batches', { method: 'POST', body }), () => {
      const name = (body.batchName || '').trim()
      const no = (body.batchNo || '').trim()
      if (!name || !no) return fail('批次名称与批次编号必填')
      if (internshipBatches.some((b) => b.batchNo === no)) return fail(`批次编号 ${no} 已存在`)
      const row = {
        id: 'batch-' + Date.now(), batchName: name, batchNo: no,
        academicYear: body.academicYear || '', term: body.term || '',
        startDate: body.startDate || '', endDate: body.endDate || '',
        signupStartDate: body.signupStartDate || '', signupEndDate: body.signupEndDate || '',
        plannedCount: Number(body.plannedCount || 0), actualCount: 0,
        status: 'DRAFT', statusLabel: '草稿', archiveStatus: 'NOT_ARCHIVED',
        remark: body.remark || '', updateTime: '刚刚'
      }
      internshipBatches.unshift(row)
      internshipBatchDetailMap[row.id] = {
        ...row, stages: body.stages && body.stages.length ? body.stages : defaultBatchStages,
        rules: body.rules || defaultBatchRules, previousStatus: '', lastTransitionAt: '',
        lastTransitionBy: '', transitionReason: '', archivedAt: '', archivedBy: '', archiveBatchNo: '',
        auditTrail: [{ id: 'at-' + Date.now(), action: 'CREATE', operator: currentRole.userName,
                      time: '刚刚', detail: JSON.stringify({ batchName: name, batchNo: no }) }]
      }
      return ok({ id: row.id })
    })
  },

  updateBatch(id, body) {
    return real(() => request(`/internship/batches/${id}`, { method: 'PUT', body }), () => {
      const row = internshipBatches.find((b) => b.id === id)
      const detail = internshipBatchDetailMap[id]
      if (!row || !detail) return fail('实习批次不存在')
      if (['CLOSED', 'ARCHIVED', 'VOIDED'].includes(row.status)) return fail('已结束/已归档/已作废的批次不可编辑')
      Object.assign(row, {
        batchName: body.batchName ?? row.batchName, academicYear: body.academicYear ?? row.academicYear,
        term: body.term ?? row.term, plannedCount: body.plannedCount ?? row.plannedCount,
        remark: body.remark ?? row.remark, updateTime: '刚刚'
      })
      Object.assign(detail, row)
      if (body.stages) detail.stages = body.stages
      if (body.rules) detail.rules = { ...detail.rules, ...body.rules }
      detail.auditTrail.unshift({ id: 'at-' + Date.now(), action: 'UPDATE', operator: currentRole.userName, time: '刚刚', detail: '{}' })
      return ok({ id })
    })
  },

  activateBatch(id) {
    return real(() => request(`/internship/batches/${id}/activate`, { method: 'POST' }),
      () => this._mockBatchTransition(id, 'DRAFT', 'RUNNING', '进行中', 'ACTIVATE'))
  },
  closeBatch(id) {
    return real(() => request(`/internship/batches/${id}/close`, { method: 'POST' }),
      () => this._mockBatchTransition(id, 'RUNNING', 'CLOSED', '已结束', 'CLOSE'))
  },
  archiveBatch(id) {
    return real(() => request(`/internship/batches/${id}/archive`, { method: 'POST' }),
      () => this._mockBatchTransition(id, 'CLOSED', 'ARCHIVED', '已归档', 'ARCHIVE'))
  },
  _mockBatchTransition(id, fromStatus, toStatus, toLabel, action) {
    const row = internshipBatches.find((b) => b.id === id)
    const detail = internshipBatchDetailMap[id]
    if (!row || !detail) return fail('实习批次不存在')
    if (row.status !== fromStatus) return fail(`仅「${fromStatus}」状态批次可执行该操作`)
    row.status = toStatus
    row.statusLabel = toLabel
    row.updateTime = '刚刚'
    detail.status = toStatus
    detail.statusLabel = toLabel
    detail.previousStatus = fromStatus
    detail.lastTransitionAt = '刚刚'
    detail.lastTransitionBy = currentRole.userName
    if (action === 'ARCHIVE') {
      row.archiveStatus = 'ARCHIVED'
      detail.archiveStatus = 'ARCHIVED'
      detail.archivedAt = '刚刚'
      detail.archivedBy = currentRole.userName
      detail.archiveBatchNo = row.batchNo
    }
    detail.auditTrail.unshift({ id: 'at-' + Date.now(), action, operator: currentRole.userName, time: '刚刚', detail: JSON.stringify({ before: fromStatus, after: toStatus }) })
    return ok({ id, status: toStatus, statusLabel: toLabel })
  },

  voidBatch(id, reason) {
    return real(() => request(`/internship/batches/${id}/void`, { method: 'POST', body: { reason } }), () => {
      if (!reason || reason.trim().length < 5) return fail('作废原因必填且不少于 5 个字')
      const row = internshipBatches.find((b) => b.id === id)
      const detail = internshipBatchDetailMap[id]
      if (!row || !detail) return fail('实习批次不存在')
      if (row.status !== 'DRAFT') return fail('仅草稿批次可作废，进行中/已结束请先按流程结束再归档')
      row.status = 'VOIDED'
      row.statusLabel = '已作废'
      row.updateTime = '刚刚'
      detail.status = 'VOIDED'
      detail.statusLabel = '已作废'
      detail.transitionReason = reason.trim()
      detail.auditTrail.unshift({ id: 'at-' + Date.now(), action: 'VOID', operator: currentRole.userName, time: '刚刚', detail: JSON.stringify({ reason: reason.trim() }) })
      return ok({ id, status: 'VOIDED', statusLabel: '已作废' })
    })
  },

  exportBatches(params = {}) {
    return real(() => request('/internship/batches/export', { method: 'POST', params }), () => ok({
      filename: '实习批次台账.csv',
      content: '批次名称,批次编号,状态\n' + internshipBatches.map((b) => `${b.batchName},${b.batchNo},${b.statusLabel}`).join('\n'),
      rowCount: internshipBatches.length
    }))
  },

  getStudents(params = {}) {
    return realList('/internship/students', params, () => this._mockStudents(params))
  },
  _mockStudents(params = {}) {
    let list = [...internshipStudents]
    if (params.keyword) {
      const kw = params.keyword.trim()
      list = list.filter((s) => s.name.includes(kw) || s.studentNo.includes(kw) || (s.enterpriseName || '').includes(kw))
    }
    if (params.classId) list = list.filter((s) => s.classId === params.classId)
    if (params.enterpriseId) list = list.filter((s) => s.enterpriseId === params.enterpriseId)
    if (params.status) list = list.filter((s) => s.status === params.status)
    if (params.riskLevel) list = list.filter((s) => s.riskLevel === params.riskLevel)
    return ok(paginate(list, params))
  },

  getStudentDetail(id) {
    return real(() => request(`/internship/students/${id}`), () => {
      const detail = studentDetailMap[id]
      if (!detail) return fail('未找到该学生的实习档案，或不在当前数据范围内')
      return ok(JSON.parse(JSON.stringify(detail)))
    })
  },

  getAttendanceExceptions(params = {}) {
    return realList('/internship/exceptions', params, () => this._mockExceptions(params))
  },
  _mockExceptions(params = {}) {
    let list = [...attendanceExceptions]
    if (params.type) list = list.filter((e) => e.type === params.type)
    if (params.status) list = list.filter((e) => e.status === params.status)
    if (params.keyword) list = list.filter((e) => e.studentName.includes(params.keyword.trim()))
    return ok(paginate(list, params))
  },

  getAttendanceExceptionDetail(id) {
    return real(() => request(`/internship/exceptions/${id}`), () => {
      const detail = attendanceExceptionDetailMap[id]
      if (!detail) return fail('异常记录不存在或已被处理归档')
      return ok(JSON.parse(JSON.stringify(detail)))
    })
  },

  handleAttendanceException(id, { action, comment }) {
    return real(
      () => request(`/internship/exceptions/${id}/handle`, { method: 'POST', body: { action, comment } }),
      () => this._mockHandleException(id, { action, comment })
    )
  },
  _mockHandleException(id, { action, comment }) {
    if (!comment || comment.trim().length < 5) return fail('处理意见必填且不少于 5 个字')
    const row = attendanceExceptions.find((e) => e.id === id)
    const detail = attendanceExceptionDetailMap[id]
    if (!row || !detail) return fail('异常记录不存在')
    const label = { REASONABLE: '已标记合理', ABNORMAL: '已记为异常', TO_RISK: '已转风险' }[action]
    if (!label) return fail('非法处理动作')
    row.status = 'COMPLETED'
    row.statusLabel = label
    detail.status = 'COMPLETED'
    detail.trail.push({
      title: currentRole.userName + ' · ' + label,
      desc: '处理意见：' + comment.trim() + '（已同步学生端打卡状态）',
      time: '刚刚',
      tone: action === 'REASONABLE' ? 'success' : 'danger'
    })
    return ok({ id, status: 'COMPLETED', statusLabel: label })
  },

  getWeeklyReports(params = {}) {
    return realList('/internship/reports', params, () => this._mockReports(params))
  },
  _mockReports(params = {}) {
    let list = [...weeklyReports]
    if (params.status) list = list.filter((r) => r.status === params.status)
    if (params.keyword) list = list.filter((r) => r.studentName.includes(params.keyword.trim()))
    return ok(paginate(list, params))
  },

  getWeeklyReportDetail(id) {
    return real(() => request(`/internship/reports/${id}`), () => {
      const detail = weeklyReportDetailMap[id]
      if (!detail) return fail('周报不存在或不在当前数据范围内')
      return ok(JSON.parse(JSON.stringify(detail)))
    })
  },

  reviewWeeklyReport(id, { action, comment }) {
    return real(
      () => request(`/internship/reports/${id}/review`, { method: 'POST', body: { action, comment } }),
      () => this._mockReviewReport(id, { action, comment })
    )
  },
  _mockReviewReport(id, { action, comment }) {
    if (action === 'RETURN' && (!comment || comment.trim().length < 5)) {
      return fail('退回原因必填且不少于 5 个字')
    }
    const row = weeklyReports.find((r) => r.id === id)
    const detail = weeklyReportDetailMap[id]
    if (!row || !detail) return fail('周报不存在')
    const next = action === 'APPROVE' ? { status: 'APPROVED', label: '已通过' } : { status: 'RETURNED', label: '已退回' }
    row.status = next.status
    row.statusLabel = next.label
    detail.status = next.status
    detail.trail.push({
      who: currentRole.userName,
      time: '刚刚',
      action: (action === 'APPROVE' ? '通过 ' : '退回 ') + detail.version,
      affected: (comment ? (action === 'APPROVE' ? '评语：' : '退回原因：') + comment.trim() + '；' : '') + '结果已同步学生端（P12）'
    })
    return ok({ id, status: next.status, statusLabel: next.label })
  },

  getRiskStudents(params = {}) {
    return realList('/internship/risks', params, () => this._mockRisks(params))
  },
  _mockRisks(params = {}) {
    let list = [...riskStudents]
    if (params.level) list = list.filter((r) => r.level === params.level)
    if (params.status) list = list.filter((r) => r.status === params.status)
    return ok(paginate(list, params))
  },

  // ═══════════ 企业库 ═══════════
  getEnterprises(params = {}) {
    return realList('/internship/enterprises', params, () => this._mockEnterprises(params))
  },
  _mockEnterprises(params = {}) {
    let list = [...enterpriseList]
    if (params.keyword) {
      const kw = params.keyword.trim()
      list = list.filter((e) => e.name.includes(kw) || (e.creditCode || '').includes(kw) || (e.contactPerson || '').includes(kw))
    }
    if (params.coopStatus) list = list.filter((e) => e.coopStatus === params.coopStatus)
    if (params.industry) list = list.filter((e) => e.industry === params.industry)
    if (params.region) list = list.filter((e) => e.region === params.region)
    if (params.blacklist !== undefined && params.blacklist !== '') list = list.filter((e) => e.blacklist === (params.blacklist === true || params.blacklist === 'true'))
    return ok(paginate(list, params))
  },

  getEnterpriseDetail(id) {
    return real(() => request(`/internship/enterprises/${id}`), () => {
      const e = enterpriseList.find((x) => x.id === id)
      if (!e) return fail('企业不存在或不在当前数据范围内')
      const contacts = enterpriseContactsMap[id] || []
      return ok({
        ...JSON.parse(JSON.stringify(e)),
        contacts: JSON.parse(JSON.stringify(contacts)),
        mentorCount: contacts.filter((c) => c.contactType === 'MENTOR').length,
        contactCount: contacts.filter((c) => c.contactType === 'CONTACT').length,
        auditTrail: []
      })
    })
  },

  createEnterprise(body) {
    return real(() => request('/internship/enterprises', { method: 'POST', body }), () => {
      const name = (body.name || '').trim()
      if (!name) return fail('企业名称必填')
      if (body.creditCode && enterpriseList.some((e) => e.creditCode === body.creditCode)) return fail(`统一社会信用代码已存在：${body.creditCode}`)
      const src = statusOptions.enterpriseSource.find((s) => s.value === body.source)
      const row = {
        id: 'ent-' + Date.now(), name, creditCode: body.creditCode || '', industry: body.industry || '',
        nature: body.nature || '', scale: body.scale || '', region: body.region || '', city: body.city || '',
        address: body.address || '', source: body.source || '', sourceLabel: src ? src.label : '—',
        cooperationLevel: body.cooperationLevel || '', contactPerson: body.contactPerson || '',
        contactPhoneMasked: body.contactPhone ? body.contactPhone.slice(0, 3) + '****' + body.contactPhone.slice(-4) : '',
        coopStatus: 'PENDING', coopStatusLabel: '待审核', coopStatusTone: 'warning',
        qualificationStatus: 'UNREVIEWED', qualificationLabel: '未核验', blacklist: false, blacklistReason: '',
        internCount: 0, hiredCount: 0, remark: body.remark || '', reviewBy: '', reviewAt: null,
        reviewComment: '', updatedAt: '刚刚'
      }
      enterpriseList.unshift(row)
      enterpriseContactsMap[row.id] = []
      return ok(row)
    })
  },

  updateEnterprise(id, body) {
    return real(() => request(`/internship/enterprises/${id}`, { method: 'PUT', body }), () => {
      const e = enterpriseList.find((x) => x.id === id)
      if (!e) return fail('企业不存在')
      Object.assign(e, { name: body.name ?? e.name, industry: body.industry ?? e.industry, region: body.region ?? e.region, address: body.address ?? e.address, remark: body.remark ?? e.remark, updatedAt: '刚刚' })
      return ok(JSON.parse(JSON.stringify(e)))
    })
  },

  reviewEnterprise(id, { action, comment }) {
    return real(() => request(`/internship/enterprises/${id}/review`, { method: 'POST', body: { action, comment } }), () => this._mockCoop(id, () => {
      const e = enterpriseList.find((x) => x.id === id)
      if (e.coopStatus !== 'PENDING') return fail('仅「待审核」企业可审核')
      e.coopStatus = action === 'APPROVE' ? 'ACTIVE' : 'REJECTED'
      e.qualificationStatus = action === 'APPROVE' ? 'PASSED' : 'FAILED'
      e.qualificationLabel = action === 'APPROVE' ? '资质通过' : '资质不通过'
      return e
    }))
  },

  setEnterpriseCooperation(id, { action, reason }) {
    return real(() => request(`/internship/enterprises/${id}/cooperation`, { method: 'POST', body: { action, reason } }), () => this._mockCoop(id, () => {
      const e = enterpriseList.find((x) => x.id === id)
      if (action === 'SUSPEND') { if (e.coopStatus !== 'ACTIVE') return fail('仅「合作中」企业可暂停'); e.coopStatus = 'SUSPENDED' } else if (action === 'RESUME') { if (e.coopStatus !== 'SUSPENDED') return fail('仅「已暂停」企业可恢复'); e.coopStatus = 'ACTIVE' } else if (action === 'ARCHIVE') { if (['ARCHIVED', 'BLACKLIST'].includes(e.coopStatus)) return fail('黑名单/已归档不可再归档'); e.coopStatus = 'ARCHIVED' } else return fail('非法动作')
      return e
    }))
  },

  setEnterpriseBlacklist(id, { on, reason }) {
    return real(() => request(`/internship/enterprises/${id}/blacklist`, { method: 'POST', body: { on, reason } }), () => this._mockCoop(id, () => {
      const e = enterpriseList.find((x) => x.id === id)
      if (on) { if (!(reason || '').trim()) return fail('拉黑必须填写原因'); e.blacklist = true; e.blacklistReason = reason.trim(); e.coopStatus = 'BLACKLIST' } else { if (!e.blacklist) return fail('该企业不在黑名单中'); e.blacklist = false; e.blacklistReason = ''; e.coopStatus = 'ACTIVE' }
      return e
    }))
  },

  _mockCoop(id, mutate) {
    const e = enterpriseList.find((x) => x.id === id)
    if (!e) return fail('企业不存在')
    const r = mutate()
    if (r && r.code === 1) return r
    const meta = COOP_META[e.coopStatus]
    e.coopStatusLabel = meta.label
    e.coopStatusTone = meta.tone
    e.updatedAt = '刚刚'
    return ok(JSON.parse(JSON.stringify(e)))
  },

  getEnterpriseContacts(id) {
    return real(() => request(`/internship/enterprises/${id}/contacts`).then((d) => ({ items: d.items || [] })), () => ok({ items: JSON.parse(JSON.stringify(enterpriseContactsMap[id] || [])) }))
  },

  addEnterpriseContact(id, body) {
    return real(() => request(`/internship/enterprises/${id}/contacts`, { method: 'POST', body }), () => {
      if (!(body.name || '').trim()) return fail('姓名必填')
      const list = enterpriseContactsMap[id] || (enterpriseContactsMap[id] = [])
      if (body.isPrimary) list.forEach((c) => { if (c.contactType === (body.contactType || 'CONTACT')) c.isPrimary = false })
      const row = { id: 'ec-' + Date.now(), companyId: id, contactType: body.contactType || 'CONTACT', contactTypeLabel: body.contactType === 'MENTOR' ? '企业导师' : '联系人', name: body.name.trim(), title: body.title || '', phoneMasked: body.phone ? body.phone.slice(0, 3) + '****' + body.phone.slice(-4) : '', email: body.email || '', isPrimary: !!body.isPrimary, remark: body.remark || '', status: 'ACTIVE' }
      list.push(row)
      return ok(row)
    })
  },

  updateEnterpriseContact(id, contactId, body) {
    return real(() => request(`/internship/enterprises/${id}/contacts/${contactId}`, { method: 'PUT', body }), () => {
      const list = enterpriseContactsMap[id] || []
      const c = list.find((x) => x.id === contactId)
      if (!c) return fail('联系人不存在')
      if (body.isPrimary) list.forEach((x) => { if (x.contactType === c.contactType) x.isPrimary = false })
      Object.assign(c, { name: body.name ?? c.name, title: body.title ?? c.title, email: body.email ?? c.email, remark: body.remark ?? c.remark, isPrimary: body.isPrimary ?? c.isPrimary })
      return ok(JSON.parse(JSON.stringify(c)))
    })
  },

  deleteEnterpriseContact(id, contactId) {
    return real(() => request(`/internship/enterprises/${id}/contacts/${contactId}`, { method: 'DELETE' }), () => {
      const list = enterpriseContactsMap[id] || []
      const i = list.findIndex((x) => x.id === contactId)
      if (i < 0) return fail('联系人不存在')
      list.splice(i, 1)
      return ok({ id: contactId, deleted: true })
    })
  },

  getEnterpriseStats() {
    return real(() => request('/internship/enterprises/stats'), () => {
      const by = statusOptions.coopStatus.map((s) => ({ status: s.value, label: s.label, count: enterpriseList.filter((e) => e.coopStatus === s.value).length }))
      return ok({ total: enterpriseList.length, byCoopStatus: by, blacklistCount: enterpriseList.filter((e) => e.blacklist).length, byIndustry: [] })
    })
  },

  importEnterprisesDryRun(rows) {
    return real(() => request('/internship/enterprises/import/dry-run', { method: 'POST', body: { rows } }), () => {
      const errors = []; const seen = new Set(); let valid = 0
      const existing = new Set(enterpriseList.map((e) => e.creditCode).filter(Boolean))
      rows.forEach((r, i) => {
        if (!(r.name || '').trim()) { errors.push({ rowNo: i + 1, field: 'name', message: '企业名称必填' }); return }
        const cc = (r.creditCode || '').trim()
        if (cc && existing.has(cc)) { errors.push({ rowNo: i + 1, field: 'creditCode', message: `信用代码库内已存在：${cc}` }); return }
        if (cc && seen.has(cc)) { errors.push({ rowNo: i + 1, field: 'creditCode', message: `文件内重复：${cc}` }); return }
        if (cc) seen.add(cc)
        valid++
      })
      return ok({ total: rows.length, validRows: valid, invalidRows: errors.length, errors })
    })
  },

  importEnterprisesConfirm(rows) {
    return real(() => request('/internship/enterprises/import/confirm', { method: 'POST', body: { rows } }), () => ok({ created: rows.length }))
  },

  exportEnterprises(params = {}) {
    return real(() => request('/internship/enterprises/export', { method: 'POST', params }), () => ok({ filename: '企业库导出.csv', content: '企业名称,合作状态\n（mock 导出）', rowCount: enterpriseList.length }))
  }
}

export default internshipApi
