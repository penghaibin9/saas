/**
 * 岗位实习中心 API（mock 实现）。
 * 契约：所有方法返回 Promise<{ code, data, message }>，code=0 成功。
 * 真实后端阶段仅替换实现，方法签名冻结不变（与 dashboard/student 模块同约定）。
 * 页面禁止直接 import mocks，必须经本文件获取数据。
 */
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
  riskStudents
} from '@/mocks/internship/internship.mock'

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

export const internshipApi = {
  /** 品牌 / 角色 / 数据范围 / 权限动作 / 字典（页面初始化统一获取） */
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
    return ok(JSON.parse(JSON.stringify(dashboardSummary)))
  },

  /** 实习学生列表（筛选 + 分页） */
  getStudents(params = {}) {
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
    const detail = studentDetailMap[id]
    if (!detail) return fail('未找到该学生的实习档案，或不在当前数据范围内')
    return ok(JSON.parse(JSON.stringify(detail)))
  },

  /** 打卡异常列表 */
  getAttendanceExceptions(params = {}) {
    let list = [...attendanceExceptions]
    if (params.type) list = list.filter((e) => e.type === params.type)
    if (params.status) list = list.filter((e) => e.status === params.status)
    if (params.keyword) list = list.filter((e) => e.studentName.includes(params.keyword.trim()))
    return ok(paginate(list, params))
  },

  getAttendanceExceptionDetail(id) {
    const detail = attendanceExceptionDetailMap[id]
    if (!detail) return fail('异常记录不存在或已被处理归档')
    return ok(JSON.parse(JSON.stringify(detail)))
  },

  /**
   * 处理打卡异常（闭环动作，处理意见必填 ≥5 字）。
   * action: REASONABLE 标记合理 | ABNORMAL 记为异常 | TO_RISK 转风险跟进
   */
  handleAttendanceException(id, { action, comment }) {
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

  /** 周报批阅列表 */
  getWeeklyReports(params = {}) {
    let list = [...weeklyReports]
    if (params.status) list = list.filter((r) => r.status === params.status)
    if (params.keyword) list = list.filter((r) => r.studentName.includes(params.keyword.trim()))
    return ok(paginate(list, params))
  },

  getWeeklyReportDetail(id) {
    const detail = weeklyReportDetailMap[id]
    if (!detail) return fail('周报不存在或不在当前数据范围内')
    return ok(JSON.parse(JSON.stringify(detail)))
  },

  /**
   * 批阅周报（闭环动作）。
   * action: APPROVE 通过（评语选填）| RETURN 退回（原因必填 ≥5 字）
   */
  reviewWeeklyReport(id, { action, comment }) {
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

  /** 风险学生列表 */
  getRiskStudents(params = {}) {
    let list = [...riskStudents]
    if (params.level) list = list.filter((r) => r.level === params.level)
    if (params.status) list = list.filter((r) => r.status === params.status)
    return ok(paginate(list, params))
  }
}

export default internshipApi
