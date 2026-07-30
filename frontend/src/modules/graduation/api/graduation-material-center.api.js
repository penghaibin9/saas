import { request } from '@/services/http/client'
import fileSdk, { normalizeFile } from '@/services/file/fileSdk'

function ticketPath(ticket = {}) {
  const value = String(ticket.url || '')
  if (!value.startsWith('/api/v1/')) return value
  return value.slice('/api/v1'.length)
}

export const graduationMaterialCenterApi = {
  listRules(batchId) {
    return request('/graduation/material-center/rules', { params: batchId ? { batchId } : {} })
  },
  createRule(payload) {
    return request('/graduation/material-center/rules', { method: 'POST', data: payload })
  },
  activateRule(ruleId) {
    return request(`/graduation/material-center/rules/${encodeURIComponent(ruleId)}/activate`, { method: 'POST' })
  },
  overview(params = {}) {
    return request('/graduation/material-center/overview', { params })
  },
  backfill({ pageSize = 200, cursorModel = 'PROPOSAL', cursorId = 0, dryRun = false } = {}) {
    return request('/graduation/material-center/backfill', {
      method: 'POST', data: { pageSize, cursorModel, cursorId, dryRun }
    })
  },
  studentLibrary(gdStudentId, includeHistory = true) {
    return request(`/graduation/material-center/students/${encodeURIComponent(gdStudentId)}/library`, {
      params: { includeHistory }
    })
  },
  submitMaterial(materialCode, { fileId, expectedVersion } = {}) {
    return request(`/graduation/material-center/materials/${encodeURIComponent(materialCode)}/submit`, {
      method: 'POST', data: { fileId, expectedVersion }
    })
  },
  reviewMaterial(materialId, { fileVersionId, action, comment } = {}) {
    return request(`/graduation/material-center/materials/${encodeURIComponent(materialId)}/review`, {
      method: 'POST', data: { fileVersionId, action, comment }
    })
  },
  proposalVersions(proposalId) {
    return request(`/graduation/material-center/proposals/${encodeURIComponent(proposalId)}/versions`)
  },
  finalVersions(finalId) {
    return request(`/graduation/material-center/finals/${encodeURIComponent(finalId)}/versions`)
  },
  manifest(gdStudentId) {
    return request(`/graduation/material-center/archives/${encodeURIComponent(gdStudentId)}/manifest`)
  },
  freezeManifest(gdStudentId, archiveBatchNo) {
    return request(`/graduation/material-center/archives/${encodeURIComponent(gdStudentId)}/manifest`, {
      method: 'POST', data: { archiveBatchNo }
    })
  },
  revokeManifest(gdStudentId, reason) {
    return request(`/graduation/material-center/archives/${encodeURIComponent(gdStudentId)}/revoke`, {
      method: 'POST', data: { reason }
    })
  },
  buildStudentPackage(gdStudentId) {
    return request(`/graduation/material-center/archives/${encodeURIComponent(gdStudentId)}/package`, { method: 'POST' })
  },
  buildBatchPackage(batchId) {
    return request(`/graduation/material-center/batches/${encodeURIComponent(batchId)}/package`, { method: 'POST' })
  },
  createExport(payload) {
    return request('/graduation/material-center/exports', { method: 'POST', data: payload })
  },
  exportJob(jobId) {
    return request(`/graduation/material-center/exports/${encodeURIComponent(jobId)}`)
  },
  retryExport(jobId) {
    return request(`/graduation/material-center/exports/${encodeURIComponent(jobId)}/retry`, { method: 'POST' })
  },
  exportTicket(jobId, expectedVersion) {
    return request(`/graduation/material-center/exports/${encodeURIComponent(jobId)}/ticket`, {
      method: 'POST', data: { expectedVersion }
    })
  },
  revokeExport(jobId, expectedVersion, reason) {
    return request(`/graduation/material-center/exports/${encodeURIComponent(jobId)}/revoke`, {
      method: 'POST', data: { expectedVersion, reason }
    })
  },
  templateCatalog(batchId) {
    return request('/graduation/material-center/templates', { params: batchId ? { batchId } : {} })
  },
  publishTemplateAsset(templateId, fileId, payload = {}) {
    return request(`/graduation/material-center/templates/${encodeURIComponent(templateId)}/asset`, {
      method: 'POST', data: { ...payload, fileId }
    })
  },
  templateVersions(templateId) {
    return request(`/graduation/material-center/templates/${encodeURIComponent(templateId)}/versions`)
  },
  normalizeVersions(items = []) {
    return items.map((item) => normalizeFile({
      ...item,
      statusText: item.readyForBusiness ? '安全可用' : (item.scanStatus || item.status || '暂不可使用')
    }))
  },
  issueMaterialTicket(fileId, action = 'preview') {
    return request(`/graduation/material-center/files/${encodeURIComponent(fileId)}/ticket`, {
      method: 'POST', data: { action }
    })
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
    return fileSdk.downloadFrom(
      `/graduation/material-center/packages/${encodeURIComponent(fileId)}/download`,
      fileName
    )
  }
}

export default graduationMaterialCenterApi
