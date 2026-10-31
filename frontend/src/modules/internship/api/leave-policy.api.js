import { request } from '@/services/http/client'

const ROOT = '/internship/leave-policies'
export const leavePolicyApi = {
  options: () => request(`${ROOT}/options`),
  read: (batchId) => request(`${ROOT}/${encodeURIComponent(batchId)}`),
  preview: (batchId, nodes) => request(`${ROOT}/${encodeURIComponent(batchId)}/preview`, {
    method: 'POST', body: { nodes }, timeoutMs: 60000
  }),
  publish: (batchId, body) => request(`${ROOT}/${encodeURIComponent(batchId)}/publish`, {
    method: 'POST', body, timeoutMs: 60000
  })
}
