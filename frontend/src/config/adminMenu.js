/**
 * 管理端跨模块菜单配置（PC-10-MODULE-INTEGRATION-FINAL-RUN 接入）。
 *
 * 定位：本文件仅提供「数据 + 权限过滤函数」，是跨模块导航的唯一事实来源。
 * 不修改、不依赖任何 Layout；BasePortalLayout「不写死业务菜单」的铁律不变，
 * 由后续全局壳 / 守卫以 props 方式消费 getVisibleAdminMenu(ctx) 的结果。
 *
 * 铁律：
 * - 不硬编码学校名（品牌名一律来自 ctx.tenantBrandConfig）。
 * - 不硬编码「当前角色」（可见性由传入的 ctx.currentRole / ctx.permissionActions 决定）。
 * - 路径与 router/index.js、各模块 routes 文件保持一致（kebab-case）。
 */

/** 角色类型（与后端 role.roleType 对齐；用于跨模块可见性判断，非角色名硬编码） */
export const ROLE_TYPE = {
  PLATFORM: 'PLATFORM', // 平台运营方 / 平台管理员（SaaS 运营侧）
  SCHOOL_ADMIN: 'SCHOOL_ADMIN', // 校级 / 学院管理员
  ACADEMIC_STAFF: 'ACADEMIC_STAFF', // 教务老师
  COUNSELOR: 'COUNSELOR', // 辅导员
  AUDITOR: 'AUDITOR' // 审计人员
}

/**
 * 一级 / 二级菜单树。
 * 每个叶子节点：
 *  - path         对应全局 router 路径
 *  - moduleCode   对应模块 meta.moduleCode
 *  - permissionKey 对应路由 meta.permissionKey（有权限体系时按此过滤）
 *  - platformOnly 仅平台角色可见
 *  - sensitive    高敏（系统敏感配置 / 审计 / 平台密钥），对受限角色隐藏
 */
export const ADMIN_MENU = [
  {
    key: 'workbench',
    label: '工作台',
    icon: '◫',
    children: [
      { key: 'wf-center', label: '权限与流程', path: '/admin/workflow', moduleCode: 'WORKFLOW', permissionKey: 'workflow.home.view' }
    ]
  },
  {
    key: 'student-center',
    label: '学生中心',
    icon: '☰',
    children: [
      { key: 'stu', label: '学生主档', path: '/admin/student', moduleCode: 'STUDENT', permissionKey: 'student.profile.view' },
      { key: 'orientation', label: '数字迎新', path: '/admin/orientation', moduleCode: 'ORIENTATION', permissionKey: 'orientation.dashboard.view' },
      { key: 'campus', label: '在校服务', path: '/admin/campus-service', moduleCode: 'CAMPUS_SERVICE', permissionKey: 'campusService.dashboard.view' },
      { key: 'academic', label: '学业过程', path: '/admin/academic', moduleCode: 'ACADEMIC', permissionKey: 'academic.dashboard.view' }
    ]
  },
  {
    key: 'practice',
    label: '教学实践',
    icon: '✎',
    children: [
      { key: 'internship', label: '岗位实习', path: '/admin/internship', moduleCode: 'INTERNSHIP', permissionKey: 'internship.dashboard.view' },
      { key: 'graduation', label: '毕业设计', path: '/admin/graduation', moduleCode: 'GRADUATION', permissionKey: 'graduation.dashboard.view' },
      { key: 'employment', label: '就业服务', path: '/admin/employment', moduleCode: 'EMPLOYMENT', permissionKey: 'employment.dashboard.view' }
    ]
  },
  {
    key: 'data-center',
    label: '数据中心',
    icon: '◐',
    children: [
      { key: 'cockpit', label: '数据驾驶舱', path: '/admin/data-center', moduleCode: 'DATA_CENTER', permissionKey: 'dataCenter.dashboard.view' },
      { key: 'approval', label: '审批中心', path: '/admin/approval', moduleCode: 'APPROVAL', permissionKey: 'approval.dashboard.view' }
    ]
  },
  {
    key: 'system',
    label: '系统管理',
    icon: '⚙',
    children: [
      { key: 'sys', label: '系统管理', path: '/admin/system', moduleCode: 'SYSTEM', permissionKey: 'system.dashboard.view' },
      { key: 'sys-sensitive', label: '安全与审计', path: '/admin/system/log', moduleCode: 'SYSTEM', permissionKey: 'system.log.view', sensitive: true }
    ]
  },
  {
    key: 'platform',
    label: '平台运营',
    icon: '☁',
    platformOnly: true,
    children: [
      { key: 'platform-ops', label: '平台运营', path: '/admin/platform', moduleCode: 'PLATFORM', permissionKey: 'platform.dashboard.view', platformOnly: true }
    ]
  }
]

/** 角色类型 → 可见模块 moduleCode 白名单（数据范围/职责边界，可被真实权限体系替换） */
const ROLE_MODULE_ALLOW = {
  [ROLE_TYPE.PLATFORM]: ['PLATFORM'],
  [ROLE_TYPE.SCHOOL_ADMIN]: ['WORKFLOW', 'STUDENT', 'ORIENTATION', 'CAMPUS_SERVICE', 'ACADEMIC', 'INTERNSHIP', 'GRADUATION', 'EMPLOYMENT', 'DATA_CENTER', 'APPROVAL', 'SYSTEM'],
  [ROLE_TYPE.ACADEMIC_STAFF]: ['STUDENT', 'ACADEMIC', 'DATA_CENTER', 'APPROVAL', 'INTERNSHIP', 'GRADUATION', 'EMPLOYMENT'],
  [ROLE_TYPE.COUNSELOR]: ['STUDENT', 'ORIENTATION', 'CAMPUS_SERVICE', 'ACADEMIC', 'INTERNSHIP'],
  [ROLE_TYPE.AUDITOR]: ['SYSTEM', 'DATA_CENTER', 'APPROVAL']
}

function roleType(ctx) {
  return (ctx && ctx.currentRole && (ctx.currentRole.roleType || ctx.currentRole.type)) || null
}

/** 某叶子节点是否有权限（优先看 permissionActions，其次角色白名单） */
function canSeeLeaf(leaf, ctx) {
  const rt = roleType(ctx)
  // 平台专属：仅平台角色
  if (leaf.platformOnly && rt !== ROLE_TYPE.PLATFORM) return false
  // 非平台模块对平台角色隐藏（平台运营方不进入学校业务）
  if (rt === ROLE_TYPE.PLATFORM && leaf.moduleCode !== 'PLATFORM') return false
  // 高敏项：辅导员不可见
  if (leaf.sensitive && rt === ROLE_TYPE.COUNSELOR) return false
  // 角色白名单（若已知角色类型）
  if (rt && ROLE_MODULE_ALLOW[rt] && !ROLE_MODULE_ALLOW[rt].includes(leaf.moduleCode)) return false
  return true
}

/**
 * 按 ctx（品牌/角色/权限）过滤出当前角色可见的菜单树。
 * ctx 缺省时返回「学校侧默认视图」（隐藏平台运营），不暴露平台能力。
 * @param {object} ctx getContext() 返回体（含 currentRole / permissionActions）
 * @returns {Array} 过滤后的菜单树（已剔除空分组）
 */
export function getVisibleAdminMenu(ctx) {
  const rt = roleType(ctx)
  return ADMIN_MENU
    .filter((group) => {
      if (group.platformOnly && rt !== ROLE_TYPE.PLATFORM) return false
      return true
    })
    .map((group) => ({ ...group, children: group.children.filter((leaf) => canSeeLeaf(leaf, ctx)) }))
    .filter((group) => group.children.length > 0)
}

/** 依据当前路径定位激活的一级/二级 key（供壳高亮使用） */
export function findActiveMenu(path) {
  for (const group of ADMIN_MENU) {
    const leaf = [...group.children]
      .sort((a, b) => b.path.length - a.path.length)
      .find((l) => path === l.path || path.startsWith(l.path + '/'))
    if (leaf) return { groupKey: group.key, leafKey: leaf.key }
  }
  return { groupKey: '', leafKey: '' }
}

export default ADMIN_MENU
