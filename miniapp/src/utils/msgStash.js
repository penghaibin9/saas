/** 当前会话的一次性列表摘要；统一消息正文仍须经过详情接口授权。 */
import { currentSessionGeneration } from '@/services/sessionGeneration.mjs'
import { getToken } from '@/services/request'
const DETAIL_KEY = 'gx_msg_detail_v1'
const LIST_KEY = 'gx_msg_search_pool_v1'
// 内存随小程序重启销毁，不把消息正文跨登录持久化。
let detail = null
let pool = null
function scoped(value) { return { value, generation: currentSessionGeneration(), token: getToken() } }
function current(entry) { return entry && entry.generation === currentSessionGeneration() && entry.token === getToken() }
export function stashDetail(item) {
  detail = scoped(item ? { ...item, id: String(item.messageId || item.id || '') } : null)
  try { uni.removeStorageSync(DETAIL_KEY) } catch {}
}
export function popDetail(id) {
  const saved = detail
  detail = null
  try { uni.removeStorageSync(DETAIL_KEY) } catch {}
  if (!id || !current(saved)) return null
  const item = saved.value
  if (id && String(id).replace(/^msg-/, '') !== String(item?.id || '').replace(/^msg-/, '')) return null
  return item
}
export function stashSearchPool(list) {
  pool = scoped(list || [])
  try { uni.removeStorageSync(LIST_KEY) } catch {}
}
export function getSearchPool() { return current(pool) ? pool.value : [] }
