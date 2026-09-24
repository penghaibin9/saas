import { request } from '@/services/http/client'

function errorResult(error, fallback) {
  return {
    code: error?.code || 1,
    bizCode: error?.bizCode || error?.biz,
    data: null,
    message: error?.message || fallback
  }
}

async function real(label, path, options = {}) {
  try {
    const data = await request(path, options)
    return { code: 0, data, message: 'ok' }
  } catch (error) {
    return errorResult(error, `${label}请求失败`)
  }
}

export const platformControlHardeningApi = {
  putRules: (tenantId, rules, expectedVersion, reason) => real(
    'rules-put-governed',
    `/platform/tenants/${tenantId}/rules`,
    { method: 'PUT', body: { rules, expectedVersion, reason } }
  ),
  putBrand: (tenantId, brand, expectedVersion, reason) => real(
    'brand-put-governed',
    `/platform/tenants/${tenantId}/brand`,
    { method: 'PUT', body: { brand, expectedVersion, reason } }
  ),
  recoverTenantAuthCache: (tenantId) => real(
    'tenant-auth-cache-recover',
    `/platform/tenants/${tenantId}/auth-cache/recover`,
    { method: 'POST', body: {} }
  )
}
