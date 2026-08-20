/**
 * V3 §4.2 前端唯一 Action 解析器（页面入口）。
 *
 * 纯逻辑在 actionRouter.mjs 里，本文件只负责绑定小程序导航与 toast，
 * 保证解析规则可以脱离 uni 运行时直接单测。
 */
import { go, toast } from '@/utils/nav'
import {
  canNavigate,
  createRunAction,
  disabledReasonOf,
  isObjectFocused,
  normalizeTarget
} from './actionRouterCore.mjs'

export const runAction = createRunAction({ navigate: go, toast })

export { canNavigate, disabledReasonOf, isObjectFocused, normalizeTarget }

export default { canNavigate, isObjectFocused, disabledReasonOf, normalizeTarget, runAction }
