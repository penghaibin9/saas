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

/**
 * uni-app 在不同入口下可能返回已解码或仍带百分号编码的 query。直接调用
 * decodeURIComponent 会让包含孤立 `%` 的外部深链在 onLoad 阶段抛异常并白屏。
 */
export function decodeQueryText(value, fallback = '') {
  const source = String(value == null ? '' : value)
  if (!source) return fallback
  try { return decodeURIComponent(source) } catch (e) { return source }
}

let pendingNavigation = null
// 一次只允许一个宿主路由转换；迟到回调不能解锁后续操作。
function navigate(method, options, fallback) {
  if (pendingNavigation && Date.now() - pendingNavigation.startedAt < 8000) return false
  const operation = { startedAt: Date.now() }
  pendingNavigation = operation
  const release = () => { if (pendingNavigation === operation) pendingNavigation = null }
  const run = (name, args, recovery) => {
    let recovering = false
    try {
      uni[name]({ ...args,
        fail() {
          if (pendingNavigation !== operation) return
          if (recovery) { recovering = true; run(recovery.method, recovery.options) }
          else toast('页面暂时无法打开，请稍后重试')
        },
        complete() { if (!recovering) release() }
      })
    } catch (error) {
      release()
      toast('页面暂时无法打开，请稍后重试')
    }
  }
  run(method, options, fallback)
  return true
}

export function go(url) {
  const target = secureTarget(url)
  // 本工程使用自定义底部 Tab（pages.json 无原生 tabBar），uni.switchTab 永远会失败，
  // 放在兜底链里只是多一次无效调用并吞掉真实报错；直接降级到 reLaunch
  // （2026-08-04 复审：即 V2 报告 P2-07）。
  navigate('navigateTo', { url: target }, { method: 'reLaunch', options: { url: target } })
}
export function relaunch(url) {
  return navigate('reLaunch', { url: secureTarget(url) })
}
/** 同级目录切换：复用栈中已有页面，否则替换当前同级页，保留上一级返回位置。 */
export function goSibling(url, directory) {
  const target = secureTarget(url)
  const pages = typeof getCurrentPages === 'function' ? getCurrentPages() : []
  const path = target.split('?')[0].replace(/^\//, '')
  const current = pages[pages.length - 1]?.route || ''
  if (current === path && !target.includes('?')) return
  let existing = -1
  pages.forEach((page, index) => { if (page.route === path) existing = index })
  if (existing >= 0 && !target.includes('?')) {
    navigate('navigateBack', { delta: pages.length - 1 - existing })
  } else if (current.startsWith(directory.replace(/^\//, '')) && !current.endsWith('/index')) {
    navigate('redirectTo', { url: target })
  } else {
    go(target)
  }
}
export function back(fallbackUrl = '/pages/login/index') {
  // 强制改密期间不能通过返回按钮回到业务页面。
  if (forcePasswordChangeRequired()) {
    relaunch(FORCE_PASSWORD_CHANGE_ROUTE)
    return
  }
  if (typeof getCurrentPages === 'function' && getCurrentPages().length <= 1) {
    relaunch(fallbackUrl)
    return
  }
  navigate('navigateBack', {}, { method: 'reLaunch', options: { url: secureTarget(fallbackUrl) } })
}
export function toast(title, icon = 'none') {
  uni.showToast({ title, icon })
}
export default { go, relaunch, back, toast, decodeQueryText }
