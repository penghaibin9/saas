/** D3-U 学籍异动便利性 API。
 *  只暴露既有 future-effective 入口；立即生效继续走 academicAffairsApi.submitStatusChange。
 */
import { request } from '@/services/http/client'

const BASE = '/academic-affairs/status-changes'

function ok(data) {
  return { code: 0, data, message: 'ok' }
}

function toErr(e) {
  if (e?.biz) return { code: e.code || 1, data: null, message: e.message || '提交失败' }
  return { code: 503001, data: null, message: e?.message || '真实接口不可用' }
}

export const statusChangeConvenienceApi = {
  async submitScheduled(body) {
    try {
      return ok(await request(`${BASE}/scheduled`, { method: 'POST', body }))
    } catch (e) {
      return toErr(e)
    }
  }
}
