import { request } from './request'

const enc = value => encodeURIComponent(String(value))

export const documentLifecycleApi = {
  versions: assetId => request(`/platform-c/document-intelligence/assets/${enc(assetId)}/versions`),
  compare: (left, right) => request('/platform-c/document-intelligence/comparisons', {
    method: 'POST', body: {
      leftFileVersionId: left.fileVersionId, leftExpectedSha256: left.sourceSha256,
      rightFileVersionId: right.fileVersionId, rightExpectedSha256: right.sourceSha256
    }
  }),
  job: jobId => request(`/platform-c/document-intelligence/jobs/${enc(jobId)}`),
  comparison: resultId => request(`/platform-c/document-intelligence/comparisons/${enc(resultId)}`),
  milestones: studentId => request(`/platform-c/students/${enc(studentId)}/lifecycle`, {
    params: { pageSize: 50 }
  })
}

export default documentLifecycleApi
