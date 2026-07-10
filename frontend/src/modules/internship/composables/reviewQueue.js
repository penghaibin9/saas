/**
 * 岗位实习 · 连续处理队列（模块内部，能力不出中心）。
 *
 * 用途：老师在列表页点进一条待处理记录后，可以在详情/工作区里
 * 「上一条 / 下一条 / 处理并下一条」，全程不回列表重新找人；
 * 返回列表时恢复原筛选、页码（listQuery 原样带回）。
 *
 * 存储：sessionStorage（单标签页会话内有效，刷新详情不丢，跨天不残留）。
 * 队列内容只来自列表页当前真实加载的行，不伪造全量。
 */

const KEY = 'internshipReviewQueue'

/**
 * 列表页进入详情前调用。
 * @param {object} q
 * @param {string} q.kind 队列类型（weekly-report / process-report / attendance-exception …）
 * @param {string} q.title 老师可读的队列名（如「待批阅周报」）
 * @param {string} q.listPath 返回列表的 path
 * @param {object} q.listQuery 返回列表时恢复的 query（筛选 + panel + 页码等）
 * @param {Array<string|number>} q.ids 当前列表页可处理记录 id 顺序
 */
export function saveReviewQueue(q) {
  try {
    sessionStorage.setItem(KEY, JSON.stringify({
      kind: q.kind || '',
      title: q.title || '',
      listPath: q.listPath || '',
      listQuery: q.listQuery || {},
      ids: (q.ids || []).map(String),
      savedAt: Date.now()
    }))
  } catch { /* 隐私模式等存储失败时静默：详情页退化为无队列模式 */ }
}

/**
 * 详情页读取队列；kind 不匹配时视为无队列（防止跨业务串台）。
 * @returns {null | {kind:string,title:string,listPath:string,listQuery:object,ids:string[]}}
 */
export function readReviewQueue(kind) {
  try {
    const raw = sessionStorage.getItem(KEY)
    if (!raw) return null
    const q = JSON.parse(raw)
    if (!q || !Array.isArray(q.ids) || !q.ids.length) return null
    if (kind && q.kind !== kind) return null
    return q
  } catch {
    return null
  }
}

export function clearReviewQueue() {
  try { sessionStorage.removeItem(KEY) } catch { /* 忽略 */ }
}

/** 根据当前 id 计算队列位置（找不到时 index=-1，页面退化为无队列模式） */
export function queuePosition(queue, currentId) {
  const id = String(currentId)
  const index = queue.ids.indexOf(id)
  return {
    index,
    total: queue.ids.length,
    prevId: index > 0 ? queue.ids[index - 1] : '',
    nextId: index > -1 && index < queue.ids.length - 1 ? queue.ids[index + 1] : ''
  }
}
