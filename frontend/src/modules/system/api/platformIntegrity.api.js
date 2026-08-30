import { request } from '@/services/http/client'

const query = (params = {}) => {
  const values = Object.entries(params).filter(([, value]) => value !== '' && value != null)
  return values.length ? `?${values.map(([key, value]) => `${encodeURIComponent(key)}=${encodeURIComponent(value)}`).join('&')}` : ''
}

export const platformIntegrityApi = {
  list: (params) => request(`/platform-integrity/exceptions${query(params)}`),
  scan: (body) => request('/platform-integrity/scans', { method: 'POST', body }),
  transition: (id, body) => request(`/platform-integrity/exceptions/${encodeURIComponent(id)}/status`, { method: 'POST', body }),
  recheck: (id, body) => request(`/platform-integrity/exceptions/${encodeURIComponent(id)}/recheck`, { method: 'POST', body }),
  packageStatus: (manifestId) => request(`/graduation/manifests/${encodeURIComponent(manifestId)}/frozen-package`),
  buildPackage: (manifestId) => request(`/graduation/manifests/${encodeURIComponent(manifestId)}/frozen-package/build`, { method: 'POST' })
}

export default platformIntegrityApi
