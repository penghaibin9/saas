/**
 * 岗位实习正式申请审核：只调用已上线的后端接口。
 * 学生端负责提交，PC 端负责按数据范围审核并查看留痕。
 */
import { request } from '@/services/http/client'

function ok(data) { return Promise.resolve({ code: 0, data, message: 'ok' }) }
function fail(message, code = 1) { return Promise.resolve({ code, data: null, message }) }
function toErr(error) {
  if (error?.biz) return fail(error.message, error.code || 1)
  return fail(error?.message || '真实接口不可用', 503001)
}
async function call(fn) {
  try { return ok(await fn()) } catch (error) { return toErr(error) }
}
async function callList(params = {}) {
  try {
    const data = await request('/internship/applications', { params })
    return ok({ list: data.items || [], total: data.total || 0, page: data.page || 1, pageSize: data.pageSize || 20 })
  } catch (error) {
    return toErr(error)
  }
}

export const internshipApplicationApi = {
  getApplications(params = {}) { return callList(params) },
  getDetail(id) { return call(() => request(`/internship/applications/${id}`)) },
  review(id, { action, comment = '', expectedVersion, version, recordExpectedVersion, recordVersion } = {}) {
    return call(() => request(`/internship/applications/${id}/review`, {
      method: 'POST',
      body: {
        action, comment, expectedVersion: expectedVersion ?? version,
        recordExpectedVersion: recordExpectedVersion ?? recordVersion
      }
    }))
  }
}

export default internshipApplicationApi
