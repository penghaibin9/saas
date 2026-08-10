const FORCE_PASSWORD_CHANGE_KEY = 'gx_force_password_change_v1'
export const FORCE_PASSWORD_CHANGE_ROUTE = '/pages/common/change-password/index?forced=1'

export function setForcePasswordChange(required) {
  try {
    if (required) uni.setStorageSync(FORCE_PASSWORD_CHANGE_KEY, '1')
    else uni.removeStorageSync(FORCE_PASSWORD_CHANGE_KEY)
  } catch (e) { /* storage unavailable: server-side gate remains authoritative */ }
}

export function forcePasswordChangeRequired() {
  try { return String(uni.getStorageSync(FORCE_PASSWORD_CHANGE_KEY) || '') === '1' } catch (e) { return false }
}

export function isForcePasswordChangeRoute(url) {
  return String(url || '').split('?')[0] === FORCE_PASSWORD_CHANGE_ROUTE.split('?')[0]
}
