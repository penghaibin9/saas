/**
 * 毕业设计中心 · 查重记录 / 教师评阅 / 答辩评分 / 成绩评定 API。
 * 所有学校端请求必须携带当前 batchId；旧标签页或缓存学生 ID 跨批时由后端 409 拒绝。
 */
import { request } from '@/services/http/client'
import { useGraduationBatchStore } from '@/modules/graduation/stores/graduationBatch'

function ok(data) { return Promise.resolve({ code: 0, data, message: 'ok' }) }
function fail(message, code = 1) { return Promise.resolve({ code, data: null, message }) }
function toErr(e) {
  if (e?.biz) return fail(e.message, e.code || 1)
  return fail(e?.message || '真实接口不可用', 503001)
}
async function call(fn) {
  try { return ok(await fn()) } catch (e) { return toErr(e) }
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
    return call(() => request(`${PLAG}/${gdStudentId}/submit`, {
      method: 'POST', params: batchParams(), body: { gdFinalId },
    }))
  },
  setPlagiarismResult(pid, rate, reportUrl) {
    return call(() => request(`${PLAG}/${pid}/result`, {
      method: 'POST', params: batchParams(), body: { rate, reportUrl },
    }))
  },
  disputePlagiarism(pid, reason) {
    return call(() => request(`${PLAG}/${pid}/dispute`, {
      method: 'POST', params: batchParams(), body: { reason },
    }))
  },
  reviewDispute(pid, action, comment) {
    return call(() => request(`${PLAG}/${pid}/dispute/review`, {
      method: 'POST', params: batchParams(), body: { action, comment },
    }))
  },

  getReviewList(params = {}) { return callList(REVIEW, params) },
  assignReview(gdStudentId, reviewerName, reviewerMentorId) {
    return call(() => request(`${REVIEW}/assign`, {
      method: 'POST', params: batchParams(),
      body: {
        gdStudentId,
        reviewerName: reviewerName || undefined,
        reviewerMentorId: reviewerMentorId ? Number(reviewerMentorId) : undefined,
      },
    }))
  },
  submitReview(rid, score, opinion) {
    return call(() => request(`${REVIEW}/${rid}/submit`, {
      method: 'POST', params: batchParams(), body: { score, opinion },
    }))
  },
  returnReview(rid, reason) {
    return call(() => request(`${REVIEW}/${rid}/return`, {
      method: 'POST', params: batchParams(), body: { reason },
    }))
  },

  getScoreList(params = {}) { return callList(SCORE, params) },
  enterScore(body) {
    return call(() => request(`${SCORE}/entry`, {
      method: 'POST', params: batchParams(), body,
    }))
  },
  confirmScores(gdStudentId) {
    return call(() => request(`${SCORE}/${gdStudentId}/confirm`, {
      method: 'POST', params: batchParams(),
    }))
  },
  createSecondDefense(gdStudentId, reason) {
    return call(() => request(`${SCORE}/${gdStudentId}/second-defense`, {
      method: 'POST', params: batchParams(), body: { reason },
    }))
  },

  getGrades(params = {}) { return callList(GRADE, params) },
  getGrade(gdStudentId) {
    return call(() => request(`${GRADE}/${gdStudentId}`, { params: batchParams() }))
  },
  calculateGrade(gdStudentId, body) {
    return call(() => request(`${GRADE}/${gdStudentId}/calculate`, {
      method: 'POST', params: batchParams(), body,
    }))
  },
  reviewGrade(gdStudentId, body) {
    return call(() => request(`${GRADE}/${gdStudentId}/review`, {
      method: 'POST', params: batchParams(), body,
    }))
  },
  publishGrade(gdStudentId) {
    return call(() => request(`${GRADE}/${gdStudentId}/publish`, {
      method: 'POST', params: batchParams(),
    }))
  },
  withdrawGrade(gdStudentId, reason) {
    return call(() => request(`${GRADE}/${gdStudentId}/withdraw`, {
      method: 'POST', params: batchParams(), body: { reason },
    }))
  },
}

export default graduationDefenseGradeApi
