/**
 * 毕业设计中心 API（mock 实现）。
 * 契约：所有方法返回 Promise<{ code, data, message }>，code=0 成功；
 * 真实后端阶段仅替换实现，方法签名冻结不变。页面禁止直接 import mocks。
 */
import {
  tenantBrandConfig,
  currentRole,
  dataScope,
  permissionActions,
  statusOptions,
  dashboardSummary,
  graduationStudents,
  studentDetailMap,
  topicList,
  proposalList,
  proposalReviewDetailMap,
  finalSubmissionList,
  defenseScheduleList
} from '@/mocks/graduation/graduation.mock'

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

export const graduationApi = {
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

  /** 毕设学生列表（筛选 + 分页） */
  getStudents(params = {}) {
    let list = [...graduationStudents]
    if (params.keyword) {
      const kw = params.keyword.trim()
      list = list.filter((s) => s.name.includes(kw) || s.studentNo.includes(kw) || s.topicTitle.includes(kw))
    }
    if (params.classId) list = list.filter((s) => s.classId === params.classId)
    if (params.advisorId) list = list.filter((s) => s.advisorId === params.advisorId)
    if (params.stage) list = list.filter((s) => s.stage === params.stage)
    if (params.riskLevel) list = list.filter((s) => s.riskLevel === params.riskLevel)
    return ok(paginate(list, params))
  },

  getStudentDetail(id) {
    const detail = studentDetailMap[id]
    if (!detail) return fail('未找到该学生的毕设档案，或不在当前数据范围内')
    return ok(JSON.parse(JSON.stringify(detail)))
  },

  /** 选题列表 */
  getTopics(params = {}) {
    let list = [...topicList]
    if (params.keyword) list = list.filter((t) => t.title.includes(params.keyword.trim()))
    if (params.status) list = list.filter((t) => t.status === params.status)
    return ok(paginate(list, params))
  },

  /** 开题材料列表 */
  getProposals(params = {}) {
    let list = [...proposalList]
    if (params.status) list = list.filter((p) => p.status === params.status)
    if (params.keyword) list = list.filter((p) => p.studentName.includes(params.keyword.trim()))
    return ok(paginate(list, params))
  },

  getProposalReviewDetail(id) {
    const detail = proposalReviewDetailMap[id]
    if (!detail) return fail('开题材料不存在或不在当前数据范围内')
    return ok(JSON.parse(JSON.stringify(detail)))
  },

  /**
   * 开题批阅（闭环动作，指导教师权限）。
   * action: APPROVE 通过 | REJECT 驳回（原因必填 ≥5 字）
   */
  reviewProposal(id, { action, comment }) {
    if (action === 'REJECT' && (!comment || comment.trim().length < 5)) {
      return fail('驳回原因必填且不少于 5 个字')
    }
    const row = proposalList.find((p) => p.id === id)
    const detail = proposalReviewDetailMap[id]
    if (!row || !detail) return fail('开题材料不存在')
    const next = action === 'APPROVE' ? { status: 'APPROVED', label: '已通过' } : { status: 'REJECTED', label: '已驳回' }
    row.status = next.status
    row.statusLabel = next.label
    detail.status = next.status
    detail.trail.push({
      who: currentRole.userName,
      time: '刚刚',
      action: (action === 'APPROVE' ? '通过 ' : '驳回 ') + detail.version,
      affected: (comment ? (action === 'APPROVE' ? '批注：' : '驳回原因：') + comment.trim() + '；' : '') + '结果已同步学生端（P15）'
    })
    return ok({ id, status: next.status, statusLabel: next.label })
  },

  /** 成果提交列表（含查重状态） */
  getFinalSubmissions(params = {}) {
    let list = [...finalSubmissionList]
    if (params.status) list = list.filter((f) => f.status === params.status)
    if (params.keyword) list = list.filter((f) => f.studentName.includes(params.keyword.trim()))
    return ok(paginate(list, params))
  },

  /** 答辩安排列表 */
  getDefenseSchedules(params = {}) {
    return ok(paginate([...defenseScheduleList], params))
  },

  /** 发布答辩安排（闭环动作：发布后学生端 P17 可见） */
  publishDefenseSchedule(id) {
    const row = defenseScheduleList.find((d) => d.id === id)
    if (!row) return fail('答辩组不存在')
    if (row.conflict) return fail('存在评委与导师冲突，调整评委后方可发布')
    if (row.chair === '待指定' || row.location === '待定') return fail('评委或地点未安排完整，暂不能发布')
    row.published = true
    row.publishedLabel = '已发布（学生端 P17 可见）'
    return ok({ id, published: true })
  }
}

export default graduationApi
