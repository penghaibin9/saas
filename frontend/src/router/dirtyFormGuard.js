// Stage B / B4：统一长表单未保存保护。
// 先覆盖实习批次/企业，再扩到同域岗位、指导、企业评价、协议模板等长表单；
// 后续只需追加 route name，不再复制页面级 beforeRouteLeave。
const DEFAULT_GUARDED_ROUTES = new Set([
  'internship-batch-new',
  'internship-batch-edit',
  'internship-enterprise-new',
  'internship-enterprise-edit',
  'internship-position-new',
  'internship-position-edit',
  'internship-guidance-new',
  'internship-enterprise-eval-new',
  'internship-agreement-template-new',
  'internship-agreement-template-edit'
])

const EDITABLE_SELECTOR = 'input:not([type="hidden"]):not([type="search"]), textarea, select, [contenteditable="true"]'

function routeName(route) {
  return String(route?.name || '')
}

function isGuarded(route, guardedRoutes) {
  return guardedRoutes.has(routeName(route))
}

export function installDirtyFormGuard(router, options = {}) {
  if (!router || typeof router.beforeEach !== 'function') return () => {}
  if (typeof window === 'undefined' || typeof document === 'undefined') return () => {}

  const guardedRoutes = new Set(options.routeNames || DEFAULT_GUARDED_ROUTES)
  const message = options.message || '当前表单有未保存修改。离开此页将丢失这些修改，仍要离开吗？'
  let dirty = false
  let pendingDiscardFrom = ''

  const markDirty = (event) => {
    if (!event?.isTrusted || !isGuarded(router.currentRoute.value, guardedRoutes)) return
    const target = event.target
    if (!(target instanceof Element) || !target.matches(EDITABLE_SELECTOR)) return
    if (target.closest('[data-dirty-ignore="true"], .advanced-filter, .mp-filter, .app-search')) return
    dirty = true
    pendingDiscardFrom = ''
  }

  const beforeUnload = (event) => {
    if (!dirty || !isGuarded(router.currentRoute.value, guardedRoutes)) return
    event.preventDefault()
    event.returnValue = ''
  }

  document.addEventListener('input', markDirty, true)
  document.addEventListener('change', markDirty, true)
  window.addEventListener('beforeunload', beforeUnload)

  const removeBefore = router.beforeEach((to, from) => {
    if (!dirty || !isGuarded(from, guardedRoutes)) {
      pendingDiscardFrom = ''
      return true
    }
    if (String(to?.fullPath || '') === String(from?.fullPath || '')) return true

    // fail-closed：点击“保存/提交”本身绝不清理 dirty，也不存在时间放行窗。
    // 用户确认丢弃时也只记录“本次离开已确认”，真正导航成功后才在 afterEach 清理。
    // 若后续权限/业务 guard 取消或导航失败，dirty 必须继续保留，下一次离开仍会提醒。
    if (window.confirm(message)) {
      pendingDiscardFrom = String(from?.fullPath || '')
      return true
    }
    pendingDiscardFrom = ''
    return false
  })

  const removeAfter = router.afterEach((to, from, failure) => {
    const fromPath = String(from?.fullPath || '')
    const toPath = String(to?.fullPath || '')
    if (!failure && pendingDiscardFrom && pendingDiscardFrom === fromPath && toPath !== fromPath) {
      dirty = false
    }
    pendingDiscardFrom = ''
    if (!failure && toPath !== fromPath && !isGuarded(from, guardedRoutes)) {
      dirty = false
    }
  })

  // 页面在真实保存成功回调里可显式调用 markSaved()；失败回调不要调用。
  window.__SAAS_DIRTY_FORM_GUARD__ = {
    markDirty: () => {
      if (isGuarded(router.currentRoute.value, guardedRoutes)) {
        dirty = true
        pendingDiscardFrom = ''
      }
    },
    markSaved: () => {
      dirty = false
      pendingDiscardFrom = ''
    },
    isDirty: () => dirty
  }

  return () => {
    document.removeEventListener('input', markDirty, true)
    document.removeEventListener('change', markDirty, true)
    window.removeEventListener('beforeunload', beforeUnload)
    if (typeof removeBefore === 'function') removeBefore()
    if (typeof removeAfter === 'function') removeAfter()
    delete window.__SAAS_DIRTY_FORM_GUARD__
  }
}

export { DEFAULT_GUARDED_ROUTES }
