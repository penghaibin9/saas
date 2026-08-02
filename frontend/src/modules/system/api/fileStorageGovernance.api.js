import { request } from '@/services/http/client'

const BASE = '/files/governance'

export const fileStorageGovernanceApi = {
  overview() {
    return request(`${BASE}/overview`)
  },
  saveQuota(payload) {
    return request(`${BASE}/quota`, { method: 'PUT', body: payload })
  },
  policies() {
    return request(`${BASE}/retention-policies`)
  },
  savePolicy(payload) {
    return request(`${BASE}/retention-policies`, { method: 'POST', body: payload })
  },
  backfill(limit = 500) {
    return request(`${BASE}/retention/backfill`, { method: 'POST', params: { limit } })
  },
  cleanup({ dryRun = true, limit = 500, previewId = null, candidateHash = null } = {}) {
    return request(`${BASE}/cleanup`, { method: 'POST', body: { dryRun, limit, previewId, candidateHash } })
  },
  setLegalHold(fileId, enabled, reason, expectedVersion) {
    return request(`${BASE}/files/${encodeURIComponent(fileId)}/legal-hold`, {
      method: 'POST',
      body: { enabled, reason, expectedVersion }
    })
  }
}

export default fileStorageGovernanceApi
