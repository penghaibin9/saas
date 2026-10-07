import { request } from '@/services/http/client'

const base = '/campus-service/work-orders'
export const workOrderApi = {
  list: params => request(base, { params }),
  detail: id => request(`${base}/${encodeURIComponent(id)}`),
  handle: (id, body) => request(`${base}/${encodeURIComponent(id)}/handle`, { method: 'POST', body })
}
