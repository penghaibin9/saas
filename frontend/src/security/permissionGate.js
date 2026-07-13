/**
 * 岗位实习路由权限门（P5.1 残留 / 07 整改 §8.5.4 路由守卫消费 meta.permissionKey）。
 *
 * ⚠️ 安全声明：这是前端**纵深防御 + UX**层，不是安全边界。真正越权拦截由后端
 *    require_permission（模块授权 + 角色 + 数据范围 + 业务关系）完成。见 §0.3 / CLAUDE.md §6.3。
 *
 * 机制：岗位实习布局初始化（internshipApi.getContext）拿到当前身份 permissionPatterns 后调用
 *   setPermissionPatterns 落到本模块；router.beforeEach 调用 canEnterRoute 消费 to.meta.permissionKey。
 *
 * 安全口径（避免误伤，宁放勿错杀）：
 *   1. 只拦截岗位实习路由（meta.moduleCode==='INTERNSHIP'）——P5.1 已逐条核验其 permissionKey 与后端码对齐；
 *      其它模块 patterns 语义未纳入本门，一律放行，交各自后端 403 / 未来各模块守卫。
 *   2. permissionPatterns 未知（未登录 / 冷加载布局尚未拉到）→ 放行（fail-open）；后端仍是最终边界。
 *      即：直链冷加载首个实习页可能"先进后由后端 403"，后续应用内导航才被本门拦截。
 */
// 相对导入（非 @ 别名）以便 node --test 直接加载本模块做真实单测；vite 同样可解析。
import { matchPermission } from '../config/navPlan.js'

let _patterns = null // null=未知（放行）；数组=已知（按 matchPermission 判定）

/** 由 getContext 落库当前身份权限码模式集（与后端 enforce_permission 同一套码）。 */
export function setPermissionPatterns(patterns) {
  _patterns = Array.isArray(patterns) ? patterns : null
}

export function getPermissionPatterns() {
  return _patterns
}

/** 登出 / 需要强制重算时清空。 */
export function clearPermissionPatterns() {
  _patterns = null
}

/**
 * 路由守卫判定：是否允许进入该路由。
 * @param {object} meta 目标路由 to.meta（含 moduleCode / permissionKey）
 * @returns {boolean} 仅当"岗位实习路由 + 已知 patterns + 明确不匹配"时才 false（拦截）。
 */
export function canEnterRoute(meta) {
  if (!meta || meta.moduleCode !== 'INTERNSHIP') return true // 非实习路由不由本门拦截
  if (!meta.permissionKey) return true                        // 无权限码要求
  if (!Array.isArray(_patterns)) return true                  // 未知 → fail-open
  return matchPermission(_patterns, meta.permissionKey)
}

export default { setPermissionPatterns, getPermissionPatterns, clearPermissionPatterns, canEnterRoute }
