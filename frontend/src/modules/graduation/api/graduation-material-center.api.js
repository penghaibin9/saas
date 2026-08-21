import { request } from '@/services/http/client'
import fileSdk, { normalizeFile } from '@/services/file/fileSdk'
import { buildPreviewDescriptorFromFile } from '@/components/file/viewer/viewer-contract'

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

export const graduationMaterialCenterApi = {
  listRules(batchId) {
    return request('/graduation/material-center/rules', { params: batchId ? { batchId } : {} })
  },
  createRule(payload) {
    return request('/graduation/material-center/rules', { method: 'POST', data: payload })
  },
  ruleImpact(ruleId) {
    return request(`/graduation/material-center/rules/${encodeURIComponent(ruleId)}/impact`)
  },
  activateRule(ruleId, { confirmCatalogRepair = false, expectedVersion } = {}) {
    return request(`/graduation/material-center/rules/${encodeURIComponent(ruleId)}/activate`, {
      method: 'POST', data: { confirmCatalogRepair, expectedVersion }
    })
  },
  overview(params = {}) { return request('/graduation/material-center/overview', { params }) },
  files(params = {}) { return request('/graduation/material-center/files', { params }) },
  students(params = {}) { return request('/graduation/material-center/students', { params }) },
  summary(params = {}) { return request('/graduation/material-center/summary', { params }) },
  backfill({ pageSize = 200, cursorModel = 'PROPOSAL', cursorId = 0, dryRun = false } = {}) {
    return request('/graduation/material-center/backfill', { method: 'POST', data: { pageSize, cursorModel, cursorId, dryRun } })
  },
  studentLibrary(gdStudentId, includeHistory = true) {
    return request(`/graduation/material-center/students/${encodeURIComponent(gdStudentId)}/library`, { params: { includeHistory } })
  },
  submitMaterial(materialCode, { fileId, expectedVersion } = {}) {
    return request(`/graduation/material-center/materials/${encodeURIComponent(materialCode)}/submit`, { method: 'POST', data: { fileId, expectedVersion } })
  },
  reviewMaterial(materialId, { fileVersionId, expectedVersion, action, comment } = {}) {
    return request(`/graduation/material-center/materials/${encodeURIComponent(materialId)}/review`, { method: 'POST', data: { fileVersionId, expectedVersion, action, comment } })
  },
  proposalVersions(proposalId) { return request(`/graduation/material-center/proposals/${encodeURIComponent(proposalId)}/versions`) },
  finalVersions(finalId) { return request(`/graduation/material-center/finals/${encodeURIComponent(finalId)}/versions`) },
  manifest(gdStudentId) { return request(`/graduation/material-center/archives/${encodeURIComponent(gdStudentId)}/manifest`) },
  freezeManifest(gdStudentId, archiveBatchNo) {
    return request(`/graduation/material-center/archives/${encodeURIComponent(gdStudentId)}/manifest`, { method: 'POST', data: { archiveBatchNo } })
  },
  revokeManifest(gdStudentId, reason) {
    return request(`/graduation/material-center/archives/${encodeURIComponent(gdStudentId)}/revoke`, { method: 'POST', data: { reason } })
  },
  buildStudentPackage(gdStudentId) { return request(`/graduation/material-center/archives/${encodeURIComponent(gdStudentId)}/package`, { method: 'POST' }) },
  buildBatchPackage(batchId) { return request(`/graduation/material-center/batches/${encodeURIComponent(batchId)}/package`, { method: 'POST' }) },
  createExport(payload) { return request('/graduation/material-center/exports', { method: 'POST', data: payload }) },
  exportJob(jobId) { return request(`/graduation/material-center/exports/${encodeURIComponent(jobId)}`) },
  retryExport(jobId) { return request(`/graduation/material-center/exports/${encodeURIComponent(jobId)}/retry`, { method: 'POST' }) },
  exportTicket(jobId, expectedVersion) {
    return request(`/graduation/material-center/exports/${encodeURIComponent(jobId)}/ticket`, { method: 'POST', data: { expectedVersion } })
  },
  revokeExport(jobId, expectedVersion, reason) {
    return request(`/graduation/material-center/exports/${encodeURIComponent(jobId)}/revoke`, { method: 'POST', data: { expectedVersion, reason } })
  },
  templateCatalog(batchId) { return request('/graduation/material-center/templates', { params: batchId ? { batchId } : {} }) },
  publishTemplateAsset(templateId, fileId, payload = {}) {
    return request(`/graduation/material-center/templates/${encodeURIComponent(templateId)}/asset`, { method: 'POST', data: { ...payload, fileId } })
  },
  setTemplateStatus(policyId, enabled, expectedVersion) {
    return request(`/graduation/material-center/templates/policies/${encodeURIComponent(policyId)}/status`, { method: 'POST', data: { enabled, expectedVersion } })
  },
  templateVersions(templateId) { return request(`/graduation/material-center/templates/${encodeURIComponent(templateId)}/versions`) },
  normalizeVersions(items = []) {
    return items.map((item) => normalizeFile({ ...item, statusText: item.readyForBusiness ? '安全可用' : (item.scanStatus || item.status || '暂不可使用') }))
  },
  issueMaterialTicket(fileId, action = 'preview') {
    return request(`/graduation/material-center/files/${encodeURIComponent(fileId)}/ticket`, { method: 'POST', body: { action } })
  },
  previewDescriptor(item = {}) {
    return buildPreviewDescriptorFromFile({
      ...item,
      fileVersionId: item.fileVersionId ?? item.versionId ?? null,
      sourceSha256: item.sourceSha256 || item.sha256 || '',
      allowedActions: ['preview', ...(item.canDownload ? ['download'] : [])]
    })
  },
  createPreviewProvider() {
    return {
      async fetchBytes(descriptor, { signal } = {}) {
        if (signal?.aborted) throw abortError()
        const ticket = await raceAbort(graduationMaterialCenterApi.issueMaterialTicket(descriptor.fileId, 'preview'), signal)
        return raceAbort(fileSdk.blobFrom(ticketPath(ticket)), signal)
      },
      dispose() {}
    }
  },
  async previewMaterial(item) {
    const ticket = await this.issueMaterialTicket(item.fileId, 'preview')
    return fileSdk.previewFrom(ticketPath(ticket))
  },
  async downloadMaterial(item) {
    const ticket = await this.issueMaterialTicket(item.fileId, 'download')
    return fileSdk.downloadFrom(ticketPath(ticket), item.fileName)
  },
  async downloadExport(job) {
    const ticket = await this.exportTicket(job.id, job.version)
    return fileSdk.downloadFrom(ticketPath(ticket), job?.result?.zipFileName || '毕业设计归档包.zip')
  },
  async downloadPackage(fileId, fileName) {
    const ticket = await request(`/graduation/material-center/packages/${encodeURIComponent(fileId)}/ticket`, { method: 'POST' })
    return fileSdk.downloadFrom(ticketPath(ticket), fileName)
  }
}

export default graduationMaterialCenterApi
