import { request } from './request'
import fileSdk from './fileSdk'

export const graduationW75Api = {
  feedback: () => request('/portal/graduation/review-feedback'),
  proposal: () => request('/portal/graduation/proposal'),
  final: () => request('/portal/graduation/final'),
  materialLibrary: () => request('/mobile/graduation/material-center/library'),
  submitProposal: (body) => request('/portal/graduation/proposal/submit', { method: 'POST', body }),
  submitFinal: (body) => request('/portal/graduation/final/submit', { method: 'POST', body }),
  upload: (file) => fileSdk.upload(file, { bizType: 'GRADUATION_MATERIAL' }),
  issueTicket: (fileId, action) => request(`/mobile/graduation/material-center/files/${encodeURIComponent(fileId)}/ticket`, { method: 'POST', body: { action } }),
  async download(fileId, fileName) {
    const ticket = await this.issueTicket(fileId, 'download')
    return fileSdk.downloadFrom(ticket, fileName)
  }
}

export default graduationW75Api
