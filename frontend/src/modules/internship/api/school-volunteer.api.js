import { request } from '@/services/http/client'

const ROOT = '/internship/recruitment-campaigns'
export const schoolVolunteerApi = {
  context: (batchId) => request(`${ROOT}/review-context`, { params: { batchId } }),
  list: (campaignId, params) => request(`${ROOT}/${encodeURIComponent(campaignId)}/volunteer-groups`, { params }),
  detail: (campaignId, groupId) => request(`${ROOT}/${encodeURIComponent(campaignId)}/volunteer-groups/${encodeURIComponent(groupId)}`),
  confirm: (campaignId, groupId, body) => request(`${ROOT}/${encodeURIComponent(campaignId)}/volunteer-groups/${encodeURIComponent(groupId)}/confirm`, { method: 'POST', body }),
  return: (campaignId, groupId, body) => request(`${ROOT}/${encodeURIComponent(campaignId)}/volunteer-groups/${encodeURIComponent(groupId)}/return`, { method: 'POST', body })
}
