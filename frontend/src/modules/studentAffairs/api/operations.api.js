import { request, requestBlob } from '@/services/http/client'

const enc = encodeURIComponent

function saveBlob(blob, fileName) {
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = fileName || '补交材料'
  document.body.appendChild(link)
  link.click()
  link.remove()
  URL.revokeObjectURL(url)
}

export const affairsOperationsApi = {
  listRequirements(params = {}) {
    return request('/student-affairs/material-requirements', { params })
  },
  createRequirement(body) {
    return request('/student-affairs/material-requirements', { method: 'POST', body })
  },
  reviewRequirement(requirementId, action, reason, version) {
    return request(`/student-affairs/material-requirements/${enc(requirementId)}/review`, {
      method: 'POST', body: { action, reason, version }
    })
  },
  listBatchJobs(params = {}) {
    return request('/student-affairs/batch-jobs', { params })
  },
  createBatchJob(body) {
    return request('/student-affairs/batch-jobs', { method: 'POST', body })
  },
  getBatchJob(jobId) {
    return request(`/student-affairs/batch-jobs/${enc(jobId)}`)
  },
  retryFailed(jobId) {
    return request(`/student-affairs/batch-jobs/${enc(jobId)}/retry-failed`, { method: 'POST' })
  },
  async downloadMaterial(fileId, fileName) {
    const blob = await requestBlob(`/files/download/${enc(fileId)}`)
    saveBlob(blob, fileName)
  }
}

export default affairsOperationsApi
