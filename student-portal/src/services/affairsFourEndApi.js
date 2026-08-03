import { downloadFile, request, uploadFile } from './request'

const enc = encodeURIComponent

async function loadAllTransferPages(path) {
  const pageSize = 200
  let page = 1
  let first = null
  const items = []
  while (true) {
    const data = await request(path, { params: { page, pageSize } })
    if (!first) first = data || {}
    items.push(...((data && data.items) || []))
    const total = Number((data && data.total) || items.length)
    if (!(data && data.hasMore) && items.length >= total) break
    if (!data || !data.items || data.items.length === 0) break
    page += 1
  }
  return { ...(first || {}), items, total: Number((first && first.total) || items.length), page: 1, pageSize: items.length, hasMore: false }
}

function creditAppealBody(body = {}) {
  const value = Number(body.claimValue)
  if (!Number.isFinite(value) || value <= 0) throw new Error('主张数值必填且必须大于0')
  if (Math.abs(Math.round(value * 100) - value * 100) > 1e-8) throw new Error('主张数值最多保留2位小数')
  return { ...body, claimValue: value }
}

export const affairsFourEndApi = {
  // 请假 version / 退回编辑
  getReturnedLeave: (id) => request(`/mobile/affairs/leave/${enc(id)}/editable`),
  updateReturnedLeave: (id, body) => request(`/mobile/affairs/leave/${enc(id)}/returned`, { method: 'PUT', body }),
  resubmitLeave: (id, version) => request(`/portal/affairs/leave/${enc(id)}/resubmit`, { method: 'POST', body: { version } }),
  cancelLeave: (id, version, proofNote = '') => request(`/portal/affairs/leave/${enc(id)}/cancel`, { method: 'POST', body: { version, proofNote } }),
  extendLeave: (id, version, newEndTime, reason) => request(`/portal/affairs/leave/${enc(id)}/extension`, { method: 'POST', body: { version, newEndTime, reason } }),

  // 困难/奖助退回编辑
  getReturnedAid: (id) => request(`/mobile/affairs/aid/${enc(id)}/editable`),
  updateReturnedAid: (id, body) => request(`/mobile/affairs/aid/${enc(id)}/returned`, { method: 'PUT', body }),
  resubmitAid: (id, version) => request(`/mobile/affairs/aid/${enc(id)}/resubmit`, { method: 'POST', body: { version } }),
  getReturnedFunding: (id) => request(`/mobile/affairs/funding/${enc(id)}/editable`),
  updateReturnedFunding: (id, body) => request(`/mobile/affairs/funding/${enc(id)}/returned`, { method: 'PUT', body }),
  resubmitFunding: (id, version) => request(`/mobile/affairs/funding/${enc(id)}/resubmit`, { method: 'POST', body: { version } }),

  // 材料缺项与逐版本补交
  myMaterialRequirements: (params = {}) => request('/mobile/affairs/material-requirements', { params }),
  uploadMaterialFile: (file) => uploadFile('/files', file),
  submitMaterialVersion: (requirementId, fileId, version, note = '') => request(`/mobile/affairs/material-requirements/${enc(requirementId)}/submissions`, {
    method: 'POST', body: { fileId, version, note }
  }),
  downloadMaterial: (fileId, fileName = '补交材料') => downloadFile(`/files/download/${enc(fileId)}`, fileName),

  // 宿舍正式调宿
  dormTransferOptions: () => loadAllTransferPages('/mobile/affairs/dorm/transfer-options'),
  dormTransferRooms: (buildingId) => loadAllTransferPages(`/mobile/affairs/dorm/transfer-buildings/${enc(buildingId)}/rooms`),
  dormTransferBeds: (roomId) => request(`/mobile/affairs/dorm/transfer-rooms/${enc(roomId)}/beds`),
  submitDormTransfer: (toBedId, reason) => request('/mobile/affairs/dorm/transfers', { method: 'POST', body: { toBedId, reason } }),
  myDormTransfers: () => request('/mobile/affairs/dorm/transfers/my'),

  // 正式第二课堂成绩单与申诉
  secondClassReport: () => request('/mobile/affairs/second-class/report'),
  myCreditAppeals: (page = 1, pageSize = 100) => request('/mobile/affairs/second-class/appeals/my', { params: { page, pageSize } }),
  submitCreditAppeal: (body) => request('/mobile/affairs/second-class/appeals', { method: 'POST', body: creditAppealBody(body) })
}

export default affairsFourEndApi
