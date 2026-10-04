const STATUS = { PENDING_REVIEW: '待批阅', APPROVED: '已批阅', RETURNED: '已退回', OVERDUE: '已逾期' }
const RATINGS = { 1: '一星', 2: '二星', 3: '三星', 4: '四星', 5: '五星' }
const SCANS = { NOT_REQUIRED: '安全可用', CLEAN: '安全可用', PENDING: '等待安全扫描', RUNNING: '正在安全扫描', SCANNING: '正在安全扫描', INFECTED: '检测到风险，禁止使用', ERROR: '安全扫描失败，请联系学校处理' }

export const weeklyStatusLabel = value => STATUS[String(value || '').toUpperCase()] || '状态待确认'
export const weeklyRatingLabel = value => RATINGS[value] ? RATINGS[value] + '评价' : '暂无评价'
export const reviewActionLabel = value => ({ APPROVE: '批阅通过', RETURN: '退回修改' })[value] || '批阅结果待确认'
export const reportTypeLabel = value => ({ DAILY: '日报', WEEKLY: '周报', MONTHLY: '月报', SUMMARY: '总结' })[value] || '报告类型待确认'
export const reportPeriodLabel = (type, key) => {
  const text = String(key || '')
  if (type === 'SUMMARY') return '实习总结'
  if (type === 'DAILY' && /^\d{4}-\d{2}-\d{2}$/.test(text)) return text
  if (type === 'MONTHLY' && /^\d{4}-\d{2}$/.test(text)) return text
  if (type === 'WEEKLY' && /^\d{4}-W\d{2}$/.test(text)) return text.replace(/^(\d{4})-W(\d{2})$/, '$1年第$2周')
  return '周期待确认'
}
export const makeupStatusLabel = value => ({ PENDING: '待审核', APPROVED: '已通过', REJECTED: '已驳回', WITHDRAWN: '已撤回' })[value] || '状态待确认'
export function weeklyReportView(row = {}) {
  return {
    ...row, id: String(row.id || ''), week: Number(row.weekNo || row.week || 0),
    statusLabel: weeklyStatusLabel(row.status), ratingLabel: weeklyRatingLabel(row.review?.ratingLevel),
    immutableVersions: (row.immutableVersions || []).map(version => ({
      ...version, review: version.review ? { ...version.review, actionLabel: reviewActionLabel(version.review.action), ratingLabel: weeklyRatingLabel(version.review.ratingLevel) } : null
    }))
  }
}
export function processReportView(row = {}) {
  return { ...row, reportTypeLabel: reportTypeLabel(row.reportType), statusLabel: weeklyStatusLabel(row.status), periodLabel: reportPeriodLabel(row.reportType, row.periodKey) }
}
export function attachmentKind(file = {}) {
  const mime = String(file.mimeType || '').toLowerCase()
  const ext = String(file.ext || file.fileName?.split('.').pop() || '').toLowerCase()
  if (mime.startsWith('video/') || ['mp4', 'mov', 'webm'].includes(ext)) return 'video'
  if (mime.startsWith('image/') || ['jpg', 'jpeg', 'png', 'gif', 'webp'].includes(ext)) return 'image'
  return 'document'
}
export function reportFileState(file = {}) {
  const scanStatus = String(file.scanStatus || '').toUpperCase()
  const status = String(file.status || '').toUpperCase()
  const ready = file.readyForBusiness === true && ['AVAILABLE', 'STORED', 'CONFIRMED'].includes(status) && ['CLEAN', 'NOT_REQUIRED'].includes(scanStatus)
  return { ...file, fileId: String(file.fileId || ''), readyForBusiness: ready, statusText: SCANS[scanStatus] || '文件状态待确认', kindLabel: ({ image: '图片', video: '视频', document: '文档或压缩文件' })[attachmentKind(file)] }
}
export const reportFilesReady = files => files.every(file => file.readyForBusiness === true)
export async function refreshReportFiles(files, metadata, isCurrent = () => true) {
  const updated = await Promise.all(files.map(async file => {
    const fresh = await metadata(String(file.fileId))
    if (String(fresh?.fileId) !== String(file.fileId)) throw new Error('附件读取结果不一致')
    return reportFileState({ ...file, ...fresh })
  }))
  return isCurrent() ? updated : null
}
