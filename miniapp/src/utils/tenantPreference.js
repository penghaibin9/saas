const LAST_TENANT_CODE_KEY = 'gx_last_tenant_code_v1'

export function getLastTenantCode() {
  try {
    return String(uni.getStorageSync(LAST_TENANT_CODE_KEY) || '').trim()
  } catch (_) {
    return ''
  }
}

export function saveLastTenantCode(value) {
  const tenantCode = String(value || '').trim()
  try {
    if (tenantCode) uni.setStorageSync(LAST_TENANT_CODE_KEY, tenantCode)
    else uni.removeStorageSync(LAST_TENANT_CODE_KEY)
  } catch (_) {
    // 本地存储不可用时不阻断登录。
  }
}
