/**
 * 毕业设计中心 · 扩展事项 API：互查、专家、申诉、优秀成果、延期答辩。
 */
import { request } from '@/services/http/client'
import { useGraduationBatchStore } from '@/stores/graduationBatch'

function ok(data) { return Promise.resolve({ code: 0, data, message: 'ok' }) }
function fail(message, code = 1) { return Promise.resolve({ code, data: null, message }) }
function toErr(e) { if (e?.biz) return fail(e.message, e.code || 1); return fail(e?.message || '真实接口不可用', 503001) }
async function call(fn) { try { return ok(await fn()) } catch (e) { return toErr(e) } }
async function callList(path, params = {}) {
  try { const d = await request(path, { params }); return ok({ list: d.items || [], total: d.total || 0 }) } catch (e) { return toErr(e) }
}
function withBatch(params = {}) {
  const id = params.batchId || useGraduationBatchStore().selectedBatchId
  if (!id) throw new Error('请先选择毕业设计批次')
  return { ...params, batchId: String(id) }
}

const G = '/graduation'

export const graduationMoreApi = {
  stat(path, params = {}) { return call(() => request(path, { params })) },
  getProposalStats(params = {}) { return this.stat(`${G}/proposals/stats`, params) },
  getFinalStats(params = {}) { return this.stat(`${G}/finals/stats`, params) },
  getGuidanceStats(params = {}) { return this.stat(`${G}/gd-guidances/stats`, params) },
  getMidtermStats(params = {}) { return this.stat(`${G}/gd-midterms/stats`, params) },
  getPlagiarismStats(params = {}) { return this.stat(`${G}/gd-plagiarism/stats`, params) },
  getReviewStats(params = {}) { return this.stat(`${G}/gd-reviews/stats`, params) },
  getDefenseScoreStats(params = {}) { return this.stat(`${G}/gd-defense-scores/stats`, params) },
  getGradeStats(params = {}) { return this.stat(`${G}/gd-grades/stats`, params) },
  getPeerStats(params = {}) { return this.stat(`${G}/gd-peer-reviews/stats`, params) },

  holdProposalDefense(pid, result, comment) {
    return call(() => request(`${G}/proposals/${pid}/defense`, { method: 'POST', body: { result, comment } }))
  },
  getPeerReviews(params = {}) { return callList(`${G}/gd-peer-reviews`, params) },
  assignPeer(gdStudentId, reviewerGdStudentId) {
    return call(() => request(`${G}/gd-peer-reviews/assign`, { method: 'POST', body: { gdStudentId, reviewerGdStudentId } }))
  },
  submitPeer(pid, opinion) { return call(() => request(`${G}/gd-peer-reviews/${pid}/submit`, { method: 'POST', body: { opinion } })) },
  rectifyPeer(pid, note) { return call(() => request(`${G}/gd-peer-reviews/${pid}/rectify`, { method: 'POST', body: { note } })) },

  getExperts(params = {}) { return callList(`${G}/gd-defense-experts`, params) },
  createExpert(body) { return call(() => request(`${G}/gd-defense-experts`, { method: 'POST', body })) },
  setExpertStatus(eid, action) { return call(() => request(`${G}/gd-defense-experts/${eid}/status`, { method: 'POST', body: { action } })) },

  getAppeals(params = {}) { return callList(`${G}/gd-grade-appeals`, params) },
  reviewAppeal(aid, action, comment) { return call(() => request(`${G}/gd-grade-appeals/${aid}/review`, { method: 'POST', body: { action, comment } })) },

  getExcellentOutcomes(params = {}) { return callList(`${G}/gd-excellent-outcomes`, withBatch(params)) },
  nominateExcellent(gdStudentId, reason, evidence = []) {
    return call(() => request(`${G}/gd-excellent-outcomes/${gdStudentId}/nominate`, { method: 'POST', body: { reason, evidence } }))
  },
  reviewExcellent(id, level, action, comment = '') {
    return call(() => request(`${G}/gd-excellent-outcomes/${id}/${level}-review`, { method: 'POST', body: { action, comment } }))
  },

  getDefenseDelays(params = {}) { return callList(`${G}/gd-defense-delays`, withBatch(params)) },
  reviewDefenseDelay(id, level, action, comment = '') {
    return call(() => request(`${G}/gd-defense-delays/${id}/${level}-review`, { method: 'POST', body: { action, comment } }))
  },
  scheduleDefenseDelay(id, defenseGroupId, plannedDefenseDate) {
    return call(() => request(`${G}/gd-defense-delays/${id}/schedule`, { method: 'POST', body: { defenseGroupId, plannedDefenseDate } }))
  },
  getDefenseGroups(params = {}) {
    return callList(`${G}/defense-groups`, withBatch({ page: 1, pageSize: 200, ...params }))
  },

  notifyDefense(defenseGroupId) { return call(() => request(`${G}/gd-defense-notify`, { method: 'POST', body: { defenseGroupId } })) }
}

export default graduationMoreApi
