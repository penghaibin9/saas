export const FILE_STATUS_TEXT = Object.freeze({
  NOT_REQUIRED: '无需扫描', PENDING: '等待安全扫描', RUNNING: '正在安全扫描',
  SCANNING: '正在安全扫描', CLEAN: '安全可用', INFECTED: '检测到风险，已拒绝',
  ERROR: '安全扫描失败，请联系学校处理'
})

export function scanState(file = {}) {
  const scanStatus = String(file.scanStatus || 'NOT_REQUIRED').toUpperCase()
  const status = String(file.status || '').toUpperCase()
  return {
    ...file, scanStatus,
    statusText: FILE_STATUS_TEXT[scanStatus] || '文件状态待确认',
    readyForBusiness: file.readyForBusiness === true
      && ['AVAILABLE', 'STORED', 'CONFIRMED'].includes(status)
      && ['CLEAN', 'NOT_REQUIRED'].includes(scanStatus)
  }
}

// Existing business attachments may omit readiness; the server still checks them on submit.
export const scanFilesReady = files => files.every(file => file.readyForBusiness !== false)

export async function refreshScanFiles(files, metadata, isCurrent = () => true) {
  const updated = await Promise.all(files.map(async file => {
    const fresh = await metadata(String(file.fileId))
    if (String(fresh?.fileId) !== String(file.fileId)) throw new Error('附件读取结果不一致，请重试')
    return scanState({ ...file, ...fresh })
  }))
  return isCurrent() ? updated : null
}
