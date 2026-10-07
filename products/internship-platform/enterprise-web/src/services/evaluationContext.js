/** Client-side concurrency only. Backend remains the permission/state authority. */
export function requireDecimalId(value, label = '业务对象') {
  if (typeof value === 'number' && !Number.isSafeInteger(value)) {
    throw new Error(`${label}编号精度已丢失，请刷新后重试`)
  }
  const text = String(value ?? '')
  if (!/^[1-9][0-9]{0,18}$/.test(text)) throw new Error(`${label}编号缺失，请刷新后重试`)
  return text
}

export function evaluationContextKey(context) {
  return JSON.stringify([
    context.contextReady === true, context.contextMode || '', context.scopeKey || '',
    context.contextEpoch || 0, context.memberRole || '', String(context.campaign?.batchId || ''),
  ])
}

export function freezeEvaluationTarget(item, context) {
  if (!context.internshipCollabReady || !context.scopeKey) throw new Error('企业协同上下文已失效，请刷新')
  const version = item.evaluationVersion
  if (version != null && (!Number.isSafeInteger(version) || version < 0)) {
    throw new Error('企业评价版本无效，请刷新后重试')
  }
  return Object.freeze({
    internshipId: requireDecimalId(item.internshipId || item.id || item.taskId || item.task_id, '实习记录'),
    batchId: requireDecimalId(context.campaign?.batchId, '批次'),
    expectedPlacementSnapshotId: requireDecimalId(item.placementSnapshotId, '安置快照'),
    expectedVersion: version == null ? undefined : version,
    contextKey: evaluationContextKey(context),
  })
}

export function assertEvaluationContext(target, context) {
  if (!target || !context.internshipCollabReady || target.contextKey !== evaluationContextKey(context)) {
    throw new Error('企业、批次或登录上下文已变化，请重新打开评价任务')
  }
  return target
}

/** A stale success, rejection or finally block cannot publish into a newer request. */
export function createRequestFence() {
  let generation = 0
  let disposed = false
  return {
    start() { const ticket = ++generation; return () => !disposed && generation === ticket },
    invalidate() { generation += 1 },
    dispose() { disposed = true; generation += 1 },
  }
}
