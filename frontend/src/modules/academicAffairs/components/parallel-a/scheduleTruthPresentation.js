// Display only; the current formal version is owned by the schedule scope head.
export function scheduleTruthPresentation(batch) {
  const truth = batch?.activeTruth
  if (truth?.truthStatus === 'INVALID') {
    return { label: '正式版本异常', type: 'danger', detail: '正式版本与批次或发布范围不一致，请由教务管理岗核对。' }
  }
  if (truth?.truthStatus === 'NOT_PUBLISHED' && !truth.activeBatchId) {
    return { label: '尚未正式发布', type: 'warning', detail: '服务端确认当前范围尚无正式课表；草稿仍需通过发布门禁。' }
  }
  if (truth?.truthStatus !== 'VERIFIED' || !truth.activeBatchId || typeof truth.isCurrent !== 'boolean') {
    return { label: '正式版本待核对', type: 'warning', detail: '尚未取得完整的正式版本信息，请重新读取后核对。' }
  }
  if (truth.isCurrent && String(truth.activeBatchId) === String(batch?.batchId)) {
    return { label: '当前正式课表', type: 'success', detail: '该批次是当前范围的正式课表，后续单课位变更须走调停课审批。' }
  }
  if (!truth.isCurrent && String(truth.activeBatchId) !== String(batch?.batchId)) {
    return { label: batch?.status === 'SUPERSEDED' ? '已被替代' : '非当前正式课表', type: 'warning', detail: `当前正式课表是批次 ${truth.activeBatchId}，请结合本批次状态办理。` }
  }
  return { label: '正式版本待核对', type: 'warning', detail: '批次与正式版本的关联信息不一致，请重新读取后核对。' }
}
