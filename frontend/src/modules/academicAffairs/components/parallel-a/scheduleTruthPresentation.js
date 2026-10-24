// Display only; the current formal version is owned by the schedule scope head.
export function scheduleTruthPresentation(batch) {
  const truth = batch?.activeTruth
  if (truth?.truthStatus === 'INVALID') {
    return { label: '课表版本异常', type: 'danger', detail: '版本与批次或发布范围不一致，请联系教务处核对。' }
  }
  if (truth?.truthStatus === 'NOT_PUBLISHED' && !truth.activeBatchId) {
    return { label: '尚未发布课表', type: 'warning', detail: '发布前须通过全部校验。' }
  }
  if (truth?.truthStatus !== 'VERIFIED' || !truth.activeBatchId || typeof truth.isCurrent !== 'boolean') {
    return { label: '生效版本待核对', type: 'warning', detail: '版本信息不完整，请刷新后核对。' }
  }
  if (truth.isCurrent && String(truth.activeBatchId) === String(batch?.batchId)) {
    return { label: '当前生效课表', type: 'success', detail: '调整课程安排须走调停课审批。' }
  }
  if (!truth.isCurrent && String(truth.activeBatchId) !== String(batch?.batchId)) {
    return { label: batch?.status === 'SUPERSEDED' ? '已被替代' : '非当前生效课表', type: 'warning', detail: '另有已发布的生效课表，请确认本批次状态后办理。' }
  }
  return { label: '生效版本待核对', type: 'warning', detail: '课表与生效版本的对应关系有误，请刷新后核对。' }
}
