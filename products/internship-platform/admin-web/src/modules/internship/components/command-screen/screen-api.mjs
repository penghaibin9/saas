/** Uses the existing authenticated client; no extra token, tenant query, retry loop, or fallback. */
import { request } from '@/services/http/client'
export async function getCommandScreenExtension(params) {
  try { return { code: 0, data: await request('/internship/stats/command-screen', { params }), message: 'ok' } }
  catch (error) { return { code: error?.code || 503001, data: null, message: error?.message || '大屏聚合不可用' } }
}
