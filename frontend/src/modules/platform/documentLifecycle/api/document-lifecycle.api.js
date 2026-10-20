import { request } from '@/services/http'

const enc = (value) => encodeURIComponent(String(value))

export const documentLifecycleApi = {
  versions(assetId, limit = 50) {
    return request(`/platform-c/document-intelligence/assets/${enc(assetId)}/versions`, {
      params: { limit }
    })
  },
  extract(fileVersionId, expectedSha256) {
    return request('/platform-c/document-intelligence/extractions', {
      method: 'POST', body: { fileVersionId, expectedSha256 }
    })
  },
  compare(left, right) {
    return request('/platform-c/document-intelligence/comparisons', {
      method: 'POST',
      body: {
        leftFileVersionId: left.fileVersionId,
        leftExpectedSha256: left.sourceSha256,
        rightFileVersionId: right.fileVersionId,
        rightExpectedSha256: right.sourceSha256
      }
    })
  },
  job(jobId) {
    return request(`/platform-c/document-intelligence/jobs/${enc(jobId)}`)
  },
  extraction(artifactId, offset = 0, limit = 100) {
    return request(`/platform-c/document-intelligence/extractions/${enc(artifactId)}`, {
      params: { offset, limit }
    })
  },
  comparison(resultId, offset = 0, limit = 100) {
    return request(`/platform-c/document-intelligence/comparisons/${enc(resultId)}`, {
      params: { offset, limit }
    })
  },
  lifecycle(studentId, params = {}) {
    return request(`/platform-c/students/${enc(studentId)}/lifecycle`, { params })
  }
}

export default documentLifecycleApi
