/**
 * V3 §11.3 真·网络分页器。
 *
 * 与 listPaging 的区别要说清楚：listPaging 只是「把已经加载到内存的数组分批渲染」，
 * 它解决的是单次 setData 过大，**解决不了** 1 万学生规模下把整段数据拉回客户端的问题。
 * 本模块负责先在后端分页，页面再按需要叠加渲染分批。
 *
 * 合同：
 *   - 首屏 pageSize（默认 20），后续按 cursor 续拉；
 *   - loading / !hasMore 时 loadMore() 直接返回，不会重复打同一页；
 *   - 新结果按 stable id 去重，翻页不重复不漏条；
 *   - requestEpoch：账号/角色切换或 refresh() 后，旧响应一律丢弃，避免乱序覆盖；
 *   - maxItems：单页内存默认不超过 100 条，超出丢弃最旧的，离开页面用 reset() 释放。
 *
 * fetchPage(cursor, pageSize, { epoch }) 需返回 { items, nextCursor }。
 */

/** 共享分页器契约版本。改变 fetchPage 签名或 state 形状时必须 +1。 */
export const NETWORK_PAGER_VERSION = '1.0.0'

export const DEFAULT_PAGE_SIZE = 20
export const DEFAULT_MAX_ITEMS = 100

function idOf(item, idKey) {
  if (!item || typeof item !== 'object') return ''
  const value = typeof idKey === 'function' ? idKey(item) : item[idKey]
  return value === undefined || value === null ? '' : String(value)
}

export function createNetworkPager(fetchPage, options = {}) {
  const pageSize = Math.max(1, Number(options.pageSize) || DEFAULT_PAGE_SIZE)
  const maxItems = Math.max(pageSize, Number(options.maxItems) || DEFAULT_MAX_ITEMS)
  const idKey = options.idKey || 'id'

  const state = {
    items: [],
    cursor: '',
    hasMore: false,
    loading: false,
    refreshing: false,
    requestEpoch: 0,
    error: null
  }

  function reset() {
    state.items = []
    state.cursor = ''
    state.hasMore = false
    state.loading = false
    state.refreshing = false
    state.error = null
    // 作废所有在途请求：换号/换角色后旧数据绝不能落回页面。
    state.requestEpoch += 1
    return state
  }

  function merge(incoming) {
    const seen = new Set(state.items.map((item) => idOf(item, idKey)))
    for (const item of incoming || []) {
      const id = idOf(item, idKey)
      // 没有稳定 id 的条目直接丢弃：它无法去重，留下来必然造成重复渲染。
      if (!id || seen.has(id)) continue
      seen.add(id)
      state.items.push(item)
    }
    if (state.items.length > maxItems) {
      state.items = state.items.slice(state.items.length - maxItems)
    }
  }

  async function run(cursor, { refreshing }) {
    const epoch = state.requestEpoch + 1
    state.requestEpoch = epoch
    state.loading = true
    state.refreshing = !!refreshing
    state.error = null
    try {
      const page = await fetchPage(cursor, pageSize, { epoch })
      // 过期响应：期间发生过 refresh/reset/换号，结果一律丢弃。
      if (epoch !== state.requestEpoch) return state
      if (refreshing) state.items = []
      merge(page && page.items)
      state.cursor = (page && page.nextCursor) || ''
      state.hasMore = !!state.cursor
      return state
    } catch (error) {
      if (epoch === state.requestEpoch) state.error = error
      throw error
    } finally {
      if (epoch === state.requestEpoch) {
        state.loading = false
        state.refreshing = false
      }
    }
  }

  return {
    state,
    reset,
    /** 回到首屏：清空游标重新拉第一页。 */
    refresh() { return run('', { refreshing: true }) },
    /** 续拉下一页；正在加载或已到底时是空操作。 */
    loadMore() {
      if (state.loading || !state.hasMore) return Promise.resolve(state)
      return run(state.cursor, { refreshing: false })
    }
  }
}

export default createNetworkPager
