/**
 * 毕业设计中心 · 查重记录 / 教师评阅 / 答辩评分 / 成绩评定 API（生产级：仅走真实后端，不回退 mock）。
 */
import { request } from '@/services/http/client'

function ok(data) { return Promise.resolve({ code: 0, data, message: 'ok' }) }
function fail(message, code = 1) { return Promise.resolve({ code, data: null, message }) }
function toErr(e) {
  if (e?.biz) return fail(e.message, e.code || 1)
  return fail(e?.message || '真实接口不可用', 503001)
}
async function call(fn) {
  try { return ok(await fn()) } catch (e) { return toErr(e) }
}
async function callList(path, params = {}) {
  try {
    const d = await request(path, { params })
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
  submitPlagiarism(gdStudentId, gdFinalId) { return call(() => request(`${PLAG}/${gdStudentId}/submit`, { method: 'POST', body: { gdFinalId } })) },
  setPlagiarismResult(pid, rate, reportUrl) { return call(() => request(`${PLAG}/${pid}/result`, { method: 'POST', body: { rate, reportUrl } })) },
  disputePlagiarism(pid, reason) { return call(() => request(`${PLAG}/${pid}/dispute`, { method: 'POST', body: { reason } })) },
  reviewDispute(pid, action, comment) { return call(() => request(`${PLAG}/${pid}/dispute/review`, { method: 'POST', body: { action, comment } })) },

  getReviewList(params = {}) { return callList(REVIEW, params) },
  assignReview(gdStudentId, reviewerName, reviewerMentorId) {
    return call(() => request(`${REVIEW}/assign`, {
      method: 'POST',
      body: {
        gdStudentId,
        reviewerName: reviewerName || undefined,
        reviewerMentorId: reviewerMentorId ? Number(reviewerMentorId) : undefined,
      },
    }))
  },
  submitReview(rid, score, opinion) { return call(() => request(`${REVIEW}/${rid}/submit`, { method: 'POST', body: { score, opinion } })) },
  returnReview(rid, reason) { return call(() => request(`${REVIEW}/${rid}/return`, { method: 'POST', body: { reason } })) },

  getScoreList(params = {}) { return callList(SCORE, params) },
  enterScore(body) { return call(() => request(`${SCORE}/entry`, { method: 'POST', body })) },
  confirmScores(gdStudentId) { return call(() => request(`${SCORE}/${gdStudentId}/confirm`, { method: 'POST' })) },
  createSecondDefense(gdStudentId, reason) { return call(() => request(`${SCORE}/${gdStudentId}/second-defense`, { method: 'POST', body: { reason } })) },

  /** 成绩台账列表（分页+keyword/status 筛选，真实后端） */
  getGrades(params = {}) { return callList(GRADE, params) },
  getGrade(gdStudentId) { return call(() => request(`${GRADE}/${gdStudentId}`)) },
  calculateGrade(gdStudentId, body) { return call(() => request(`${GRADE}/${gdStudentId}/calculate`, { method: 'POST', body })) },
  reviewGrade(gdStudentId, body) { return call(() => request(`${GRADE}/${gdStudentId}/review`, { method: 'POST', body })) },
  publishGrade(gdStudentId) { return call(() => request(`${GRADE}/${gdStudentId}/publish`, { method: 'POST' })) },
  withdrawGrade(gdStudentId, reason) { return call(() => request(`${GRADE}/${gdStudentId}/withdraw`, { method: 'POST', body: { reason } })) }
}

export default graduationDefenseGradeApi
