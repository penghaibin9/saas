/**
 * Standalone 岗位实习唯一导航事实源。
 * 只保留岗位实习域；原 SaaS 的学工/教务/毕设/就业/平台导航不进入独立产品。
 */
function leaf(label, path, permissionKey, entryType = 'WORKBENCH', extra = {}) {
  return { label, path, permissionKey, entryType, status: 'implemented', disabled: false, badge: '', ...extra }
}
function hidden(label, path, permissionKey, entryType = 'DETAIL', extra = {}) {
  return { ...leaf(label, path, permissionKey, entryType, extra), hidden: true }
}
function mod(key, label, path, children = []) {
  return { key, label, path, status: 'implemented', disabled: false, badge: '', children }
}

export const NAV_PLAN = [{
  key: 'internship',
  label: '岗位实习中心',
  moduleKey: 'internship',
  children: [
    mod('in-workbench', '今日工作', '/admin/internship', [
      leaf('待办与进度', '/admin/internship', 'internship.dashboard.view'),
      hidden('全局趋势 / 统计', '/admin/internship/stats?dimension=trend', 'internship.stats.view', 'ANALYTICS_VIEW'),
      hidden('当前批次进度', '/admin/internship?panel=batch-progress', 'internship.dashboard.view')
    ]),
    mod('in-command-screen', '实习中心大屏', '/admin/internship/command-screen', [
      leaf('实习中心大屏', '/admin/internship/command-screen', 'internship.stats.view', 'ANALYTICS_VIEW')
    ]),
    mod('in-batch-rules', '批次与学生', '/admin/internship/batches', [
      leaf('批次管理', '/admin/internship/batches?panel=list', 'internship.batch.view', 'WORKBENCH', { workspacePaths: ['/admin/internship/batches'] }),
      leaf('学生名单', '/admin/internship/students?panel=roster', 'internship.student.view', 'WORKBENCH', { workspacePaths: ['/admin/internship/students'] }),
      leaf('资格认定', '/admin/internship/students?panel=eligibility', 'internship.student.eligibility.review', 'TASK_QUEUE'),
      hidden('参与学生配置', '/admin/internship/batches?panel=participants', 'internship.batch.manage', 'CONFIG_VIEW'),
      hidden('阶段与规则配置', '/admin/internship/batches?panel=configuration', 'internship.batch.manage', 'CONFIG_VIEW'),
      hidden('学生材料', '/admin/internship/archive?panel=materials', 'internship.student.material.view')
    ]),
    mod('in-enterprise-position', '企业与岗位', '/admin/internship/enterprises', [
      leaf('企业库', '/admin/internship/enterprises?panel=list', 'internship.enterprise.view', 'WORKBENCH', { workspacePaths: ['/admin/internship/enterprises'] }),
      leaf('岗位库', '/admin/internship/positions?panel=list', 'internship.position.view', 'WORKBENCH', { workspacePaths: ['/admin/internship/positions'] }),
      leaf('招聘与邀请', '/admin/internship/recruitment-campaigns', 'internship.recruitment.view'),
      leaf('企业准入', '/admin/internship/enterprises?panel=qualification', 'internship.enterprise.manage', 'TASK_QUEUE'),
      hidden('企业联系人', '/admin/internship/enterprises?panel=contacts', 'internship.enterprise.contact.view'),
      hidden('企业导师', '/admin/internship/enterprises?panel=mentor', 'internship.enterprise.mentor.view')
    ]),
    mod('in-match-assign', '申请与落岗', '/admin/internship/applications', [
      leaf('岗位确认', '/admin/internship/volunteer-review', 'internship.application.view', 'TASK_QUEUE'),
      leaf('申请审核', '/admin/internship/applications?status=PENDING_REVIEW', 'internship.application.view', 'TASK_QUEUE'),
      leaf('岗位匹配', '/admin/internship/match?panel=intention', 'internship.match.intention.view'),
      leaf('导师分配', '/admin/internship/students?panel=mentor', 'internship.student.view', 'TASK_QUEUE'),
      leaf('三方协议', '/admin/internship/agreements?panel=confirm', 'internship.agreement.view', 'TASK_QUEUE', { workspacePaths: ['/admin/internship/agreements', '/admin/internship/agreement-templates'] }),
      leaf('保险核验', '/admin/internship/insurance', 'internship.insurance.view', 'TASK_QUEUE'),
      leaf('上岗核验', '/admin/internship/compliance?tab=overview', 'internship.compliance.view'),
      leaf('分配记录', '/admin/internship/assignment-logs', 'internship.match.log.view', 'ANALYTICS_VIEW')
    ]),
    mod('in-attendance-leave', '实习过程', '/admin/internship/attendance', [
      leaf('考勤记录', '/admin/internship/attendance?panel=checkins', 'internship.attendance.view', 'WORKBENCH', { workspacePaths: ['/admin/internship/attendance?panel=makeup-apply', '/admin/internship/attendance?panel=makeup-review'] }),
      leaf('月度工资台账', '/admin/internship/payroll', 'internship.payroll.view'),
      leaf('异常核验', '/admin/internship/attendance?panel=exceptions', 'internship.attendance.view', 'TASK_QUEUE', { workspacePaths: ['/admin/internship/exceptions'] }),
      leaf('请假与返岗', '/admin/internship/leaves?panel=pending', 'internship.leave.view', 'TASK_QUEUE', { workspacePaths: ['/admin/internship/leaves'] }),
      leaf('通知公告', '/admin/internship/notices', 'internship.communication.view'),
      leaf('计划任务', '/admin/internship/plans', 'internship.plan.view', 'CONFIG_VIEW'),
      leaf('报告批阅', '/admin/internship/reports?panel=review', 'internship.report.view', 'TASK_QUEUE', { workspacePaths: ['/admin/internship/reports', '/admin/internship/process-reports'] }),
      leaf('指导巡访', '/admin/internship/guidance?panel=guidance', 'internship.guidance.view', 'WORKBENCH', { workspacePaths: ['/admin/internship/guidance/new', '/admin/internship/guidance?panel=communication', '/admin/internship/guidance?panel=visit', '/admin/internship/guidance?panel=visit-plan'] }),
      leaf('我的指导报告', '/admin/internship/my-reports', 'internship.guidance.view'),
      leaf('教师本人报告', '/admin/internship/teacher-reports', 'internship.stats.view', 'WORKBENCH', { schoolAdminOnly: true }),
      leaf('教师工作台账', '/admin/internship/teacher-management', 'internship.stats.view', 'WORKBENCH', { schoolAdminOnly: true }),
      leaf('指导计划', '/admin/internship/guidance-plan', 'internship.guidance.view', 'CONFIG_VIEW')
    ]),
    mod('in-risk', '风险与变更', '/admin/internship/risks', [
      leaf('风险预警', '/admin/internship/risks?panel=board', 'internship.risk.view'),
      leaf('学生意见反馈', '/admin/internship/feedback', 'internship.complaint.view', 'TASK_QUEUE'),
      leaf('风险处置', '/admin/internship/risk-disposal?stage=pending', 'internship.risk.handle', 'TASK_QUEUE'),
      leaf('调岗退岗', '/admin/internship/changes?panel=pending', 'internship.change.view', 'TASK_QUEUE'),
      leaf('事故与应急', '/admin/internship/compliance?tab=incidents', 'internship.incident.handle', 'TASK_QUEUE')
    ]),
    mod('in-eval-score', '评价与成绩', '/admin/internship/enterprise-evals', [
      leaf('企业评价', '/admin/internship/enterprise-evals', 'internship.eval.enterprise.view'),
      leaf('学生与教师评价', '/admin/internship/student-evals?view=self', 'internship.eval.self.view', 'WORKBENCH', { workspacePaths: ['/admin/internship/student-evals'] }),
      leaf('综合成绩', '/admin/internship/scores?stage=overview', 'internship.score.view', 'WORKBENCH', { workspacePaths: ['/admin/internship/scores'] }),
      leaf('成绩申诉', '/admin/internship/scores?stage=appeal', 'internship.score.publish', 'TASK_QUEUE')
    ]),
    mod('in-archive-stats', '归档与分析', '/admin/internship/archive', [
      leaf('就业上报', '/admin/internship/employment', 'internship.employment.view', 'TASK_QUEUE'),
      leaf('材料归档', '/admin/internship/archive?panel=records', 'internship.archive.view', 'WORKBENCH', { workspacePaths: ['/admin/internship/archive', '/admin/internship/material-center', '/admin/internship/material-requirements'] }),
      leaf('正式文书', '/admin/internship/formal-documents', 'internship.archive.view', 'WORKBENCH'),
      leaf('实习统计', '/admin/internship/stats?dimension=overview', 'internship.stats.view', 'ANALYTICS_VIEW'),
      leaf('监管上报', '/admin/internship/regulatory-reporting', 'internship.reporting.view', 'WORKBENCH')
    ])
  ]
}, {
  key: 'system', label: '系统管理', moduleKey: 'system', children: [
    mod('sys-overview', '管理概览', '/admin/system', [leaf('系统管理概览', '/admin/system', 'system.overview.view')]),
    mod('sys-people', '组织与人员', '/admin/system/organizations', [
      leaf('组织架构', '/admin/system/organizations', 'system.org.view'),
      leaf('教职工资料', '/admin/system/staff', 'system.staff.view'),
      leaf('学生资料', '/admin/system/students', 'system.student.view')]),
    mod('sys-identity', '账号与权限', '/admin/system/accounts', [
      leaf('用户账号', '/admin/system/accounts', 'system.account.view'),
      leaf('角色与权限', '/admin/system/roles', 'system.role.view'),
      leaf('管理范围与责任关系', '/admin/system/scopes', 'system.scope.view')]),
    mod('sys-rules', '规则与基础配置', '/admin/system/brand', [
      leaf('学校资料与品牌', '/admin/system/brand', 'system.brand.view'),
      leaf('基础字典', '/admin/system/dictionary', 'system.dictionary.view'),
      leaf('请假审批配置', '/admin/system/leave-policy', 'system.leave-policy.view'),
      leaf('通知与服务设置', '/admin/system/notification', 'system.notification.view')]),
    mod('sys-data', '数据与对接', '/admin/system/identity-import/students', [
      leaf('师生导入与账号开通', '/admin/system/identity-import/students', 'system.identity-import.view', 'WORKBENCH', { workspacePaths: ['/admin/system/identity-import/staff'] }),
      leaf('导入导出任务', '/admin/system/tasks', 'system.task.view'),
      leaf('历史数据迁移', '/admin/system/migration', 'system.migration.view'),
      leaf('外部服务与对接', '/admin/system/integrations', 'system.integration.view')]),
    mod('sys-security', '安全与运维', '/admin/system/audit', [
      leaf('登录与操作审计', '/admin/system/audit', 'system.audit.view'),
      leaf('运行与备份状态', '/admin/system/runtime', 'system.runtime.view'),
      leaf('版本与交付资料', '/admin/system/delivery', 'system.delivery.view')])
  ]
}]

export function matchPermission(patterns, code) {
  if (!Array.isArray(patterns) || !code) return false
  return patterns.some((p) => p === '*' || p === code ||
    (p.endsWith('.*') && (code === p.slice(0, -2) || code.startsWith(p.slice(0, -1)))) ||
    (p.startsWith('*.') && code.endsWith(p.slice(1))))
}

function leafVisible(leaf, patterns, currentRole) {
  if (leaf.hidden) return false
  if (leaf.schoolAdminOnly && !['SCHOOL_ADMIN', 'PLATFORM_SUPER_ADMIN'].includes(currentRole?.baseRoleCode || currentRole?.roleCode)) return false
  if (!Array.isArray(patterns)) return true
  if (leaf.permissionKey && !matchPermission(patterns, leaf.permissionKey)) return false
  if (Array.isArray(leaf.permissionAny) && leaf.permissionAny.length &&
      !leaf.permissionAny.some((code) => matchPermission(patterns, code))) return false
  return true
}

export function getVisibleNavPlan({ permissionPatterns = null, currentRole = null } = {}) {
  return NAV_PLAN.map((group) => ({
    ...group,
    children: group.children.map((m) => ({
      ...m,
      children: m.children.filter((item) => leafVisible(item, permissionPatterns, currentRole))
    })).filter((m) => m.children.length > 0)
  })).filter((group) => group.children.length > 0)
}

export function splitNavRef(ref) {
  if (!ref) return { path: '', query: '' }
  const q = ref.indexOf('?')
  return q === -1 ? { path: ref, query: '' } : { path: ref.slice(0, q), query: ref.slice(q + 1) }
}

function normalizeQuery(query) {
  if (!query) return ''
  return query.split('&').filter(Boolean).sort().join('&')
}

const DEFAULT_PANEL_BY_PATH = {
  '/admin/internship/students': 'roster',
  '/admin/internship/batches': 'list',
  '/admin/internship/enterprises': 'list',
  '/admin/internship/positions': 'list',
  '/admin/internship/match': 'intention',
  '/admin/internship/guidance': 'guidance'
}

export function normalizeNavRef(fullPath) {
  const ref = String(fullPath || '').split('#')[0]
  const { path, query } = splitNavRef(ref)
  const fallback = DEFAULT_PANEL_BY_PATH[path]
  const normalized = normalizeQuery(query || (fallback ? `panel=${fallback}` : ''))
  return normalized ? `${path}?${normalized}` : path
}

export function navRefExactMatch(currentRef, candidateRef) {
  return !!candidateRef && normalizeNavRef(currentRef) === normalizeNavRef(candidateRef)
}

export function navRefMatches(currentRef, candidateRef) {
  if (!candidateRef) return false
  const cur = splitNavRef(normalizeNavRef(currentRef))
  const cand = splitNavRef(normalizeNavRef(candidateRef))
  if (cand.query) return cur.path === cand.path && cur.query === cand.query
  return cur.path === cand.path || cur.path.startsWith(`${cand.path}/`)
}

const FLAT = NAV_PLAN.flatMap((group) => group.children.flatMap((m) =>
  m.children.map((item, index) => ({ ...item, groupKey: group.key, groupLabel: group.label, modKey: m.key, modLabel: m.label, leafKey: `${m.key}:${index}` }))
))

export function findActiveInPlan(path, fullPath = '') {
  const ref = fullPath || path
  let best = { groupKey: '', modKey: '', leafKey: '', score: -1 }
  for (const row of FLAT) {
    const candidates = [row.path, ...(row.workspacePaths || [])].filter(Boolean)
    for (const candidate of candidates) {
      if (!navRefMatches(ref, candidate)) continue
      const score = candidate.length + (candidate.includes('?') ? 1000 : 0)
      if (score > best.score) best = { groupKey: row.groupKey, modKey: row.modKey, leafKey: row.leafKey, score }
    }
  }
  return { groupKey: best.groupKey, modKey: best.modKey, leafKey: best.leafKey }
}

export function searchNavPlan(query, permissionPatterns = null) {
  const q = String(query || '').trim().toLowerCase()
  if (!q) return []
  return FLAT.filter((row) => !row.hidden)
    .filter((row) => !Array.isArray(permissionPatterns) || !row.permissionKey || matchPermission(permissionPatterns, row.permissionKey))
    .filter((row) => row.label.toLowerCase().includes(q))
    .map((row) => ({
      label: row.label,
      path: row.path,
      status: row.status,
      disabled: false,
      badge: '',
      groupKey: row.groupKey,
      trail: `${row.groupLabel} / ${row.modLabel} / ${row.label}`
    }))
}
