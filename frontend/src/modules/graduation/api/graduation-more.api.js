/**
 * 毕业设计中心 · Batch 5-9：统计中心 + 互查整改 + 答辩专家 + 成绩申诉 + 开题答辩（realStrict）。
 */
import { request } from '@/services/http/client'

function ok(data) { return Promise.resolve({ code: 0, data, message: 'ok' }) }
function fail(message, code = 1) { return Promise.resolve({ code, data: null, message }) }
function toErr(e) { if (e?.biz) return fail(e.message, e.code || 1); return fail(e?.message || '真实接口不可用', 503001) }
async function call(fn) { try { return ok(await fn()) } catch (e) { return toErr(e) } }
async function callList(path, params = {}) {
  try { const d = await request(path, { params }); return ok({ list: d.items || [], total: d.total || 0 }) } catch (e) { return toErr(e) }
}

const G = '/graduation'

export const graduationMoreApi = {
  // ── 统计中心：直接取各域 /stats ──
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

  // ── 开题答辩（现场）──
  holdProposalDefense(pid, result, comment) {
    return call(() => request(`${G}/proposals/${pid}/defense`, { method: 'POST', body: { result, comment } }))
  },

  // ── 成果互查整改 ──
  getPeerReviews(params = {}) { return callList(`${G}/gd-peer-reviews`, params) },
  assignPeer(gdStudentId, reviewerGdStudentId) {
    return call(() => request(`${G}/gd-peer-reviews/assign`, { method: 'POST', body: { gdStudentId, reviewerGdStudentId } }))
  },
  submitPeer(pid, opinion) { return call(() => request(`${G}/gd-peer-reviews/${pid}/submit`, { method: 'POST', body: { opinion } })) },
  rectifyPeer(pid, note) { return call(() => request(`${G}/gd-peer-reviews/${pid}/rectify`, { method: 'POST', body: { note } })) },

  // ── 答辩专家库 ──
  getExperts(params = {}) { return callList(`${G}/gd-defense-experts`, params) },
  createExpert(body) { return call(() => request(`${G}/gd-defense-experts`, { method: 'POST', body })) },
  setExpertStatus(eid, action) { return call(() => request(`${G}/gd-defense-experts/${eid}/status`, { method: 'POST', body: { action } })) },

  // ── 成绩更正申诉 ──
  getAppeals(params = {}) { return callList(`${G}/gd-grade-appeals`, params) },
  reviewAppeal(aid, action, comment) { return call(() => request(`${G}/gd-grade-appeals/${aid}/review`, { method: 'POST', body: { action, comment } })) },

  // ── 答辩通知 ──
  notifyDefense(defenseGroupId) { return call(() => request(`${G}/gd-defense-notify`, { method: 'POST', body: { defenseGroupId } })) }
}

export default graduationMoreApi
