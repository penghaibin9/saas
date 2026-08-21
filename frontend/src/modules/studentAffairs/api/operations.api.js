import { request } from '@/services/http/client'
import { fileSdk } from '@/services/file/fileSdk'
import { buildPreviewDescriptorFromFile } from '@/components/file/viewer/viewer-contract'

const enc = encodeURIComponent
const MATERIAL_BASE = '/student-affairs/material-center'
// Stable source-level route anchors: material-center/biz-context · material-center/item-suggestions.
// Runtime paths still compose from MATERIAL_BASE so every material-center call shares one authority root.

function ticketPath(ticket = {}) {
  const value = String(ticket.url || ticket.downloadUrl || '')
  if (!value.startsWith('/api/v1/')) return value
  return value.slice('/api/v1'.length)
}

function abortError() {
  const error = new DOMException('预览已切换', 'AbortError')
  error.code = 'PREVIEW_ABORTED'
  return error
}

function raceAbort(promise, signal) {
  if (!signal) return promise
  if (signal.aborted) return Promise.reject(abortError())
  return new Promise((resolve, reject) => {
    const onAbort = () => reject(abortError())
    signal.addEventListener('abort', onAbort, { once: true })
    Promise.resolve(promise).then(resolve, reject).finally(() => signal.removeEventListener('abort', onAbort))
  })
}

export const affairsOperationsApi = {
  listCenter(params = {}) {
    return request(MATERIAL_BASE, { params })
  },
  backfill(limit = 500) {
    return request(`${MATERIAL_BASE}/backfill`, { method: 'POST', body: { limit } })
  },
  getLatestManifest(studentId) {
    return request(`${MATERIAL_BASE}/students/${enc(studentId)}/manifest`)
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
    return request(`${MATERIAL_BASE}/biz-context`, { params })
  },
  /** 本校该业务域已真实用过的材料项，供登记时选择而不是猜编码。 */
  listItemSuggestions(params = {}) {
    return request(`${MATERIAL_BASE}/item-suggestions`, { params })
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
  issueMaterialTicket(version = {}, action = 'preview') {
    if (!version?.fileId || !version?.fileVersionId) {
      const error = new Error('材料缺少不可变 FileVersion，不能预览')
      error.code = 'FILE_VERSION_REQUIRED'
      return Promise.reject(error)
    }
    return request(`${MATERIAL_BASE}/files/${enc(version.fileId)}/ticket`, {
      method: 'POST',
      body: { action, fileVersionId: version.fileVersionId }
    })
  },
  previewDescriptor(version = {}) {
    return buildPreviewDescriptorFromFile({
      ...version,
      fileVersionId: version.fileVersionId,
      sourceSha256: version.sourceSha256 || version.sha256 || '',
      materialName: version.itemName || version.fileName,
      allowedActions: ['preview', ...(version.downloadable !== false ? ['download'] : [])],
      canDownload: version.downloadable !== false
    })
  },
  createPreviewProvider() {
    return {
      async fetchBytes(descriptor, { signal } = {}) {
        if (signal?.aborted) throw abortError()
        const ticket = await raceAbort(
          affairsOperationsApi.issueMaterialTicket(descriptor, 'preview'), signal
        )
        return raceAbort(fileSdk.blobFrom(ticketPath(ticket)), signal)
      },
      dispose() {}
    }
  },
  async downloadMaterial(version = {}) {
    const ticket = await this.issueMaterialTicket(version, 'download')
    return fileSdk.downloadFrom(ticketPath(ticket), version.fileName || '学工材料')
  }
}

export default affairsOperationsApi
