import { request } from '@/services/http/client'

const BASE = '/academic-affairs/grade-tasks'

function ok(data) {
  return { code: 0, data, message: 'ok' }
}

function fail(error) {
  if (error?.biz) return { code: error.code || 1, data: null, message: error.message || '催录失败' }
  return { code: 503001, data: null, message: error?.message || '真实接口不可用' }
}

/** C-W4 管理端成绩催录：后端角色/dataScope 是最终权限边界。 */
export const gradeReminderApi = {
  async remind(taskId, reason) {
    try {
      const data = await request(`${BASE}/${encodeURIComponent(taskId)}/remind`, {
        method: 'POST',
        body: { reason }
      })
      return ok(data)
    } catch (error) {
      return fail(error)
    }
  }
}

export default gradeReminderApi
