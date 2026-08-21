import { request } from '@/services/http/client'

const BASE = '/academic-affairs/exam/incidents'

function queryString(params = {}) {
  const search = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === '') continue
    search.set(key, String(value))
  }
  const text = search.toString()
  return text ? `?${text}` : ''
}

/** W2 考务异常：服务端事实唯一权威；任何 mutation 后调用方必须重新 GET workbench。 */
export const academicExamIncidentApi = {
  workbench(params = {}) {
    return request(`${BASE}/workbench${queryString(params)}`)
  },

  resolve(incidentId, { action, reason, disciplineCaseRef } = {}) {
    const id = String(incidentId || '').trim()
    if (!id) return Promise.reject(new Error('考场异常 ID 必填'))
    return request(`${BASE}/${encodeURIComponent(id)}/resolve`, {
      method: 'POST',
      body: {
        action,
        reason,
        disciplineCaseRef: disciplineCaseRef || undefined
      }
    })
  }
}
