/** 统一导航封装：容错处理，避免路径写错时白屏 */
import {
  forcePasswordChangeRequired,
  FORCE_PASSWORD_CHANGE_ROUTE,
  isForcePasswordChangeRoute
} from '@/security/passwordChangeGate'

function secureTarget(url) {
  if (forcePasswordChangeRequired() && !isForcePasswordChangeRoute(url)) {
    return FORCE_PASSWORD_CHANGE_ROUTE
  }
  return url
}

export function go(url) {
  const target = secureTarget(url)
  // 本工程使用自定义底部 Tab（pages.json 无原生 tabBar），uni.switchTab 永远会失败，
  // 放在兜底链里只是多一次无效调用并吞掉真实报错；直接降级到 reLaunch
  // （2026-08-04 复审：即 V2 报告 P2-07）。
  uni.navigateTo({
    url: target,
    fail() {
      uni.reLaunch({ url: target })
    }
  })
}
export function relaunch(url) {
  uni.reLaunch({ url: secureTarget(url) })
}
export function back() {
  // 强制改密期间不能通过返回按钮回到业务页面。
  if (forcePasswordChangeRequired()) {
    uni.reLaunch({ url: FORCE_PASSWORD_CHANGE_ROUTE })
    return
  }
  uni.navigateBack({ fail() { uni.reLaunch({ url: '/pages/login/index' }) } })
}
export function toast(title, icon = 'none') {
  uni.showToast({ title, icon })
}
export default { go, relaunch, back, toast }