import { request } from '@/services/http/client'

export const systemP1ClosureApi = Object.freeze({
  listActiveConfigOverrides: (domain = 'SECURITY') => request('/system/effective-config-overrides', {
    params: { domain }
  }),
  restoreConfigInheritance: (configKey, overrideChain, reason) => request(
    '/system/effective-config-overrides/restore-inheritance',
    {
      method: 'POST',
      body: {
        configKey,
        reason,
        overrides: (overrideChain || []).map((item) => ({
          overrideId: item.overrideId,
          expectedVersion: item.version
        }))
      }
    }
  )
})
