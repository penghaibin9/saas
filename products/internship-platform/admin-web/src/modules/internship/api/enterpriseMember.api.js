import { request } from '@/services/http/client'

const root = companyId => `/internship/enterprises/${encodeURIComponent(companyId)}/members`
export const enterpriseMemberApi = {
  members: (companyId, page = 1) => request(root(companyId), { params: { page, pageSize: 20 } }),
  bind: (companyId, memberId, body) => request(`${root(companyId)}/${memberId}/contact`, { method: 'PUT', body }),
  status: (companyId, memberId, body) => request(`${root(companyId)}/${memberId}/status`, { method: 'POST', body }),
  grants: (companyId, memberId, page = 1) => request(`${root(companyId)}/${memberId}/collaboration-grants`, { params: { page, pageSize: 20 } }),
  issue: (companyId, memberId, body) => request(`${root(companyId)}/${memberId}/collaboration-grants`, { method: 'POST', body }),
  revoke: (companyId, memberId, id, body) => request(`${root(companyId)}/${memberId}/collaboration-grants/${id}/revoke`, { method: 'POST', body })
}
