/**
 * 学工中心前端按钮权限判定（照抄 @/modules/internship/composables/permission 的既有约定）。
 *
 * ⚠️ 安全声明：本模块只决定按钮的“可点/禁用/提示”前端体验，不构成安全边界。
 *    真正越权拦截由后端 require_permission（模块授权 + 角色 + 数据范围 + 业务关系）完成。见 CLAUDE.md §6.3。
 *
 * 判定依据：AdminStudentAffairsLayout 挂载时 studentAffairsApi.getContext() 从
 * /rbac/current-context 取到的 ctx.permissionPatterns（与后端 enforce_permission 同一套权限码），
 * 下发给各子路由的 ctx prop。用 navPlan 的 matchPermission 做 `*` / `a.b.*` 前缀 / `*.view` 后缀 / 精确 四类匹配。
 *
 * 降级口径：取不到 permissionPatterns（离线 / current-context 降级）时，开发构建放开、
 * 正式构建收紧为禁用，不 all-allow；后端仍是最终边界。
 */
import { matchPermission } from '@/config/navPlan'

function isProdBuild() {
  const env = (typeof import.meta !== 'undefined' && import.meta.env) || {}
  return env.PROD === true
}

export function allowByPatterns(patterns, code) {
  if (!Array.isArray(patterns)) return !isProdBuild()
  if (!code) return true
  return matchPermission(patterns, code)
}

/** 视图侧便捷判定：canCode(ctx, code)，ctx 为 studentAffairsApi.getContext() 返回体（含 permissionPatterns）。 */
export function canCode(ctx, code) {
  return allowByPatterns(ctx && ctx.permissionPatterns, code)
}

export default { allowByPatterns, canCode }
