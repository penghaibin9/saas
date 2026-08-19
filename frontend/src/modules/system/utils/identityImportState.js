export const IDENTITY_IMPORT_PROCESSING_STATUSES = new Set([
  'SCANNING',
  'WORKER_CLAIMED',
  'PARSING'
])

export const IDENTITY_IMPORT_TERMINAL_STATUSES = new Set([
  'VALIDATED',
  'VALIDATION_FAILED',
  'FAILED',
  'CANCELLED',
  'EXPIRED'
])

const STATUS_LABELS = {
  SCANNING: '文件安全扫描中',
  WORKER_CLAIMED: '服务端已领取任务',
  PARSING: '服务端正在解析并预检',
  VALIDATED: '预检完成',
  VALIDATION_FAILED: '预检未通过',
  FAILED: '处理失败',
  CANCELLED: '任务已取消',
  EXPIRED: '任务已过期'
}

export function identityImportStatus(job) {
  return String(job?.status || '').trim().toUpperCase()
}

export function identityImportStatusLabel(job) {
  const status = identityImportStatus(job)
  return STATUS_LABELS[status] || status || '等待服务端状态'
}

export function isIdentityImportProcessing(job) {
  return IDENTITY_IMPORT_PROCESSING_STATUSES.has(identityImportStatus(job))
}

export function isIdentityImportTerminal(job) {
  return IDENTITY_IMPORT_TERMINAL_STATUSES.has(identityImportStatus(job))
}

export function canConfirmIdentityImport(job) {
  return identityImportStatus(job) === 'VALIDATED'
    && Number(job?.invalidRows ?? job?.invalid ?? 0) === 0
    && Number(job?.validRows ?? job?.valid ?? 0) > 0
}

export function toIdentityPreview(job) {
  if (!job) return null
  const status = identityImportStatus(job)
  const countsReady = status === 'VALIDATED' || status === 'VALIDATION_FAILED'
  const invalid = countsReady ? Number(job.invalidRows ?? 0) : null
  const valid = countsReady ? Number(job.validRows ?? 0) : null
  const total = countsReady ? Number(job.totalRows ?? 0) : null
  return {
    ...job,
    jobId: job.id || job.jobId,
    status,
    statusLabel: identityImportStatusLabel(job),
    processing: IDENTITY_IMPORT_PROCESSING_STATUSES.has(status),
    total,
    valid,
    invalid,
    errors: countsReady && invalid > 0
      ? [{ row: 0, field: '预检结果', message: `发现 ${invalid} 行错误，完整回执已进入数据交换任务中心` }]
      : []
  }
}
