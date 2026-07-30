import { request, requestBlob } from '@/services/http/client'
import { normalizeFile } from '@/services/file/fileSdk'

function saveBlob(blob, fileName = '毕业设计材料') {
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = fileName || '毕业设计材料'
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
  URL.revokeObjectURL(url)
}

function openBlob(blob) {
  const url = URL.createObjectURL(blob)
  const opened = window.open(url, '_blank', 'noopener,noreferrer')
  if (!opened) URL.revokeObjectURL(url)
  else setTimeout(() => URL.revokeObjectURL(url), 60000)
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
  backfill(limit = 500) {
    return request('/graduation/material-center/backfill', { method: 'POST', data: { limit } })
  },
  studentLibrary(gdStudentId, includeHistory = true) {
    return request(`/graduation/material-center/students/${encodeURIComponent(gdStudentId)}/library`, {
      params: { includeHistory }
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
  buildStudentPackage(gdStudentId) {
    return request(`/graduation/material-center/archives/${encodeURIComponent(gdStudentId)}/package`, { method: 'POST' })
  },
  buildBatchPackage(batchId) {
    return request(`/graduation/material-center/batches/${encodeURIComponent(batchId)}/package`, { method: 'POST' })
  },
  publishTemplateAsset(templateId, fileId = null) {
    return request(`/graduation/material-center/templates/${encodeURIComponent(templateId)}/asset`, {
      method: 'POST', data: fileId ? { fileId } : {}
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
  async previewMaterial(item) {
    const blob = await requestBlob(`/graduation/material-center/files/${encodeURIComponent(item.fileId)}/download`)
    openBlob(blob)
  },
  async downloadMaterial(item) {
    const blob = await requestBlob(`/graduation/material-center/files/${encodeURIComponent(item.fileId)}/download`)
    saveBlob(blob, item.fileName)
  },
  async downloadPackage(fileId, fileName) {
    const blob = await requestBlob(`/graduation/material-center/packages/${encodeURIComponent(fileId)}/download`)
    saveBlob(blob, fileName)
  }
}

export default graduationMaterialCenterApi
