/**
 * 学生中心 API（mock 实现，PC 管理端新版页面统一入口）。
 * 契约：所有方法返回 Promise<{ code, data, message }>，code=0 成功。
 * 真实后端阶段仅替换实现，方法签名冻结不变（与 internship / dataCenter / approval 模块同约定）。
 * 页面禁止直接 import mocks，必须经本文件获取数据；写操作真实变更内存数据并写入审计留痕。
 * 说明：modules/student 下旧 provider（student.api.mock.js 等）为 01 期契约资产，保持不动；
 * 本文件是 PC-STUDENT-DATA-RUN 任务的学生中心门面。
 */
import {
  tenantBrandConfig,
  mockRuntime,
  roleProfiles,
  metricDefs,
  students,
  getDetailPreset,
  statusChangeRecords,
  identityRecords,
  correctionRequests,
  riskTags,
  importTemplates,
  exportOptions,
  transferTasks,
  importValidatePreset,
  fieldColumns,
  statusOptions,
  filterOptions,
  classList,
  auditLogs
} from '@/mocks/student/student.mock'

const DELAY = 120

function ok(data) {
  return new Promise((resolve) => {
    setTimeout(() => resolve({ code: 0, data, message: 'ok' }), DELAY)
  })
}

function fail(message) {
  return Promise.resolve({ code: 1, data: null, message })
}

function clone(v) {
  return JSON.parse(JSON.stringify(v))
}

function paginate(list, { page = 1, pageSize = 10 } = {}) {
  const total = list.length
  const start = (page - 1) * pageSize
  return { list: clone(list.slice(start, start + pageSize)), total, page, pageSize }
}

function profile() {
  return roleProfiles[mockRuntime.activeRoleCode] || roleProfiles.REGISTRAR
}

function nowText() {
  const d = new Date()
  const p = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`
}

let seq = 100

function pushAudit(action, targetType, targetName, detail) {
  const p = profile()
  auditLogs.unshift({
    id: `aud-${++seq}`,
    time: nowText(),
    operator: p.currentRole.userName,
    roleName: p.currentRole.roleName,
    action,
    targetType,
    targetName,
    detail,
    result: '成功'
  })
  return auditLogs[0].id
}

/** 数据范围过滤：辅导员按所带班级、学院管理员按学院，全校角色不过滤 */
function inScope(item) {
  const p = profile()
  if (p.scopeClassIds.length) return p.scopeClassIds.includes(item.classId)
  if (p.scopeCollegeIds.length) return p.scopeCollegeIds.includes(item.collegeId)
  return true
}

function scopedStudents({ includeVoided = false } = {}) {
  return students.filter((s) => (includeVoided || !s.voided) && inScope(s))
}

function findStudent(id) {
  return students.find((s) => s.studentId === id)
}

function studentLabel(s) {
  return `${s.name}（${s.studentNo}）`
}

const kw = (text, k) => !k || String(text || '').includes(String(k).trim())

export const studentApi = {
  /** 品牌 / 角色 / 数据范围 / 权限动作 / 字典（模块布局初始化统一获取） */
  getContext() {
    const p = profile()
    return ok({
      tenantBrandConfig: clone(tenantBrandConfig),
      currentRole: clone(p.currentRole),
      dataScope: clone(p.dataScope),
      permissionActions: clone(p.permissionActions),
      statusOptions: clone(statusOptions),
      filterOptions: clone(filterOptions),
      availableRoles: Object.values(roleProfiles).map((r) => ({
        value: r.currentRole.roleCode,
        label: r.currentRole.roleName
      }))
    })
  },

  /** 切换演示角色（体现不同角色指标 / 数据范围 / 按钮差异） */
  switchRole(roleCode) {
    if (!roleProfiles[roleCode]) return fail('角色不存在')
    mockRuntime.activeRoleCode = roleCode
    return ok({ roleCode })
  },

  /** 学生中心看板（指标按当前角色 metricKeys 过滤，数值实时计算） */
  getDashboardSummary() {
    const p = profile()
    const list = scopedStudents()
    const pendingCorrections = correctionRequests.filter(
      (c) => c.status === 'PENDING_REVIEW' && inScope(c)
    )
    const pendingIdentity = identityRecords.filter((r) => r.status === 'PENDING_REVIEW' && inScope(r))
    const activeRisk = riskTags.filter((t) => ['ACTIVE', 'FOLLOWING'].includes(t.status) && inScope(t))
    const monthPrefix = nowText().slice(0, 7)
    const values = {
      total: list.length,
      active: list.filter((s) => s.studentStatus === 'ACTIVE').length,
      pendingIdentity: pendingIdentity.length,
      pendingCorrection: pendingCorrections.length,
      statusChangedMonth: statusChangeRecords.filter(
        (r) => inScope({ classId: findStudent(r.studentId)?.classId, collegeId: findStudent(r.studentId)?.collegeId }) && r.operatedAt.startsWith(monthPrefix)
      ).length,
      dataComplete: list.length
        ? Math.round(list.reduce((sum, s) => sum + s.dataCompleteness, 0) / list.length)
        : 0,
      highRisk: list.filter((s) => s.riskLevel === 'HIGH').length,
      riskFollowing: activeRisk.filter((t) => t.status === 'FOLLOWING').length,
      academicWarning: activeRisk.filter((t) => t.tagType === 'ACADEMIC').length,
      graduatingCount: list.filter((s) => s.grade === '2023级' && s.studentStatus === 'ACTIVE').length,
      accountUnbound: list.filter((s) => s.accountBindStatus === 'UNBOUND').length,
      auditWeek: auditLogs.length
    }
    const stats = p.metricKeys.map((key) => ({
      key,
      label: metricDefs[key].label,
      value: metricDefs[key].unit === '%' ? `${values[key]}%` : String(values[key]),
      unit: metricDefs[key].unit
    }))
    const flow = statusOptions.studentStatusFlow.map((s) => ({
      label: s.label,
      value: list.filter((x) => x.studentStatus === s.value).length,
      active: s.value === 'ACTIVE'
    }))
    const todos = [
      {
        key: 'identity',
        label: '待复核身份核验',
        count: pendingIdentity.length,
        tone: 'warning',
        hint: pendingIdentity.length ? `最早提交于 ${pendingIdentity[pendingIdentity.length - 1].checkedAt}` : '暂无待办',
        route: '/admin/student/identity'
      },
      {
        key: 'correction',
        label: '待审核信息更正',
        count: pendingCorrections.length,
        tone: 'warning',
        hint: pendingCorrections.some((c) => c.sensitive) ? '含证件 / 联系方式等敏感字段' : '常规字段更正',
        route: '/admin/student/corrections'
      },
      {
        key: 'risk',
        label: '风险标签待跟进',
        count: activeRisk.length,
        tone: activeRisk.some((t) => t.level === 'HIGH') ? 'danger' : 'warning',
        hint: activeRisk.some((t) => t.level === 'HIGH') ? '含高风险 1 条以上' : '以低中风险为主',
        route: '/admin/student/risk-tags'
      }
    ]
    const recentChanges = clone(
      statusChangeRecords.filter((r) => {
        const s = findStudent(r.studentId)
        return s && inScope(s)
      })
    ).slice(0, 5)
    return ok({
      stats,
      flow,
      todos,
      recentChanges,
      recentAudits: clone(auditLogs.slice(0, 6))
    })
  },

  /* ================= 学生主档列表 ================= */

  getStudents(params = {}) {
    let list = scopedStudents({ includeVoided: params.includeVoided === true || params.includeVoided === 'true' })
    if (params.keyword) {
      list = list.filter(
        (s) => kw(s.name, params.keyword) || kw(s.studentNo, params.keyword) || kw(s.phone, params.keyword)
      )
    }
    if (params.collegeId) list = list.filter((s) => s.collegeId === params.collegeId)
    if (params.majorId) list = list.filter((s) => s.majorId === params.majorId)
    if (params.classId) list = list.filter((s) => s.classId === params.classId)
    if (params.grade) list = list.filter((s) => s.grade === params.grade)
    if (params.studentStatus) list = list.filter((s) => s.studentStatus === params.studentStatus)
    if (params.identityVerifyStatus)
      list = list.filter((s) => s.identityVerifyStatus === params.identityVerifyStatus)
    if (params.riskLevel) list = list.filter((s) => s.riskLevel === params.riskLevel)
    return ok(paginate(list, params))
  },

  /** 学生360：主档 + 全生命周期关联记录 + 审计 */
  getStudentDetail(studentId) {
    const s = findStudent(studentId)
    if (!s || !inScope(s)) return fail('学生不存在或不在当前数据范围内')
    const preset = getDetailPreset(studentId)
    const detail = {
      ...clone(s),
      ...clone(preset),
      statusHistory: clone(statusChangeRecords.filter((r) => r.studentId === studentId)),
      identityRecords: clone(identityRecords.filter((r) => r.studentId === studentId)),
      corrections: clone(correctionRequests.filter((r) => r.studentId === studentId)),
      riskTags: clone(riskTags.filter((r) => r.studentId === studentId && r.status !== 'VOIDED')),
      auditTrail: clone(
        auditLogs.filter((a) => a.targetName && a.targetName.includes(s.name)).slice(0, 10)
      )
    }
    pushAudit('查看学生360', 'STUDENT', studentLabel(s), '敏感字段按当前角色权限脱敏展示')
    return ok(detail)
  },

  createStudent(payload = {}) {
    const name = String(payload.name || '').trim()
    const studentNo = String(payload.studentNo || '').trim()
    if (!name || !studentNo || !payload.classId) return fail('姓名、学号、班级为必填项')
    if (students.some((s) => s.studentNo === studentNo)) return fail(`学号 ${studentNo} 已存在，不可重复建档`)
    const cls = classList.find((c) => c.value === payload.classId)
    if (!cls) return fail('班级不存在于组织字典')
    const major = filterOptions.majors.find((m) => m.value === cls.majorId)
    const college = filterOptions.colleges.find((c) => c.value === cls.collegeId)
    const item = {
      studentId: `stu-${Date.now()}`,
      name,
      gender: payload.gender || '男',
      studentNo,
      idCard: payload.idCard || '',
      phone: payload.phone || '',
      collegeId: cls.collegeId,
      collegeName: college ? college.label : '',
      majorId: cls.majorId,
      majorName: major ? major.label : '',
      classId: cls.value,
      className: cls.label,
      grade: payload.grade || '2026级',
      enrollDate: payload.enrollDate || nowText().slice(0, 10),
      counselorName: cls.counselorName,
      studentStatus: 'ADMITTED',
      identityVerifyStatus: 'PENDING',
      accountBindStatus: 'UNBOUND',
      riskLevel: 'NONE',
      dataCompleteness: 60,
      voided: false,
      voidReason: '',
      updatedAt: nowText()
    }
    students.unshift(item)
    pushAudit('新增学生主档', 'STUDENT', studentLabel(item), `建档班级：${cls.label}`)
    return ok(clone(item))
  },

  updateStudent(studentId, payload = {}) {
    const s = findStudent(studentId)
    if (!s || !inScope(s)) return fail('学生不存在或不在当前数据范围内')
    const editable = ['name', 'gender', 'phone', 'idCard', 'grade', 'counselorName']
    const changed = []
    editable.forEach((k) => {
      if (payload[k] !== undefined && payload[k] !== s[k]) {
        changed.push(`${k}：${s[k] || '空'} → ${payload[k]}`)
        s[k] = payload[k]
      }
    })
    if (payload.classId && payload.classId !== s.classId) {
      const cls = classList.find((c) => c.value === payload.classId)
      if (!cls) return fail('班级不存在于组织字典')
      changed.push(`班级：${s.className} → ${cls.label}`)
      s.classId = cls.value
      s.className = cls.label
      s.counselorName = cls.counselorName
    }
    if (!changed.length) return fail('未检测到任何字段变更')
    s.updatedAt = nowText()
    pushAudit('编辑学生信息', 'STUDENT', studentLabel(s), changed.join('；'))
    return ok(clone(s))
  },

  /** 作废主档（逻辑删除，不物理删除，原因必填） */
  voidStudent(studentId, { reason } = {}) {
    const s = findStudent(studentId)
    if (!s) return fail('学生不存在')
    if (s.voided) return fail('该学生主档已是作废状态')
    const r = String(reason || '').trim()
    if (r.length < 5) return fail('作废原因必填且不少于 5 个字')
    s.voided = true
    s.studentStatus = 'VOIDED'
    s.voidReason = r
    s.updatedAt = nowText()
    pushAudit('作废学生主档', 'STUDENT', studentLabel(s), `作废原因：${r}（逻辑删除，可追溯）`)
    return ok(clone(s))
  },

  batchAssignClass(studentIds = [], classId) {
    const cls = classList.find((c) => c.value === classId)
    if (!cls) return fail('目标班级不存在')
    if (!studentIds.length) return fail('请先勾选学生')
    let count = 0
    studentIds.forEach((id) => {
      const s = findStudent(id)
      if (s && inScope(s) && !s.voided) {
        s.classId = cls.value
        s.className = cls.label
        s.counselorName = cls.counselorName
        s.updatedAt = nowText()
        count++
      }
    })
    pushAudit('批量分班', 'STUDENT', `${count} 名学生`, `目标班级：${cls.label}`)
    return ok({ count, className: cls.label })
  },

  batchAssignCounselor(studentIds = [], counselorName) {
    if (!counselorName) return fail('请选择辅导员')
    if (!studentIds.length) return fail('请先勾选学生')
    let count = 0
    studentIds.forEach((id) => {
      const s = findStudent(id)
      if (s && inScope(s) && !s.voided) {
        s.counselorName = counselorName
        s.updatedAt = nowText()
        count++
      }
    })
    pushAudit('批量分配辅导员', 'STUDENT', `${count} 名学生`, `辅导员：${counselorName}`)
    return ok({ count, counselorName })
  },

  batchRemind(studentIds = []) {
    if (!studentIds.length) return fail('请先勾选学生')
    pushAudit('批量提醒', 'STUDENT', `${studentIds.length} 名学生`, '站内信 + 学生小程序推送')
    return ok({ count: studentIds.length })
  },

  /* ================= 学籍状态管理 ================= */

  getStatusRecords(params = {}) {
    let list = statusChangeRecords.filter((r) => {
      const s = findStudent(r.studentId)
      return s && inScope(s)
    })
    if (params.keyword) list = list.filter((r) => kw(r.studentName, params.keyword))
    if (params.toStatus) list = list.filter((r) => r.toStatus === params.toStatus)
    if (params.dateFrom) list = list.filter((r) => r.operatedAt >= params.dateFrom)
    return ok(paginate(list, params))
  },

  /** 学籍状态变更（原因必填，留痕） */
  changeStatus(studentId, { toStatus, reason, attachment } = {}) {
    const s = findStudent(studentId)
    if (!s || !inScope(s)) return fail('学生不存在或不在当前数据范围内')
    if (s.voided) return fail('已作废主档不可变更状态')
    const target = statusOptions.studentStatusFlow.find((o) => o.value === toStatus)
    if (!target) return fail('非法的目标学籍状态')
    if (s.studentStatus === toStatus) return fail('目标状态与当前状态一致，无需变更')
    const r = String(reason || '').trim()
    if (r.length < 5) return fail('状态变更原因必填且不少于 5 个字')
    const p = profile()
    const fromStatus = s.studentStatus
    s.studentStatus = toStatus
    s.updatedAt = nowText()
    statusChangeRecords.unshift({
      id: `sc-${Date.now()}`,
      studentId,
      studentName: s.name,
      className: s.className,
      fromStatus,
      toStatus,
      reason: r,
      attachment: attachment || '',
      operator: p.currentRole.userName,
      roleName: p.currentRole.roleName,
      operatedAt: nowText()
    })
    const fromLabel = statusOptions.studentStatus.find((o) => o.value === fromStatus)?.label || fromStatus
    pushAudit('学籍状态变更', 'STUDENT', studentLabel(s), `${fromLabel} → ${target.label}（${r}）`)
    return ok(clone(s))
  },

  batchChangeStatus(studentIds = [], { toStatus, reason } = {}) {
    if (!studentIds.length) return fail('请先选择学生')
    const r = String(reason || '').trim()
    if (r.length < 5) return fail('批量变更原因必填且不少于 5 个字')
    let success = 0
    const skipped = []
    return Promise.all(
      studentIds.map((id) =>
        this.changeStatus(id, { toStatus, reason: r }).then((res) => {
          if (res.code === 0) success++
          else skipped.push(res.message)
        })
      )
    ).then(() => ({
      code: 0,
      message: 'ok',
      data: { success, skipped: skipped.length, skippedReasons: skipped.slice(0, 3) }
    }))
  },

  /* ================= 身份核验 ================= */

  getIdentityRecords(params = {}) {
    let list = identityRecords.filter((r) => inScope(r) || inScope(findStudent(r.studentId) || {}))
    if (params.keyword) list = list.filter((r) => kw(r.studentName, params.keyword))
    if (params.status) list = list.filter((r) => r.status === params.status)
    if (params.result) list = list.filter((r) => r.result === params.result)
    return ok(paginate(list, params))
  },

  /** 人工复核：CONFIRM 确认通过 / RETURN 退回重验（退回原因必填） */
  reviewIdentityRecord(recordId, { action, comment } = {}) {
    const rec = identityRecords.find((r) => r.id === recordId)
    if (!rec) return fail('核验记录不存在')
    if (rec.status !== 'PENDING_REVIEW') return fail('该记录已复核，不可重复操作')
    const p = profile()
    const note = String(comment || '').trim()
    if (action === 'CONFIRM') {
      rec.status = 'CONFIRMED'
      rec.result = 'PASS'
      rec.reviewer = p.currentRole.userName
      rec.reviewComment = note || '人工复核通过'
      const s = findStudent(rec.studentId)
      if (s) s.identityVerifyStatus = 'VERIFIED'
      pushAudit('身份核验复核通过', 'IDENTITY', `${rec.studentName} · ${rec.method}`, rec.reviewComment)
      return ok(clone(rec))
    }
    if (action === 'RETURN') {
      if (note.length < 5) return fail('退回原因必填且不少于 5 个字')
      rec.status = 'CONFIRMED'
      rec.result = 'FAIL'
      rec.reviewer = p.currentRole.userName
      rec.reviewComment = note
      const s = findStudent(rec.studentId)
      if (s) s.identityVerifyStatus = 'REJECTED'
      pushAudit('身份核验退回重验', 'IDENTITY', `${rec.studentName} · ${rec.method}`, note)
      return ok(clone(rec))
    }
    return fail('非法的复核动作')
  },

  markIdentityAbnormal(recordId, { reason } = {}) {
    const rec = identityRecords.find((r) => r.id === recordId)
    if (!rec) return fail('核验记录不存在')
    if (rec.status === 'ABNORMAL') return fail('该记录已标记异常')
    const r = String(reason || '').trim()
    if (r.length < 5) return fail('异常说明必填且不少于 5 个字')
    const p = profile()
    rec.status = 'ABNORMAL'
    rec.reviewer = p.currentRole.userName
    rec.reviewComment = r
    const s = findStudent(rec.studentId)
    if (s) s.identityVerifyStatus = 'ABNORMAL'
    pushAudit('标记核验异常', 'IDENTITY', `${rec.studentName} · ${rec.method}`, r)
    return ok(clone(rec))
  },

  /* ================= 信息更正审核 ================= */

  getCorrections(params = {}) {
    let list = correctionRequests.filter((r) => inScope(r) || inScope(findStudent(r.studentId) || {}))
    if (params.keyword) list = list.filter((r) => kw(r.studentName, params.keyword) || kw(r.fieldLabel, params.keyword))
    if (params.status) list = list.filter((r) => r.status === params.status)
    if (params.channel) list = list.filter((r) => r.channel === params.channel)
    return ok(paginate(list, params))
  },

  getCorrectionDetail(id) {
    const rec = correctionRequests.find((r) => r.id === id)
    if (!rec) return fail('更正申请不存在')
    return ok(clone(rec))
  },

  /** 更正审核：APPROVE 通过（同步主档）/ RETURN 退回（原因必填） */
  reviewCorrection(id, { action, reason } = {}) {
    const rec = correctionRequests.find((r) => r.id === id)
    if (!rec) return fail('更正申请不存在')
    if (rec.status !== 'PENDING_REVIEW') return fail('该申请已审核，不可重复操作')
    const p = profile()
    const note = String(reason || '').trim()
    if (action === 'APPROVE') {
      rec.status = 'APPROVED'
      rec.reviewer = p.currentRole.userName
      rec.reviewTime = nowText()
      rec.reviewComment = note || '审核通过，主档已同步更新'
      const s = findStudent(rec.studentId)
      if (s && ['phone', 'idCard', 'name'].includes(rec.fieldKey)) {
        s[rec.fieldKey] = rec.newValue
        s.updatedAt = nowText()
      }
      pushAudit(
        '更正审核通过',
        'CORRECTION',
        `${rec.studentName} · ${rec.fieldLabel}更正`,
        `${rec.oldValue} → ${rec.newValue}`
      )
      return ok(clone(rec))
    }
    if (action === 'RETURN') {
      if (note.length < 5) return fail('退回原因必填且不少于 5 个字')
      rec.status = 'RETURNED'
      rec.reviewer = p.currentRole.userName
      rec.reviewTime = nowText()
      rec.reviewComment = note
      pushAudit('更正审核退回', 'CORRECTION', `${rec.studentName} · ${rec.fieldLabel}更正`, `退回原因：${note}`)
      return ok(clone(rec))
    }
    return fail('非法的审核动作')
  },

  /* ================= 风险标签 ================= */

  getRiskTags(params = {}) {
    let list = riskTags.filter((t) => inScope(t) || inScope(findStudent(t.studentId) || {}))
    if (params.keyword) list = list.filter((t) => kw(t.studentName, params.keyword) || kw(t.title, params.keyword))
    if (params.tagType) list = list.filter((t) => t.tagType === params.tagType)
    if (params.level) list = list.filter((t) => t.level === params.level)
    if (params.status) list = list.filter((t) => t.status === params.status)
    return ok(paginate(list, params))
  },

  createRiskTag(payload = {}) {
    const s = findStudent(payload.studentId)
    if (!s || !inScope(s)) return fail('学生不存在或不在当前数据范围内')
    const title = String(payload.title || '').trim()
    if (title.length < 4) return fail('标签标题必填且不少于 4 个字')
    const type = statusOptions.riskTagType.find((t) => t.value === payload.tagType)
    if (!type) return fail('请选择风险类型')
    const p = profile()
    const item = {
      id: `rt-${Date.now()}`,
      studentId: s.studentId,
      studentName: s.name,
      className: s.className,
      tagType: type.value,
      tagTypeLabel: type.label,
      level: payload.level || 'LOW',
      title,
      description: String(payload.description || '').trim(),
      source: 'MANUAL',
      sourceLabel: '人工创建',
      status: 'ACTIVE',
      owner: p.currentRole.userName,
      createdAt: nowText(),
      voidReason: '',
      followUps: []
    }
    riskTags.unshift(item)
    if (item.level === 'HIGH' || (s.riskLevel === 'NONE' && item.level !== 'NONE')) s.riskLevel = item.level
    pushAudit('新增风险标签', 'RISK_TAG', `${s.name} · ${title}`, `${type.label} / ${item.level}`)
    return ok(clone(item))
  },

  updateRiskTag(id, payload = {}) {
    const t = riskTags.find((x) => x.id === id)
    if (!t) return fail('风险标签不存在')
    if (t.status === 'VOIDED') return fail('已作废标签不可编辑')
    const changed = []
    ;['title', 'description', 'level', 'status', 'owner'].forEach((k) => {
      if (payload[k] !== undefined && payload[k] !== t[k]) {
        changed.push(k)
        t[k] = payload[k]
      }
    })
    if (!changed.length) return fail('未检测到任何字段变更')
    pushAudit('编辑风险标签', 'RISK_TAG', `${t.studentName} · ${t.title}`, `变更字段：${changed.join('、')}`)
    return ok(clone(t))
  },

  voidRiskTag(id, { reason } = {}) {
    const t = riskTags.find((x) => x.id === id)
    if (!t) return fail('风险标签不存在')
    if (t.status === 'VOIDED') return fail('该标签已作废')
    const r = String(reason || '').trim()
    if (r.length < 5) return fail('作废原因必填且不少于 5 个字')
    t.status = 'VOIDED'
    t.voidReason = r
    pushAudit('作废风险标签', 'RISK_TAG', `${t.studentName} · ${t.title}`, `作废原因：${r}`)
    return ok(clone(t))
  },

  addRiskFollowUp(id, { note } = {}) {
    const t = riskTags.find((x) => x.id === id)
    if (!t) return fail('风险标签不存在')
    if (t.status === 'VOIDED' || t.status === 'RESOLVED') return fail('已解除 / 已作废标签无需跟进')
    const n = String(note || '').trim()
    if (n.length < 5) return fail('跟进记录必填且不少于 5 个字')
    const p = profile()
    t.followUps.unshift({ time: nowText(), who: p.currentRole.userName, note: n })
    t.status = 'FOLLOWING'
    pushAudit('风险跟进', 'RISK_TAG', `${t.studentName} · ${t.title}`, n)
    return ok(clone(t))
  },

  batchRemindRisk(ids = []) {
    if (!ids.length) return fail('请先勾选风险标签')
    pushAudit('风险批量提醒', 'RISK_TAG', `${ids.length} 条风险标签`, '已通知责任人与学生（站内信 + 小程序）')
    return ok({ count: ids.length })
  },

  /* ================= 导入 / 导出 ================= */

  getImportTemplates() {
    return ok(clone(importTemplates))
  },

  /** 导入校验（mock 不解析真实文件，返回校验预览） */
  validateImport({ templateId, fileName } = {}) {
    const tpl = importTemplates.find((t) => t.id === templateId)
    if (!tpl) return fail('请先选择导入模板')
    if (!fileName) return fail('请先选择数据文件')
    pushAudit('导入校验', 'IMPORT', tpl.name, `文件：${fileName}，${importValidatePreset.errorRows} 条错误待处理`)
    return ok({ ...clone(importValidatePreset), templateName: tpl.name, fileName })
  },

  /** 确认导入（生成回执 + 审计） */
  confirmImport({ templateId, fileName, skipErrors } = {}) {
    const tpl = importTemplates.find((t) => t.id === templateId)
    if (!tpl) return fail('导入模板不存在')
    const preset = importValidatePreset
    const success = skipErrors ? preset.validRows : preset.totalRows - preset.errorRows
    const auditId = pushAudit(
      '批量导入',
      'IMPORT',
      tpl.name,
      `文件：${fileName}，导入 ${preset.totalRows} 条，成功 ${success} 条，失败 ${preset.errorRows} 条`
    )
    const task = {
      id: `task-${Date.now()}`,
      type: 'IMPORT',
      typeLabel: '导入',
      title: tpl.name,
      fileName,
      totalRows: preset.totalRows,
      successRows: success,
      failedRows: preset.errorRows,
      status: 'COMPLETED',
      operator: profile().currentRole.userName,
      roleName: profile().currentRole.roleName,
      time: nowText(),
      masked: false,
      watermark: false,
      auditId
    }
    transferTasks.unshift(task)
    return ok(clone(task))
  },

  getExportOptions() {
    return ok(clone(exportOptions))
  },

  /** 创建导出任务（强制脱敏 + 水印 + 审计确认） */
  createExport({ scope, fieldKeys = [], purpose, remark, rowCount } = {}) {
    const scopeDef = exportOptions.scopes.find((s) => s.value === scope)
    if (!scopeDef) return fail('请选择导出范围')
    if (!fieldKeys.length) return fail('请至少选择一个导出字段')
    const purposeDef = exportOptions.purposes.find((p) => p.value === purpose)
    if (!purposeDef) return fail('导出用途必选（用于审计留痕）')
    const sensitiveCount = exportOptions.fieldGroups
      .flatMap((g) => g.fields)
      .filter((f) => fieldKeys.includes(f.key) && f.sensitive).length
    const p = profile()
    const auditId = pushAudit(
      '导出台账',
      'EXPORT',
      `${scopeDef.label}（${rowCount ?? scopedStudents().length} 条）`,
      `用途：${purposeDef.label}${remark ? `（${remark}）` : ''}；敏感字段 ${sensitiveCount} 个已脱敏；文件含「${tenantBrandConfig.watermarkText}」水印`
    )
    const task = {
      id: `task-${Date.now()}`,
      type: 'EXPORT',
      typeLabel: '导出',
      title: scopeDef.label,
      fileName: `student-export-${Date.now()}.xlsx`,
      totalRows: rowCount ?? scopedStudents().length,
      successRows: rowCount ?? scopedStudents().length,
      failedRows: 0,
      status: 'COMPLETED',
      operator: p.currentRole.userName,
      roleName: p.currentRole.roleName,
      time: nowText(),
      masked: true,
      watermark: true,
      auditId
    }
    transferTasks.unshift(task)
    return ok(clone(task))
  },

  getTransferTasks() {
    return ok(clone(transferTasks))
  },

  /* ================= 审计 / 列设置 ================= */

  getAuditLogs(params = {}) {
    let list = [...auditLogs]
    if (params.keyword) list = list.filter((a) => kw(a.targetName, params.keyword) || kw(a.action, params.keyword))
    return ok(paginate(list, { page: params.page || 1, pageSize: params.pageSize || 10 }))
  },

  getFieldColumns(viewKey) {
    if (!fieldColumns[viewKey]) return fail('未配置该视图的列定义')
    return ok(clone(fieldColumns[viewKey]))
  },

  saveFieldColumns(viewKey, columns = []) {
    if (!fieldColumns[viewKey]) return fail('未配置该视图的列定义')
    const lockedKeys = fieldColumns[viewKey].filter((c) => c.locked).map((c) => c.key)
    const incoming = columns.map((c) => c.key)
    if (lockedKeys.some((k) => !incoming.includes(k))) return fail('固定列不可移除')
    fieldColumns[viewKey] = clone(columns)
    pushAudit('表格列设置', 'CONFIG', `视图：${viewKey}`, `可见列 ${columns.filter((c) => c.visible).length} 个`)
    return ok(clone(fieldColumns[viewKey]))
  }
}

export default studentApi
