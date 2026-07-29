import { request } from '@/services/http/client'

const BASE = '/academic-affairs/teaching-classes'

function ok(data) { return { code: 0, data, message: 'ok' } }
function fail(error) {
  return {
    code: error?.code || 1,
    data: error?.details || null,
    message: error?.message || '教学班接口不可用'
  }
}
async function call(fn) {
  try { return ok(await fn()) } catch (error) { return fail(error) }
}

export const teachingClassApi = {
  list(params = {}) {
    return call(() => request(BASE, { params }))
  },
  detail(teachingClassId) {
    return call(() => request(`${BASE}/${teachingClassId}`))
  },
  backfill(termId, dryRun = true, reason = '') {
    return call(() => request(`${BASE}/actions/backfill`, {
      method: 'POST',
      body: {
        termId: Number(termId),
        dryRun: Boolean(dryRun),
        reason: reason || undefined
      }
    }))
  },
  previewRosterChange(teachingClassId, studentIds) {
    return call(() => request(`${BASE}/${teachingClassId}/roster/impact`, {
      method: 'POST', body: { studentIds: (studentIds || []).map(Number) }
    }))
  },
  createRosterVersion(teachingClassId, studentIds, reason) {
    return call(() => request(`${BASE}/${teachingClassId}/roster/versions`, {
      method: 'POST',
      body: { studentIds: (studentIds || []).map(Number), reason }
    }))
  }
}
