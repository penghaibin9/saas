import { renewalInputFromUtc } from './moduleCommerceSales.mjs'

export const COMMERCIAL_DESTINATIONS = Object.freeze([
  { key: 'sales', label: '商品与订购', description: '发布商品、分项新购、订单台账' },
  { key: 'renewal', label: '到期与续费', description: '客户跟进、续费衔接' },
  { key: 'finance', label: '应收、退款与发票', description: '申请、审批、外部凭据登记' },
  { key: 'operations', label: '售后与服务成本', description: '工单、明确SLA、实际成本' },
  { key: 'lifecycle', label: '交付与模块退出', description: '验收、停续、冻结、签收' },
  { key: 'review', label: '退出完整性检查', description: '只读查看阻断，不执行清理' },
  { key: 'reconciliation', label: '用量与对账', description: '商业额度与实际消费' }
])

const MODULES = new Set(['internship', 'graduationDesign', 'studentAffairs', 'academicAffairs'])
const id = (value) => typeof value === 'string' && /^[1-9]\d{0,18}$/.test(value) && BigInt(value) <= 9223372036854775807n
const integer = (value, minimum = 0) => Number.isSafeInteger(value) && value >= minimum

// A handoff is only a draft suggestion, not an order or an entitlement. Resolve the
// current paid boundary after loading the selected school's server context again.
export function buildRenewalHandoff(candidate, context, tenantId) {
  if (!id(tenantId) || candidate?.tenantId !== tenantId || context?.tenantId !== tenantId) {
    throw new Error('续费来源不属于当前学校，未更改销售草稿')
  }
  const moduleKey = candidate.moduleKey
  if (!MODULES.has(moduleKey) || candidate.canStartRenewalOrder !== true || candidate.blocker) {
    throw new Error('此来源当前不能进入续费办理，请刷新续费候选')
  }
  const state = context.states?.[moduleKey]
  if (context.tenantStatus !== 'ACTIVE' || state?.dataState !== 'AVAILABLE' ||
      !integer(candidate.moduleGeneration, 1) || state.generation !== candidate.moduleGeneration) {
    throw new Error('学校或模块状态、代次已变化，未更改销售草稿')
  }
  const paidThrough = context.paidThrough?.[moduleKey]
  // Require a timezone-bearing server instant. Never interpret a naive timestamp
  // using the operator's browser timezone, and never reuse the old candidate price.
  if (typeof paidThrough !== 'string' || !/(Z|[+-]\d{2}:\d{2})$/.test(paidThrough)) {
    throw new Error('当前已付截止不可核验，请刷新后再办理续费')
  }
  return Object.freeze({
    tenantId, moduleKey, generation: state.generation, orderType: 'RENEW',
    startLocal: renewalInputFromUtc(paidThrough), paidThrough,
    sourceId: String(candidate.sourceId || ''),
    priceMustBeReconfirmed: true, endAtMustBeExplicit: true
  })
}

export function exitReviewScope(tenantId, job) {
  if (!id(tenantId) || job?.tenantId !== tenantId || !id(job?.jobId) ||
      !MODULES.has(job?.moduleKey) || !integer(job?.moduleGeneration, 1) || !integer(job?.version)) {
    throw new Error('请先刷新当前学校的退出任务，不能使用其他学校或旧任务的检查上下文')
  }
  return Object.freeze({ tenantId, jobId: job.jobId, moduleKey: job.moduleKey,
    expectedGeneration: job.moduleGeneration, expectedVersion: job.version })
}

export function validateExitReview(data, scope) {
  if (!data || data.tenantId !== scope.tenantId || data.jobId !== scope.jobId ||
      data.moduleKey !== scope.moduleKey || data.moduleGeneration !== scope.expectedGeneration ||
      data.jobVersion !== scope.expectedVersion) throw new Error('检查回执与当前学校、模块或任务版本不一致，请刷新')
  if (data.dryRunOnly !== true || data.destructiveExecutionAvailable !== false ||
      data.physicalPurgeAuthorized !== false || data.deletionAuthorized !== false ||
      data.canExecutePhysicalPurge !== false || data.fullResourceClosureComplete !== false ||
      !Array.isArray(data.destructiveStatements) || data.destructiveStatements.length !== 0) {
    throw new Error('检查回执越过只读边界，已停止展示；本页不能授权清理')
  }
  const mandatory = ['M0_FULL_RESOURCE_CLOSURE_REQUIRED', 'MODULE_PURGE_EXECUTION_DISABLED', 'BACKUP_DISPOSITION_POLICY_REQUIRED']
  if (!Array.isArray(data.blockers) || !data.blockers.every(row => typeof row?.code === 'string' && typeof row?.message === 'string') ||
      !mandatory.every(code => data.blockers.some(row => row.code === code))) {
    throw new Error('检查回执缺少必要的阻断信息，不能当作完整检查结果')
  }
  return data
}

export function blockerGroup(code) {
  if (/^(M0_|MODULE_PURGE_|BACKUP_|TENANT_PURGE_|MODULE_SELECTOR_)/.test(code)) return '技术准入与备份'
  if (/^(RETENTION_|EXPORT_|VERIFIED_EXPORT_|MODULE_NOT_RETAINED)/.test(code)) return '交付与保留'
  if (/^(LEGAL_HOLD_|SHARED_FILE_|ACTIVE_STORAGE_)/.test(code)) return '文件与共享引用'
  return '任务、模块与消费者'
}
