import { request } from '@/services/http/client'

const BASE = '/academic-affairs/terms'

function ok(data) {
  return { code: 0, data, message: 'ok' }
}

function fail(error) {
  return {
    code: error?.code || 1,
    data: error?.details || null,
    message: error?.message || '真实接口不可用'
  }
}

async function call(fn) {
  try {
    return ok(await fn())
  } catch (error) {
    return fail(error)
  }
}

export const academicAffairsTermDetailApi = {
  get(termId) {
    return call(() => request(`${BASE}/${termId}/workspace`))
  },
  preview(termId, body) {
    return call(() => request(`${BASE}/${termId}/impact-preview`, { method: 'POST', body }))
  },
  update(termId, body) {
    return call(() => request(`${BASE}/${termId}`, { method: 'PUT', body }))
  }
}
