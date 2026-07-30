import { request } from '@/services/http/client'

const BASE = '/internship/material-center'

export const internshipMaterialCenterApi = {
  list(params = {}) {
    return request(BASE, { params })
  },
  detail(internshipId) {
    return request(`${BASE}/${encodeURIComponent(internshipId)}`)
  },
  sync(internshipId) {
    return request(`${BASE}/${encodeURIComponent(internshipId)}/sync`, { method: 'POST' })
  },
  manifest(internshipId) {
    return request(`${BASE}/${encodeURIComponent(internshipId)}/manifest`)
  }
}

export default internshipMaterialCenterApi
