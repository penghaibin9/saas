import { request, requestBlob, requestUpload } from '@/services/http/client'

function saveBlob(blob, filename) {
  const href = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = href
  anchor.download = filename || '数据交换回执.xlsx'
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
  URL.revokeObjectURL(href)
}

export const dataExchangeApi = {
  list(params = {}) {
    return request('/data-exchange/jobs', { params })
  },
  getImport(jobId) {
    return request(`/data-exchange/imports/${jobId}`)
  },
  getExport(jobId) {
    return request(`/data-exchange/exports/${jobId}`)
  },
  confirmImport(jobId, expectedVersion) {
    return request(`/data-exchange/imports/${jobId}/confirm`, {
      method: 'POST',
      body: { expectedVersion }
    })
  },
  validateIdentity(kind, file) {
    return requestUpload(`/data-exchange/imports/identity/${kind}/validate-file`, file)
  },
  async downloadExport(job) {
    const ticket = await request(`/data-exchange/exports/${job.id}/download-ticket`, {
      method: 'POST',
      body: { expectedVersion: job.version }
    })
    const blob = await requestBlob(`/data-exchange/exports/${job.id}/download`, {
      params: { ticket: ticket.ticket }
    })
    const label = job.exportType === 'INITIAL_CREDENTIAL_RECEIPT'
      ? '初始账号凭据.xlsx'
      : job.exportType === 'IMPORT_ERROR_RECEIPT'
        ? '导入错误回执.xlsx'
        : '数据交换导出.xlsx'
    saveBlob(blob, label)
    return ticket
  },
  revokeExport(jobId, expectedVersion, reason) {
    return request(`/data-exchange/exports/${jobId}/revoke`, {
      method: 'POST',
      body: { expectedVersion, reason }
    })
  }
}
