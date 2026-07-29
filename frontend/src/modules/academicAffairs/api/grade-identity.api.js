import { request } from '@/services/http/client'

function ok(data) { return { code: 0, data, message: 'ok' } }
function fail(error) {
  return {
    code: error?.code || 1,
    data: error?.details || null,
    message: error?.message || '成绩身份接口不可用'
  }
}
async function call(fn) {
  try { return ok(await fn()) } catch (error) { return fail(error) }
}

export const gradeIdentityApi = {
  createGradeTask(body) {
    return call(() => request('/academic-affairs/grade-tasks/identity', {
      method: 'POST',
      body
    }))
  },
  myMakeupOptions() {
    return call(() => request('/mobile/academic/makeup/options'))
  },
  identityDebt(term = '') {
    return call(() => request('/academic-affairs/grade-identity/debt', {
      params: term ? { term } : {}
    }))
  }
}
