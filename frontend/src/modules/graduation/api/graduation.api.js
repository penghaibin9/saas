/**
 * 毕业设计中心 API（P7：真实优先 + mock 兜底）。
 * 契约：所有方法返回 Promise<{ code, data, message }>，code=0 成功；方法签名冻结不变。
 * 真实接口 /api/v1/graduation/*；后端不可达时自动回退 mock，页面不白屏；业务错误透出。
 */
import { request, shouldTryReal } from '@/services/http/client'
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

function ok(data) {
  return Promise.resolve({ code: 0, data, message: 'ok' })
}

function fail(message) {
  return Promise.resolve({ code: 1, data: null, message })
}

function paginate(list, { page = 1, pageSize = 10 } = {}) {
  const total = list.length
  const start = (page - 1) * pageSize
  return { list: list.slice(start, start + pageSize), total, page, pageSize }
}

async function real(realFn, mockFn) {
  if (!shouldTryReal()) return mockFn()
  try {
    return { code: 0, data: await realFn(), message: 'ok' }
  } catch (e) {
    if (e.biz) return { code: e.code || 1, data: null, message: e.message }
    return mockFn()
  }
}

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
    return real(() => request('/graduation/dashboard'),
      () => ok(JSON.parse(JSON.stringify(dashboardSummary))))
  },

  getStudents(params = {}) {
    return realList('/graduation/students', params, () => this._mockStudents(params))
  },
  _mockStudents(params = {}) {
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
    return real(() => request(`/graduation/students/${id}`), () => {
      const detail = studentDetailMap[id]
      if (!detail) return fail('未找到该学生的毕设档案，或不在当前数据范围内')
      return ok(JSON.parse(JSON.stringify(detail)))
    })
  },

  getTopics(params = {}) {
    return realList('/graduation/topics', params, () => {
      let list = [...topicList]
      if (params.keyword) list = list.filter((t) => t.title.includes(params.keyword.trim()))
      if (params.status) list = list.filter((t) => t.status === params.status)
      return ok(paginate(list, params))
    })
  },

  getProposals(params = {}) {
    return realList('/graduation/proposals', params, () => {
      let list = [...proposalList]
      if (params.status) list = list.filter((p) => p.status === params.status)
      if (params.keyword) list = list.filter((p) => p.studentName.includes(params.keyword.trim()))
      return ok(paginate(list, params))
    })
  },

  getProposalReviewDetail(id) {
    return real(() => request(`/graduation/proposals/${id}`), () => {
      const detail = proposalReviewDetailMap[id]
      if (!detail) return fail('开题材料不存在或不在当前数据范围内')
      return ok(JSON.parse(JSON.stringify(detail)))
    })
  },

  reviewProposal(id, { action, comment }) {
    return real(
      () => request(`/graduation/proposals/${id}/review`, { method: 'POST', body: { action, comment } }),
      () => this._mockReviewProposal(id, { action, comment })
    )
  },
  _mockReviewProposal(id, { action, comment }) {
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

  getFinalSubmissions(params = {}) {
    return realList('/graduation/finals', params, () => {
      let list = [...finalSubmissionList]
      if (params.status) list = list.filter((f) => f.status === params.status)
      if (params.keyword) list = list.filter((f) => f.studentName.includes(params.keyword.trim()))
      return ok(paginate(list, params))
    })
  },

  getDefenseSchedules(params = {}) {
    return realList('/graduation/defense-groups', params,
      () => ok(paginate([...defenseScheduleList], params)))
  },

  publishDefenseSchedule(id) {
    return real(
      () => request(`/graduation/defense-groups/${id}/publish`, { method: 'POST', body: {} }),
      () => this._mockPublish(id)
    )
  },
  _mockPublish(id) {
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
