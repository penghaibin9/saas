import { request } from '@/services/http/client'
import fileSdk from '@/services/file/fileSdk'
import { buildPreviewDescriptorFromFile } from '@/components/file/viewer/viewer-contract'

const BASE = '/internship/material-center'

function ticketPath(ticket = {}) {
  const value = String(ticket.url || ticket.downloadUrl || '')
  if (!value.startsWith('/api/v1/')) return value
  return value.slice('/api/v1'.length)
}

function abortError() {
  const error = new Error('预览已切换')
  error.name = 'AbortError'
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

export const internshipMaterialCenterApi = {
  requirements(params = {}) { return request('/internship/material-requirements', { params }) },
  createRequirement(body) { return request('/internship/material-requirements', { method: 'POST', body }) },
  attachRequirementTemplate(requirementId, fileId) {
    return request(`/internship/material-requirements/${encodeURIComponent(requirementId)}/template`, {
      method: 'POST', body: { fileId }
    })
  },
  publishRequirement(requirementId) {
    return request(`/internship/material-requirements/${encodeURIComponent(requirementId)}/publish`, { method: 'POST' })
  },
  requirementCoverage(requirementId, params = {}) {
    return request(`/internship/material-requirements/${encodeURIComponent(requirementId)}/coverage`, { params })
  },
  requirementStudents(requirementId, params = {}) {
    return request(`/internship/material-requirements/${encodeURIComponent(requirementId)}/students`, { params })
  },
  reviewSubmission(submissionId, body) {
    return request(`/internship/material-submissions/${encodeURIComponent(submissionId)}/review`, {
      method: 'POST', body
    })
  },
  uploadRequirementTemplate(file, onProgress) {
    return fileSdk.upload(file, { bizType: 'INTERNSHIP_MATERIAL_TEMPLATE', bizId: '', onProgress })
  },
  downloadRequirementTemplate(requirementId, templateVersionId) {
    return fileSdk.downloadFrom(`/internship/material-requirements/${encodeURIComponent(requirementId)}/template/download?templateVersionId=${encodeURIComponent(templateVersionId)}`, '材料模板')
  },
  downloadRequirementPackage(requirementId, params = {}) {
    const query = new URLSearchParams(Object.entries(params).filter(([,value]) => value !== undefined && value !== null && value !== ''))
    return fileSdk.downloadFrom(`/internship/material-requirements/${encodeURIComponent(requirementId)}/package/download?${query}`, '材料文件包.zip')
  },
  list(params = {}) { return request(BASE, { params }) },
  detail(internshipId) { return request(`${BASE}/${encodeURIComponent(internshipId)}`) },
  sync(internshipId) {
    return request(`${BASE}/${encodeURIComponent(internshipId)}/sync`, { method: 'POST' })
  },
  manifest(internshipId) { return request(`${BASE}/${encodeURIComponent(internshipId)}/manifest`) },
  issueMaterialTicket(fileId, action = 'preview') {
    return request(`${BASE}/files/${encodeURIComponent(fileId)}/ticket`, {
      method: 'POST', body: { action }
    })
  },
  previewDescriptor(item = {}) {
    return buildPreviewDescriptorFromFile({
      ...item,
      fileVersionId: item.fileVersionId ?? item.versionId ?? null,
      sourceSha256: item.sourceSha256 || item.sha256 || '',
      materialName: item.categoryLabel || item.title || item.fileName,
      allowedActions: ['preview', ...(item.canDownload ? ['download'] : [])]
    })
  },
  createPreviewProvider() {
    return {
      async fetchBytes(descriptor, { signal } = {}) {
        if (signal?.aborted) throw abortError()
        const ticket = await raceAbort(
          internshipMaterialCenterApi.issueMaterialTicket(descriptor.fileId, 'preview'), signal
        )
        return raceAbort(fileSdk.blobFrom(ticketPath(ticket)), signal)
      },
      dispose() {}
    }
  },
  async downloadMaterial(item = {}) {
    const ticket = await this.issueMaterialTicket(item.fileId, 'download')
    return fileSdk.downloadFrom(ticketPath(ticket), item.fileName || '实习材料')
  }
}

export default internshipMaterialCenterApi
