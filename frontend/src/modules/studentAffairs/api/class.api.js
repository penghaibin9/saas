/**
 * 学工中心 · 班级与辅导员（班级列表/画像/学生/材料/班干部 + 辅导员考评）API —— 生产级只走真实后端。
 * 端点 /student-affairs/classes/* 与 /student-affairs/counselor-assessment/*，数据范围/审计由后端强校验。
 * 契约见 docs/03-业务模块设计/学工中心/13A-学工中心API契约草案.md §4 + §4.5。
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

const B = '/student-affairs'

export const classApi = {
  list(params = {}) { return callList(`${B}/classes`, params) },
  profile(id) { return call(() => request(`${B}/classes/${id}/profile`)) },
  students(id, params = {}) { return callList(`${B}/classes/${id}/students`, params) },
  cadres(id) { return call(() => request(`${B}/classes/${id}/cadres`)) },
  addCadre(id, body) { return call(() => request(`${B}/classes/${id}/cadres`, { method: 'POST', body })) },
  removeCadre(cadreId) { return call(() => request(`${B}/classes/cadres/${cadreId}`, { method: 'DELETE' })) },
  materials(id, params = {}) { return callList(`${B}/classes/${id}/materials`, params) },
  addMaterial(id, body) { return call(() => request(`${B}/classes/${id}/materials`, { method: 'POST', body })) },
  voidMaterial(materialId) { return call(() => request(`${B}/classes/materials/${materialId}`, { method: 'DELETE' })) }
}

export const assessmentApi = {
  createPeriod(body) { return call(() => request(`${B}/counselor-assessment/periods`, { method: 'POST', body })) },
  periods(params = {}) { return callList(`${B}/counselor-assessment/periods`, params) },
  collect(pid) { return call(() => request(`${B}/counselor-assessment/periods/${pid}/collect`, { method: 'POST' })) },
  assessments(pid) { return call(() => request(`${B}/counselor-assessment/periods/${pid}/assessments`)) },
  score(aid, body) { return call(() => request(`${B}/counselor-assessment/assessments/${aid}/score`, { method: 'POST', body })) },
  publish(pid) { return call(() => request(`${B}/counselor-assessment/periods/${pid}/publish`, { method: 'POST' })) }
}
