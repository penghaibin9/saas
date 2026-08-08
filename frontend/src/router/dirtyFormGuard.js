// Stage B / B4：统一长表单未保存保护。
// 第一批锁定实习批次、企业新增/编辑页；后续只需追加 route name，不再复制页面级 beforeRouteLeave。
const DEFAULT_GUARDED_ROUTES = new Set([
  'internship-batch-new',
  'internship-batch-edit',
  'internship-enterprise-new',
  'internship-enterprise-edit'
])

const EDITABLE_SELECTOR = 'input:not([type="hidden"]):not([type="search"]), textarea, select, [contenteditable="true"]'
const SAVE_TEXT_RE = /(保存|提交|创建|更新|确认新增|确认修改|确认保存)/

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
  let submitWindowUntil = 0

  const markDirty = (event) => {
    if (!event?.isTrusted || !isGuarded(router.currentRoute.value, guardedRoutes)) return
    const target = event.target
    if (!(target instanceof Element) || !target.matches(EDITABLE_SELECTOR)) return
    if (target.closest('[data-dirty-ignore="true"], .advanced-filter, .mp-filter, .app-search')) return
    dirty = true
  }

  const armSubmitWindow = (event) => {
    if (!event?.isTrusted || !dirty || !isGuarded(router.currentRoute.value, guardedRoutes)) return
    const button = event.target instanceof Element ? event.target.closest('button, [role="button"]') : null
    if (!button || button.hasAttribute('disabled') || button.getAttribute('aria-disabled') === 'true') return
    const text = String(button.textContent || '').replace(/\s+/g, '')
    if (SAVE_TEXT_RE.test(text)) submitWindowUntil = Date.now() + 5000
  }

  const beforeUnload = (event) => {
    if (!dirty || !isGuarded(router.currentRoute.value, guardedRoutes)) return
    event.preventDefault()
    event.returnValue = ''
  }

  document.addEventListener('input', markDirty, true)
  document.addEventListener('change', markDirty, true)
  document.addEventListener('click', armSubmitWindow, true)
  window.addEventListener('beforeunload', beforeUnload)

  const removeBefore = router.beforeEach((to, from) => {
    if (!dirty || !isGuarded(from, guardedRoutes)) return true
    if (routeName(to) === routeName(from)) return true

    // 保存/提交成功通常紧跟一次路由跳转；这里只给短窗口，不提前清 dirty。
    // 若请求失败留在原页，dirty 仍保持，后续离开仍会拦截。
    if (Date.now() <= submitWindowUntil) {
      dirty = false
      submitWindowUntil = 0
      return true
    }

    if (window.confirm(message)) {
      dirty = false
      submitWindowUntil = 0
      return true
    }
    return false
  })

  const removeAfter = router.afterEach((to, from) => {
    if (routeName(to) !== routeName(from)) {
      dirty = false
      submitWindowUntil = 0
    }
  })

  // 为后续页面在真实保存成功后显式清理提供统一接口；不要求第一批页面复制 guard 逻辑。
  window.__SAAS_DIRTY_FORM_GUARD__ = {
    markDirty: () => { if (isGuarded(router.currentRoute.value, guardedRoutes)) dirty = true },
    markSaved: () => { dirty = false; submitWindowUntil = 0 },
    isDirty: () => dirty
  }

  return () => {
    document.removeEventListener('input', markDirty, true)
    document.removeEventListener('change', markDirty, true)
    document.removeEventListener('click', armSubmitWindow, true)
    window.removeEventListener('beforeunload', beforeUnload)
    if (typeof removeBefore === 'function') removeBefore()
    if (typeof removeAfter === 'function') removeAfter()
    delete window.__SAAS_DIRTY_FORM_GUARD__
  }
}

export { DEFAULT_GUARDED_ROUTES }
