/**
 * 毕业设计中心 · 查重记录 / 教师评阅 / 答辩评分 / 成绩评定 API。
 * 所有学校端请求必须携带当前 batchId；写操作在前端权限门和后端动作权限双重校验。
 */
import { request } from '@/services/http/client'
import { useGraduationBatchStore } from '@/stores/graduationBatch'
import { getPermissionPatterns } from '@/security/permissionGate'
import { matchPermission } from '@/config/navPlan'

function ok(data) { return Promise.resolve({ code: 0, data, message: 'ok' }) }
function fail(message, code = 1) { return Promise.resolve({ code, data: null, message }) }
function toErr(e) {
  if (e?.biz) return fail(e.message, e.code || 1)
  return fail(e?.message || '真实接口不可用', 503001)
}
async function call(fn) {
  try { return ok(await fn()) } catch (e) { return toErr(e) }
}
function requireAction(permission) {
  const patterns = getPermissionPatterns()
  if (!Array.isArray(patterns)) throw new Error('权限上下文尚未加载，请刷新页面后重试')
  if (!matchPermission(patterns, permission)) {
    const err = new Error(`当前角色没有操作权限：${permission}`)
    err.biz = true
    err.code = 'NO_PERMISSION'
    throw err
  }
}
function batchParams(extra = {}) {
  const store = useGraduationBatchStore()
  const batchId = extra.batchId || store.selectedBatchId
  if (!batchId) throw new Error('请先选择毕业设计批次')
  return { ...extra, batchId: String(batchId) }
}
async function callList(path, params = {}) {
  try {
    const d = await request(path, { params: batchParams(params) })
    return ok({ list: d.items || [], total: d.total || 0, page: d.page || 1, pageSize: d.pageSize || 20 })
  } catch (e) { return toErr(e) }
}

const PLAG = '/graduation/gd-plagiarism'
const REVIEW = '/graduation/gd-reviews'
const SCORE = '/graduation/gd-defense-scores'
const GRADE = '/graduation/gd-grades'

export const gradeListPath = GRADE

export const graduationDefenseGradeApi = {
  getPlagiarismList(params = {}) { return callList(PLAG, params) },
  submitPlagiarism(gdStudentId, gdFinalId) {
    return call(() => {
      requireAction('graduationDesign.plagiarism.start')
      return request(`${PLAG}/${gdStudentId}/submit`, {
        method: 'POST', params: batchParams(), body: { gdFinalId },
      })
    })
  },
  setPlagiarismResult(pid, rate, reportUrl) {
    return call(() => {
      requireAction('graduationDesign.plagiarism.result')
      return request(`${PLAG}/${pid}/result`, {
        method: 'POST', params: batchParams(), body: { rate, reportUrl },
      })
    })
  },
  disputePlagiarism(pid, reason) {
    return call(() => {
      requireAction('graduationDesign.plagiarism.start')
      return request(`${PLAG}/${pid}/dispute`, {
        method: 'POST', params: batchParams(), body: { reason },
      })
    })
  },
  reviewDispute(pid, action, comment) {
    return call(() => {
      requireAction('graduationDesign.plagiarism.disputeReview')
      return request(`${PLAG}/${pid}/dispute/review`, {
        method: 'POST', params: batchParams(), body: { action, comment },
      })
    })
  },

  getReviewList(params = {}) { return callList(REVIEW, params) },
  assignReview(gdStudentId, reviewerName, reviewerMentorId) {
    return call(() => {
      requireAction('graduationDesign.review.assign')
      return request(`${REVIEW}/assign`, {
        method: 'POST', params: batchParams(),
        body: {
          gdStudentId,
          reviewerName: reviewerName || undefined,
          reviewerMentorId: reviewerMentorId ? Number(reviewerMentorId) : undefined,
        },
      })
    })
  },
  submitReview(rid, score, opinion) {
    return call(() => {
      requireAction('graduationDesign.review.submit')
      return request(`${REVIEW}/${rid}/submit`, {
        method: 'POST', params: batchParams(), body: { score, opinion },
      })
    })
  },
  returnReview(rid, reason) {
    return call(() => {
      requireAction('graduationDesign.review.return')
      return request(`${REVIEW}/${rid}/return`, {
        method: 'POST', params: batchParams(), body: { reason },
      })
    })
  },

  getScoreList(params = {}) { return callList(SCORE, params) },
  enterScore(body) {
    return call(() => {
      requireAction('graduationDesign.defense.score')
      return request(`${SCORE}/entry`, {
        method: 'POST', params: batchParams(), body,
      })
    })
  },
  confirmScores(gdStudentId) {
    return call(() => {
      requireAction('graduationDesign.defense.scoreConfirm')
      return request(`${SCORE}/${gdStudentId}/confirm`, {
        method: 'POST', params: batchParams(),
      })
    })
  },
  createSecondDefense(gdStudentId, reason) {
    return call(() => {
      requireAction('graduationDesign.defense.secondRound')
      return request(`${SCORE}/${gdStudentId}/second-defense`, {
        method: 'POST', params: batchParams(), body: { reason },
      })
    })
  },

  getGrades(params = {}) { return callList(GRADE, params) },
  getGrade(gdStudentId) {
    return call(() => request(`${GRADE}/${gdStudentId}`, { params: batchParams() }))
  },
  calculateGrade(gdStudentId, body) {
    return call(() => {
      requireAction('graduationDesign.grade.calculate')
      return request(`${GRADE}/${gdStudentId}/calculate`, {
        method: 'POST', params: batchParams(), body,
      })
    })
  },
  reviewGrade(gdStudentId, body) {
    return call(() => {
      requireAction('graduationDesign.grade.review')
      return request(`${GRADE}/${gdStudentId}/review`, {
        method: 'POST', params: batchParams(), body,
      })
    })
  },
  publishGrade(gdStudentId) {
    return call(() => {
      requireAction('graduationDesign.grade.publish')
      return request(`${GRADE}/${gdStudentId}/publish`, {
        method: 'POST', params: batchParams(),
      })
    })
  },
  withdrawGrade(gdStudentId, reason) {
    return call(() => {
      requireAction('graduationDesign.grade.withdraw')
      return request(`${GRADE}/${gdStudentId}/withdraw`, {
        method: 'POST', params: batchParams(), body: { reason },
      })
    })
  },
}

export default graduationDefenseGradeApi
