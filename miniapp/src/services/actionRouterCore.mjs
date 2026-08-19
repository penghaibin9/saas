/**
 * V3 §4.2 Action 解析器纯逻辑（不依赖 @/ 别名与 uni 运行时，可直接 node 单测）。
 *
 * 后端告诉前端“这个对象现在能做什么、去哪里做”；前端不按 title / todoType / group /
 * status 猜业务。页面只调用 runAction()，不再各自维护 ACTION_ROUTES / MODULE_ROUTES。
 *
 * ActionDescriptor 是只读投影，不是第二套权限系统：canNavigate() 只做端边界与形状的
 * fail-closed 兜底，真正的租户/权限/数据范围/状态/version 校验仍在后端 canonical service。
 */

export const ALLOWED_PREFIXES = {
  student: ['/pages/student/', '/pages/common/'],
  teacher: ['/pages/teacher/', '/pages/common/']
}

export const DEFAULT_DISABLED_REASON = '当前端暂无安全处理入口'

function targetOf(action) {
  return action && typeof action === 'object' ? action.target : null
}

/** 该 action 在本端是否有安全落点。无 target / 越界前缀一律 false。 */
export function canNavigate(action, side = 'student') {
  const target = targetOf(action)
  if (!target || !target.path) return false
  const path = String(target.path)
  const allowed = ALLOWED_PREFIXES[side] || ALLOWED_PREFIXES.student
  return allowed.some((prefix) => path.startsWith(prefix))
}

/** 该 action 是否真的能落到具体业务对象上（§4.4 focus 合同）。 */
export function isObjectFocused(action) {
  const target = targetOf(action)
  return !!(target && target.routeExact)
}

/** 禁用原因：后端给什么显示什么，没给才用统一兜底文案。 */
export function disabledReasonOf(action) {
  if (!action || typeof action !== 'object') return DEFAULT_DISABLED_REASON
  return action.disabledReason || DEFAULT_DISABLED_REASON
}

function encodeQuery(query) {
  if (!query || typeof query !== 'object') return ''
  const parts = []
  for (const key of Object.keys(query)) {
    const value = query[key]
    if (value === null || value === undefined || value === '') continue
    parts.push(`${encodeURIComponent(key)}=${encodeURIComponent(String(value))}`)
  }
  return parts.join('&')
}

/**
 * 把服务端已校验的 target 拼成本端可执行 URL。
 * query 必须来自服务端已校验的 actionParams；这里只负责统一 encode，不补业务参数。
 */
export function normalizeTarget(target) {
  if (!target || !target.path) return ''
  const path = String(target.path)
  const query = encodeQuery(target.query)
  if (!query) return path
  return `${path}${path.includes('?') ? '&' : '?'}${query}`
}

/**
 * 执行一个 action。返回是否真的发起了跳转。
 * fail-closed：不可跳转时只提示原因，绝不退化到通用大厅页。
 */
export function createRunAction({ navigate, toast }) {
  return function runAction(action, options = {}) {
    const side = options.side || 'student'
    const notify = options.toast || toast
    const jump = options.navigate || navigate
    if (!canNavigate(action, side)) {
      notify(disabledReasonOf(action))
      return false
    }
    const url = normalizeTarget(targetOf(action))
    if (!url) {
      notify(disabledReasonOf(action))
      return false
    }
    jump(url)
    return true
  }
}
