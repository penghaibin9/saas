/** D3-U 学籍异动便利性 API。
 *  新便利性路径只做统一编排：内部仍调用 canonical status change + temporal guard。
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
  async submit(body) {
    try {
      return ok(await request(`${BASE}/convenience-submit`, { method: 'POST', body }))
    } catch (e) {
      return toErr(e)
    }
  },
  async listMaterials(changeId) {
    try {
      return ok(await request(`${BASE}/${encodeURIComponent(changeId)}/materials`))
    } catch (e) {
      return toErr(e)
    }
  }
}
