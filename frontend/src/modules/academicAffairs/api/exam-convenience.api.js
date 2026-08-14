import { request } from '@/services/http/client'

const BASE = '/academic-affairs'

function ok(data) {
  return Promise.resolve({ code: 0, data, message: 'ok' })
}

function fail(message, code = 1) {
  return Promise.resolve({ code, data: null, message })
}

function toErr(error) {
  if (error?.biz) return fail(error.message, error.code || 1)
  return fail(error?.message || '真实接口不可用', 503001)
}

async function call(fn) {
  try {
    return ok(await fn())
  } catch (error) {
    return toErr(error)
  }
}

async function callList(path, params = {}) {
  try {
    const data = await request(path, { params })
    return ok({
      list: data.items || [],
      total: data.total || 0,
      page: data.page || 1,
      pageSize: data.pageSize || 20
    })
  } catch (error) {
    return toErr(error)
  }
}

/**
 * D7-U 考务便利性 API。
 * 候选/preview/readiness 走便利层；自动定时直接复用既有 canonical auto-times，
 * 后续考场/座位/监考仍由既有 auto-arrange 完成，不新增考试事实写入口。
 */
export const academicAffairsExamConvenienceApi = {
  getReadiness(batchId) {
    return call(() => request(`${BASE}/exam/batches/${batchId}/readiness`))
  },
  listCourseCandidates(batchId, params = {}) {
    return callList(`${BASE}/exam/batches/${batchId}/course-candidates`, params)
  },
  previewCourses(batchId, teachingTaskIds) {
    return call(() => request(`${BASE}/exam/batches/${batchId}/course-candidates/preview`, {
      method: 'POST',
      body: { teachingTaskIds }
    }))
  },
  confirmCourses(batchId, previewToken) {
    return call(() => request(`${BASE}/exam/batches/${batchId}/course-candidates/confirm`, {
      method: 'POST',
      body: { previewToken }
    }))
  },
  autoTimes(batchId, body, dryRun = false) {
    return call(() => request(`${BASE}/exam/batches/${batchId}/auto-times`, {
      method: 'POST',
      params: { dryRun },
      body
    }))
  }
}
