// Presentation adapter for the current publish DTO; it never authorizes or retries a write.
const countOrUnknown = value => typeof value === 'number' && Number.isSafeInteger(value) && value >= 0 ? value : null

export function gradeWarningEffectState(data) {
  const state = data?.warningScanState
  if (['PENDING', 'RUNNING', 'RETRY', 'SUCCEEDED', 'FAILED', 'NOT_RECORDED', 'UNKNOWN'].includes(state)) return state
  return data?.warningScanOk === true ? 'SUCCEEDED' : data?.warningScanOk === false ? 'FAILED' : 'UNKNOWN'
}

export function buildGradePublishReceipt(envelope) {
  const data = envelope?.data
  // This explicit pre-commit policy rejection rolls back the publication transaction.
  // Timeouts, generic conflicts and success envelopes for another task remain unknown.
  if (envelope?.code !== 0 && envelope?.httpStatus === 409 && envelope?.bizCode === 'GPA_POLICY_INVALID') return Object.freeze({
    primary: 'REJECTED', warningRefresh: 'NOT_STARTED', tone: 'warning',
    projectedCount: 0, failedGradeCount: null, warningCount: null,
    diagnosticPresent: false, mayReplayPublish: false,
    title: '本次未发布：绩点策略无效',
    nextStep: '请核对并发布有效的绩点策略，再重新核验该成绩任务。本次没有生成正式成绩。'
  })
  if (envelope?.code !== 0 || data?.status !== 'PUBLISHED') return Object.freeze({
    primary: 'UNKNOWN', warningRefresh: 'UNKNOWN', tone: 'warning',
    projectedCount: null, failedGradeCount: null, warningCount: null,
    diagnosticPresent: false, mayReplayPublish: false,
    title: '发布结果尚未确认',
    nextStep: '先查询该任务的正式状态与操作记录，不要直接再次发布。'
  })
  const warningRefresh = gradeWarningEffectState(data)
  const projectedCount = countOrUnknown(data.projected), failedGradeCount = countOrUnknown(data.failCount)
  return Object.freeze({
    primary: 'COMMITTED', warningRefresh,
    tone: warningRefresh === 'SUCCEEDED' && projectedCount !== null && failedGradeCount !== null ? 'success' : 'warning',
    projectedCount, failedGradeCount,
    warningCount: null,
    diagnosticPresent: typeof data.warningScanError === 'string' && data.warningScanError.length > 0,
    mayReplayPublish: false,
    warningScanJobId: data.warningScanJobId || null,
    title: warningRefresh === 'SUCCEEDED' ? '成绩已发布，预警扫描已完成'
      : warningRefresh === 'FAILED' ? '成绩已发布，预警刷新失败'
        : ['PENDING', 'RUNNING', 'RETRY'].includes(warningRefresh) ? '成绩已发布，预警扫描待完成' : '成绩已发布，预警扫描状态未知',
    nextStep: warningRefresh === 'SUCCEEDED'
      ? '按权限查看正式成绩和预警结果；扫描完成不代表已通知或已处置。'
      : data.warningScanJobId ? '扫描任务已留存，可查询其恢复进度；不要重新发布正式成绩。'
        : '请有预警管理权限的教务人员核对或补扫；不要重新发布正式成绩。'
  })
}
