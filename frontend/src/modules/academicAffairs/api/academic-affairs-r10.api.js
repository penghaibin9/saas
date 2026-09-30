import { request } from '@/services/http/client'

const BASE = '/academic-affairs'

function ok(data) { return { code: 0, data, message: 'ok' } }
function fail(error) {
  return {
    code: error?.code || 1,
    bizCode: error?.bizCode,
    httpStatus: error?.httpStatus ?? error?.status,
    data: null,
    message: error?.message || '真实接口不可用'
  }
}
async function call(fn) {
  try { return ok(await fn()) } catch (error) { return fail(error) }
}

export const academicAffairsR10Api = {
  getGradeScheme(taskId) {
    return call(() => request(`${BASE}/grade-tasks/${taskId}/scheme`))
  },
  updateGradeScheme(taskId, components) {
    return call(() => request(`${BASE}/grade-tasks/${taskId}/scheme`, {
      method: 'PUT', body: { components }
    }))
  },
  getDynamicGradeRoster(taskId, params = {}) {
    return call(() => request(`${BASE}/grade-tasks/${taskId}/component-roster`, { params }))
  },
  saveDynamicGradeBatch(taskId, body, commandKey) {
    return call(() => request(`${BASE}/grade-tasks/${taskId}/component-batch-save`, { method: 'POST', body: { ...body, commandKey } }))
  },
  submitDynamicGrade(taskId, expected, commandKey) {
    return call(() => request(`${BASE}/grade-tasks/${taskId}/component-submit`, { method: 'POST', body: { ...expected, commandKey } }))
  },
  getDynamicGradeReceipt(taskId, operation, commandKey) {
    return call(() => request(`${BASE}/grade-tasks/${taskId}/component-command-receipts/${encodeURIComponent(commandKey)}`, { params: { operation } }))
  },
  getDynamicGradeQuality(taskId) {
    return call(() => request(`${BASE}/grade-tasks/${taskId}/component-quality`))
  },
  saveDynamicGrade(taskId, body) {
    return call(() => request(`${BASE}/grade-tasks/${taskId}/component-scores`, {
      method: 'POST', body
    }))
  },
  createStatsSnapshot(body) {
    return call(() => request(`${BASE}/stats/snapshots`, { method: 'POST', body }))
  },
  listStatsSnapshots(params = {}) {
    return call(() => request(`${BASE}/stats/snapshots`, { params }))
  },
  getStatsSnapshot(snapshotId) {
    return call(() => request(`${BASE}/stats/snapshots/${snapshotId}`))
  }
}

export default academicAffairsR10Api
