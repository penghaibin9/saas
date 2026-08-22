import { request } from '@/services/http/client'

const BASE = '/academic-affairs/stats/snapshots'

function queryString(params = {}) {
  const search = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === '') continue
    search.set(key, String(value))
  }
  const text = search.toString()
  return text ? `?${text}` : ''
}

/**
 * W3 教务统计冻结快照唯一语义客户端。
 * hash/integrity 只消费后端结果；前端绝不重算 payloadHash 作为正式依据。
 */
export const academicStatsSnapshotApi = {
  create(body = {}) {
    return request(BASE, {
      method: 'POST',
      body: {
        snapshotType: body.snapshotType || 'OVERVIEW',
        termId: body.termId || undefined,
        collegeId: body.collegeId || undefined,
        majorId: body.majorId || undefined,
        reason: body.reason
      }
    })
  },

  list(params = {}) {
    return request(`${BASE}${queryString(params)}`)
  },

  detail(snapshotId) {
    const id = String(snapshotId || '').trim()
    if (!id) return Promise.reject(new Error('统计快照 ID 必填'))
    return request(`${BASE}/${encodeURIComponent(id)}`)
  },

  verify(snapshotId) {
    const id = String(snapshotId || '').trim()
    if (!id) return Promise.reject(new Error('统计快照 ID 必填'))
    return request(`${BASE}/${encodeURIComponent(id)}/verify`, { method: 'POST' })
  }
}

export default academicStatsSnapshotApi
