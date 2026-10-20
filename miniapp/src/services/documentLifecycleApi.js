import { realRequest } from '@/services/request'

const enc = value => encodeURIComponent(String(value))

export const documentLifecycleApi = {
  milestones(studentId, sourceModule = '') {
    const moduleQuery = sourceModule ? `&sourceModule=${enc(sourceModule)}` : ''
    return realRequest(`/platform-c/students/${enc(studentId)}/lifecycle?pageSize=20${moduleQuery}`)
  },
  compare(left, right) {
    return realRequest('/platform-c/document-intelligence/comparisons', {
      method: 'POST', data: {
        leftFileVersionId: left.fileVersionId, leftExpectedSha256: left.sourceSha256,
        rightFileVersionId: right.fileVersionId, rightExpectedSha256: right.sourceSha256
      }
    })
  },
  job(jobId) {
    return realRequest(`/platform-c/document-intelligence/jobs/${enc(jobId)}`)
  }
}

export default documentLifecycleApi
