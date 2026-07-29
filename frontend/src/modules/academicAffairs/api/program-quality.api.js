import { request } from '@/services/http/client'

const BASE = '/academic-affairs'

function ok(data) { return { code: 0, data, message: 'ok' } }
function fail(error) {
  return {
    code: error?.code || 1,
    data: null,
    message: error?.message || '培养方案质量接口不可用'
  }
}
async function call(fn) {
  try { return ok(await fn()) } catch (error) { return fail(error) }
}

export const programQualityApi = {
  validate(programId) {
    return call(() => request(`${BASE}/programs/${programId}/validation`))
  },
  governanceSummary() {
    return call(() => request(`${BASE}/program-governance/summary`))
  },
  openingDifferences(params = {}) {
    return call(() => request(`${BASE}/opening-plan/differences`, { params }))
  }
}
