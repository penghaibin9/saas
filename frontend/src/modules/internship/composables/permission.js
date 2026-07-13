/**
 * 岗位实习前端按钮权限判定（P5.1 角色化）。
 *
 * ⚠️ 安全声明：本模块只决定按钮的“可点/禁用/提示”前端体验，不构成安全边界。
 *    真正越权拦截由后端 require_permission（模块授权 + 角色 + 数据范围 + 业务关系）完成。
 *    见 07 整改方案 §0.3 / §8.4；CLAUDE.md §6.3。
 *
 * 判定依据：布局初始化时 internshipApi.getContext() 从 /rbac/current-context 取到的
 * ctx.permissionPatterns（与后端 enforce_permission 同一套权限码模式集）。用 navPlan 的
 * matchPermission 做 `*` / `a.b.*` 前缀 / `*.view` 后缀 / 精确 四类匹配。
 *
 * 降级口径（§8.4.3“正式构建不得回退为全部允许”）：
 *   - 取不到 permissionPatterns（离线 / current-context 降级）：
 *       · 开发构建放开（本地兜底，便于联调）；
 *       · 正式构建收紧为禁用（不 all-allow；后端仍是最终边界）。
 */
import { matchPermission } from '@/config/navPlan'

function isProdBuild() {
  // 兼容 Vite（import.meta.env.PROD）与纯 node 单测（import.meta.env 可能未定义）
  const env = (typeof import.meta !== 'undefined' && import.meta.env) || {}
  return env.PROD === true
}

/**
 * 按权限码模式集判定是否允许某操作。
 * @param {string[]|null} patterns 当前身份权限码模式集（ctx.permissionPatterns）
 * @param {string} code 该操作对应的后端权限码（与 require_permission 一致）
 * @returns {boolean}
 */
export function allowByPatterns(patterns, code) {
  if (!Array.isArray(patterns)) return !isProdBuild()
  if (!code) return true
  return matchPermission(patterns, code)
}

/**
 * 视图侧便捷判定：canCode(ctx, code)。
 * @param {object} ctx getContext() 返回的上下文（含 permissionPatterns）
 * @param {string} code 后端权限码
 */
export function canCode(ctx, code) {
  return allowByPatterns(ctx && ctx.permissionPatterns, code)
}

export default { allowByPatterns, canCode }
