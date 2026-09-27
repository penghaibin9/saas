import { NAV_PLAN, getVisibleNavPlan } from '../../config/navPlan.js'

export const INTERNSHIP_WORKSPACE_INFO = {
  'in-command-screen': { short: '大屏', icon: 'overview', hint: '查看当前批次的实习分布、全过程进度与风险' },
  'in-workbench': { short: '今日', icon: 'workbench', hint: '从待办开始，按当前批次连续办理' },
  'in-batch-rules': { short: '准备', icon: 'students', hint: '确定实习周期、学生名单和参与资格' },
  'in-enterprise-position': { short: '岗位', icon: 'topics', hint: '核对企业准入，准备可用岗位' },
  'in-match-assign': {
    short: '落岗',
    icon: 'enrollment',
    hint: '申请审核 → 岗位与导师 → 协议保险 → 上岗核验'
  },
  'in-attendance-leave': { short: '过程', icon: 'records', hint: '考勤、请假、报告与指导持续跟进' },
  'in-risk': { short: '风险', icon: 'risk', hint: '核实问题、跟进变更，办结后返回实习过程' },
  'in-eval-score': { short: '评价', icon: 'reports', hint: '多方评价 → 成绩核算 → 审核发布与申诉' },
  'in-employment-archive-stats': {
    short: '归档',
    icon: 'overview',
    hint: '核对材料、完成归档，衔接就业跟进'
  }
}

export function internshipWorkspaces(ctx) {
  if (!Array.isArray(ctx?.permissionPatterns) || ctx.permissionServiceError) return []
  const group = getVisibleNavPlan({
    permissionPatterns: ctx.permissionPatterns,
    ctxKey: ctx.ctxKey || ''
  }).find((item) => item.key === 'internship')
  return (group?.children || []).map((item) => ({
    ...item,
    ...INTERNSHIP_WORKSPACE_INFO[item.key],
    path: item.children[0]?.path || item.path
  }))
}

export function withInternshipBatch(ref, batchId) {
  const url = new URL(ref, 'https://local.invalid')
  if (url.pathname.startsWith('/admin/internship') && batchId && !url.searchParams.has('batchId')) {
    url.searchParams.set('batchId', String(batchId))
  }
  return { path: url.pathname, query: Object.fromEntries(url.searchParams), hash: url.hash }
}

// Batch workspaces return to the filtered list even after a refresh or a new tab.
export function internshipBatchListReturn(query = {}, batchId) {
  const ref = query.returnTo
  if (typeof ref === 'string' && /^\/admin\/internship\/batches(?:\?|$)/.test(ref)) return ref
  return withInternshipBatch('/admin/internship/batches?panel=list', batchId)
}

// A new batch must not reuse the previous batch's object id or review queue.
export function internshipBatchSwitch(ref, batchId) {
  const current = new URL(ref, 'https://local.invalid')
  const owner = internshipLocation(ref, internshipWorkspaces({ permissionPatterns: ['*'] }))
  const landing = new URL(owner.path || '/admin/internship', 'https://local.invalid')
  const target = current.pathname === landing.pathname ? current : landing
  for (const key of [
    'batchId',
    'page',
    'id',
    'studentId',
    'internshipId',
    'recordId',
    'resumeKey',
    'queueKey',
    'campaignId',
    'section',
    'mode',
    'file',
    'appealId',
    'fromAppeal',
    'appealPage',
    'receipt'
  ])
    target.searchParams.delete(key)
  target.hash = ''
  return withInternshipBatch(target.pathname + target.search, batchId)
}

// Parameters such as batchId/page/keyword are context, not a second menu identity.
// Hidden capability entries still determine the owner of old bookmarks and detail pages.
export function internshipLocation(
  ref,
  workspaces = NAV_PLAN.find((g) => g.key === 'internship').children
) {
  const current = new URL(ref, 'https://local.invalid')
  current.pathname = current.pathname.replace(
    '/admin/internship/process-reports/',
    '/admin/internship/reports/'
  )
  // 材料阅读是归档工作区的对象深链，沿用该三级菜单的归属与高亮。
  if (current.pathname === '/admin/internship/material-center') current.pathname = '/admin/internship/archive'
  let best = { workspaceKey: '', path: '', label: '', score: -1 }
  for (const workspace of workspaces) {
    for (const leaf of workspace.children) {
      if (!leaf.path) continue
      const candidate = new URL(leaf.path, 'https://local.invalid')
      const exactPath = current.pathname === candidate.pathname
      if (!exactPath && !current.pathname.startsWith(candidate.pathname + '/')) continue
      const entries = [...candidate.searchParams].filter(([key]) => key !== 'batchId')
      const matches = entries.every(([key, value]) => current.searchParams.get(key) === value)
      const score =
        candidate.pathname.length + (exactPath ? 100 : 0) + (matches ? entries.length * 1000 : 0)
      if (score > best.score)
        best = { workspaceKey: workspace.key, path: leaf.path, label: leaf.label, score }
    }
  }
  return best
}
