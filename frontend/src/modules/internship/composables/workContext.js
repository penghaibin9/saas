/**
 * 岗位实习 · 工作上下文保持（模块内部，能力不出中心）。
 *
 * 解决的问题：老师在列表页筛了半天（页签 / 状态 / 关键词 / 页码），点进一条处理完，
 * 或者顺手 F5 一下、点浏览器返回，回来筛选条件全没了，得从头再筛一遍。
 *
 * 存储：sessionStorage，按**路由 path** 分桶，互不串台。
 * - 单标签页会话内有效：关掉标签页就干净，不会跨天残留一份过期筛选；
 * - 另加 8 小时过期，防止老师上午筛的条件下午回来还在生效；
 * - 只存筛选类的轻量标量（页签、状态、关键词、页码、选中 id），
 *   **不存业务数据、不存权限结论**——恢复出来的只是「你上次在看哪一屏」，
 *   真实数据和可见范围一律重新向服务端要。
 *
 * 深链优先：URL 上带了显式参数（?panel= / ?stage= / ?id= 之类）时不恢复，
 * 否则从待办卡片、消息通知点进来的链接会被上一次的筛选悄悄改写。
 */

const KEY = 'internshipWorkContext'

/** 过期时间：超过就当没存过（毫秒） */
const TTL_MS = 8 * 60 * 60 * 1000

/** 最多保留多少个页面的上下文，防止 sessionStorage 无限长 */
const MAX_ENTRIES = 20

/** 上下文里允许出现的规范字段名（其余字段调用方可自定，这里只作文档说明） */
export const CONTEXT_FIELDS = [
  'batchId', 'internshipId', 'studentId', 'queueKind',
  'panel', 'source', 'listPath', 'listQuery', 'page'
]

function readAll() {
  try {
    const raw = sessionStorage.getItem(KEY)
    if (!raw) return {}
    const all = JSON.parse(raw)
    return all && typeof all === 'object' ? all : {}
  } catch {
    return {}
  }
}

function writeAll(all) {
  try {
    const keys = Object.keys(all)
    if (keys.length > MAX_ENTRIES) {
      // 丢最旧的，保留最近用过的那几屏
      keys.sort((a, b) => (all[a].savedAt || 0) - (all[b].savedAt || 0))
      keys.slice(0, keys.length - MAX_ENTRIES).forEach((k) => { delete all[k] })
    }
    sessionStorage.setItem(KEY, JSON.stringify(all))
  } catch { /* 隐私模式等存储失败时静默：页面退化为「每次都是默认筛选」 */ }
}

/**
 * 保存当前页的工作上下文。
 * @param {string} path 路由 path（同一页面的不同记录共用一份筛选，故不含 query）
 * @param {object} ctx 轻量标量对象
 */
export function saveWorkContext(path, ctx) {
  if (!path || !ctx) return
  const all = readAll()
  all[path] = { ctx, savedAt: Date.now() }
  writeAll(all)
}

/**
 * 读取工作上下文；不存在或已过期返回 null。
 * @returns {object|null}
 */
export function readWorkContext(path) {
  const entry = readAll()[path]
  if (!entry || !entry.ctx) return null
  if (!entry.savedAt || Date.now() - entry.savedAt > TTL_MS) {
    clearWorkContext(path)
    return null
  }
  return entry.ctx
}

export function clearWorkContext(path) {
  const all = readAll()
  if (!(path in all)) return
  delete all[path]
  writeAll(all)
}

/** 支持 'filters.status' 这种点号路径：很多页面把筛选装在 filters/pagination 对象里 */
function getPath(obj, path) {
  return String(path).split('.').reduce((o, k) => (o == null ? undefined : o[k]), obj)
}

function setPath(obj, path, value) {
  const keys = String(path).split('.')
  const last = keys.pop()
  const target = keys.reduce((o, k) => (o == null ? undefined : o[k]), obj)
  if (target == null || !(last in target)) return false
  target[last] = value
  return true
}

/**
 * 把组件上指定的几个字段存进上下文。放在 load() 里调用即可——
 * 筛选、翻页、切页签最终都会走 load()，不必给每个控件单独挂事件。
 *
 * @param {object} vm 组件实例（this）
 * @param {string[]} fields 要保持的字段路径，支持 'filters.status' 形式
 */
export function captureWorkContext(vm, fields) {
  if (!vm || !vm.$route || !Array.isArray(fields)) return
  const ctx = {}
  fields.forEach((f) => {
    const v = getPath(vm, f)
    if (v === undefined || v === null) return
    if (typeof v === 'object') return // 只保存标量，避免把整行数据塞进去
    ctx[f] = v
  })
  saveWorkContext(vm.$route.path, ctx)
}

/**
 * 恢复上下文到组件。在 created() 里、首次 load() 之前调用。
 *
 * @param {object} vm 组件实例（this）
 * @param {string[]} fields 要恢复的 data 字段名
 * @param {object} [opts]
 * @param {string[]} [opts.skipWhenQuery] URL 上出现这些 query key 时整体不恢复（深链优先）
 * @returns {boolean} 是否真的恢复了内容
 */
export function restoreWorkContext(vm, fields, { skipWhenQuery = [] } = {}) {
  if (!vm || !vm.$route || !Array.isArray(fields)) return false
  const query = vm.$route.query || {}
  if (skipWhenQuery.some((k) => query[k] !== undefined && query[k] !== '')) return false
  const ctx = readWorkContext(vm.$route.path)
  if (!ctx) return false
  let restored = false
  fields.forEach((f) => {
    if (!(f in ctx)) return
    if (setPath(vm, f, ctx[f])) restored = true
  })
  return restored
}
