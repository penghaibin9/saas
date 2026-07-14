/** 消息/通知详情与搜索的轻量客户端暂存（真实数据已在列表页拉取，避免为详情页/搜索页新建后端接口）。
 * 用 storage 而非路由传参：内容可能较长，且需要跨页保留完整对象。 */
const DETAIL_KEY = 'gx_msg_detail_v1'
const LIST_KEY = 'gx_msg_search_pool_v1'

export function stashDetail(item) {
  try { uni.setStorageSync(DETAIL_KEY, JSON.stringify(item || null)) } catch (e) {}
}

export function popDetail() {
  try {
    const raw = uni.getStorageSync(DETAIL_KEY)
    return raw ? JSON.parse(raw) : null
  } catch (e) { return null }
}

export function stashSearchPool(list) {
  try { uni.setStorageSync(LIST_KEY, JSON.stringify(list || [])) } catch (e) {}
}

export function getSearchPool() {
  try {
    const raw = uni.getStorageSync(LIST_KEY)
    return raw ? JSON.parse(raw) : []
  } catch (e) { return [] }
}
