import { request } from '@/services/http/client'

export const systemP1ClosureApi = Object.freeze({
  listActiveConfigOverrides: (domain = 'SECURITY') => request('/system/effective-config-overrides', {
    params: { domain }
  }),
  revokeActiveConfigOverride: (overrideId, body) => request(
    `/system/effective-config-overrides/${encodeURIComponent(overrideId)}/revoke`,
    { method: 'POST', body }
  )
})
