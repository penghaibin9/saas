export const FILE_STATUS_TEXT = Object.freeze({
  NOT_REQUIRED:'安全可用', CLEAN:'安全可用', PENDING:'等待安全扫描',
  RUNNING:'正在安全扫描', SCANNING:'正在安全扫描',
  INFECTED:'检测到风险，禁止使用', ERROR:'安全扫描失败，请联系学校处理'
})
export const scanStatusLabel = value => FILE_STATUS_TEXT[String(value || '').toUpperCase()] || '文件状态待确认'
export const materialStatusLabel = value => ({DRAFT:'待提交',SUBMITTED:'待审核',RETURNED:'已退回',APPROVED:'已通过',WITHDRAWN:'已撤回'})[value] || (value ? '状态待确认' : '未提交')
export function materialSubmissionView(submission) {
  return submission ? {...submission,statusLabel:materialStatusLabel(submission.status),files:(submission.files || []).map(file=>({...file,statusText:scanStatusLabel(file.scanStatus)}))} : null
}
export const materialRequirementView = item => ({...item,submission:materialSubmissionView(item.submission)})
export const allowedFormatText = values => [...new Set((values || []).map(value=>({pdf:'便携文档',doc:'文字文档',docx:'文字文档',xls:'电子表格',xlsx:'电子表格',jpg:'图片',jpeg:'图片',png:'图片',zip:'压缩文件',rar:'压缩文件',mp4:'视频'})[String(value).toLowerCase()] || '学校指定格式'))].join(' / ') || '学校未限制'
export function normalizeFileReadiness(file = {}) {
  const status = String(file.status || '').toUpperCase(), scanStatus = String(file.scanStatus || '').toUpperCase()
  const ready = file.readyForBusiness === true && ['AVAILABLE','STORED','CONFIRMED'].includes(status) && ['CLEAN','NOT_REQUIRED'].includes(scanStatus)
  return {...file,fileId:String(file.fileId || ''),scanStatus,readyForBusiness:ready,statusText:scanStatusLabel(scanStatus)}
}
export const filesReadyForBusiness = files => files.every(file => file.readyForBusiness === true)
export async function refreshFileReadiness(files, metadata, isCurrent = () => true) {
  const refreshed = await Promise.all(files.map(async file => {
    const fresh = await metadata(String(file.fileId))
    if (String(fresh?.fileId) !== String(file.fileId)) throw new Error('文件读取结果不一致，请重试')
    return {...file,...normalizeFileReadiness(fresh)}
  }))
  return isCurrent() ? refreshed : null
}
