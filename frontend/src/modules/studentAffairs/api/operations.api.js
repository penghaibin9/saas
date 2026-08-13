import { request } from '@/services/http/client'
import { fileSdk } from '@/services/file/fileSdk'

const enc = encodeURIComponent

export const affairsOperationsApi = {
  listCenter(params = {}) {
    return request('/student-affairs/material-center', { params })
  },
  backfill(limit = 500) {
    return request('/student-affairs/material-center/backfill', { method: 'POST', body: { limit } })
  },
  getLatestManifest(studentId) {
    return request(`/student-affairs/material-center/students/${enc(studentId)}/manifest`)
  },
  getPackageManifest(packageId) {
    return request(`/student-affairs/archive/packages/${enc(packageId)}/manifest`)
  },
  listRequirements(params = {}) {
    return request('/student-affairs/material-requirements', { params })
  },
  createRequirement(body) {
    return request('/student-affairs/material-requirements', { method: 'POST', body })
  },
  /** 按 bizType+bizId 解析业务上下文，供「业务详情 → 要求补材料」预填，老师不再手抄主键。 */
  resolveBizContext(params = {}) {
    return request('/student-affairs/material-center/biz-context', { params })
  },
  /** 本校该业务域已真实用过的材料项，供登记时选择而不是猜编码。 */
  listItemSuggestions(params = {}) {
    return request('/student-affairs/material-center/item-suggestions', { params })
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
  previewMaterial(fileId) {
    return fileSdk.preview(fileId)
  },
  downloadMaterial(fileId, fileName) {
    return fileSdk.download(fileId, fileName)
  }
}

export default affairsOperationsApi
