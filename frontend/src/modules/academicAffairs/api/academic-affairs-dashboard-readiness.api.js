import { request, requestBlob } from '@/services/http/client'

const q = (params = {}) => {
  const search = new URLSearchParams()
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== '') search.set(key, String(value))
  })
  const text = search.toString()
  return text ? `?${text}` : ''
}

export const academicAffairsDashboardReadinessApi = {
  get(termId) {
    return request(`/academic-affairs/dashboard/readiness${q({ termId })}`)
  },
  exportXlsx(termId, purpose) {
    return requestBlob(`/academic-affairs/dashboard/readiness/export${q({ termId, purpose })}`)
  }
}
