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
    /* 一级①工作台：我的工作台 + 待办/审批中心（原审批中心）+ 领导驾驶舱（原数据中心驾驶舱） */
    key: 'workbench',
    label: '工作台',
    icon: '◫',
    children: [
      { key: 'wb-home', label: '我的工作台', path: '/', moduleCode: 'WORKBENCH', permissionKey: 'workbench.home.view' },
      { key: 'wb-todo', label: '我的待办', path: '/admin/approval/todos', moduleCode: 'APPROVAL', permissionKey: 'approval.todo.view' },
      { key: 'wb-approval', label: '审批中心', path: '/admin/approval', moduleCode: 'APPROVAL', permissionKey: 'approval.dashboard.view' },
      { key: 'wb-cockpit', label: '领导驾驶舱', path: '/admin/data-center', moduleCode: 'DATA_CENTER', permissionKey: 'dataCenter.dashboard.view' }
    ]
  },
  {
    /* 一级②学工中心：B 包主线 / 数字迎新外部承接 / 在校服务过渡入口 */
    key: 'student-affairs',
    label: '学工中心',
    icon: '☰',
    children: [
      { key: 'sa-dashboard', label: '学工看板', path: '/admin/student-affairs/dashboard', moduleCode: 'STUDENT_AFFAIRS', permissionKey: 'studentAffairs.dashboard.view' },
      { key: 'sa-profile', label: '学生画像', path: '/admin/student-affairs/profile', moduleCode: 'STUDENT_AFFAIRS', permissionKey: 'studentAffairs.profile.view' },
      { key: 'sa-classes', label: '班级管理', path: '/admin/student-affairs/classes', moduleCode: 'STUDENT_AFFAIRS', permissionKey: 'studentAffairs.classes.view' },
      { key: 'sa-dormitory', label: '宿舍管理', path: '/admin/student-affairs/dormitory', moduleCode: 'STUDENT_AFFAIRS', permissionKey: 'studentAffairs.dorm.view' },
      { key: 'sa-leave', label: '????', path: '/admin/student-affairs/leave', moduleCode: 'STUDENT_AFFAIRS', permissionKey: 'studentAffairs.leave.view' },
      { key: 'sa-risk', label: '????', path: '/admin/student-affairs/risk', moduleCode: 'STUDENT_AFFAIRS', permissionKey: 'studentAffairs.risk.view' },
      { key: 'sa-orientation', label: '数字迎新', path: '/admin/orientation', moduleCode: 'ORIENTATION', permissionKey: 'orientation.dashboard.view' },
      { key: 'sa-campus', label: '在校服务', path: '/admin/campus-service', moduleCode: 'CAMPUS_SERVICE', permissionKey: 'campusService.dashboard.view' }
    ]
  },
  {
    /* 一级③教务中心：学业过程（原学生中心＞学业过程迁入） */
    key: 'academic-affairs',
    label: '教务中心',
    icon: '◈',
    children: [
      { key: 'aa-academic', label: '学业过程', path: '/admin/academic', moduleCode: 'ACADEMIC', permissionKey: 'academic.dashboard.view' }
    ]
  },
  {
    /* 一级④毕业设计中心：原教学实践＞毕业设计独立成一级 */
    key: 'graduation',
    label: '毕业设计中心',
    icon: '✿',
    children: [
      { key: 'gd-graduation', label: '毕业设计', path: '/admin/graduation', moduleCode: 'GRADUATION', permissionKey: 'graduation.dashboard.view' }
    ]
  },
  {
    /* 一级⑤岗位实习中心：原教学实践＞岗位实习 + 就业服务迁入 */
    key: 'internship',
    label: '岗位实习中心',
    icon: '✎',
    children: [
      { key: 'in-internship', label: '岗位实习', path: '/admin/internship', moduleCode: 'INTERNSHIP', permissionKey: 'internship.dashboard.view' },
      { key: 'in-employment', label: '就业服务', path: '/admin/employment', moduleCode: 'EMPLOYMENT', permissionKey: 'employment.dashboard.view' }
    ]
  },
  {
    /* 一级⑥系统管理：权限与流程（原一级“权限与流程”迁入）+ 系统管理 + 安全与审计 */
    key: 'system',
    label: '系统管理',
    icon: '⚙',
    children: [
      // 首叶置「系统管理」，保证点击系统管理一级默认进入管理看板 /admin/system
      { key: 'sys-system', label: '系统管理', path: '/admin/system', moduleCode: 'SYSTEM', permissionKey: 'system.dashboard.view' },
      { key: 'sys-workflow', label: '权限与流程', path: '/admin/workflow', moduleCode: 'WORKFLOW', permissionKey: 'workflow.home.view' },
      { key: 'sys-sensitive', label: '安全与审计', path: '/admin/system/logs', moduleCode: 'SYSTEM', permissionKey: 'system.log.view', sensitive: true }
    ]
  },
  {
    key: 'platform',
    label: '平台运营',
    icon: '☁',
    platformOnly: true,
    children: [
      { key: 'platform-control', label: '平台总控台', path: '/admin/platform/overview', moduleCode: 'PLATFORM', permissionKey: 'platform.control.view', platformOnly: true },
      { key: 'platform-tenants', label: '租户学校管控', path: '/admin/platform/tenants', moduleCode: 'PLATFORM', permissionKey: 'platform.tenant.view', platformOnly: true },
      { key: 'platform-rules', label: '规则与功能开关', path: '/admin/platform/rules', moduleCode: 'PLATFORM', permissionKey: 'platform.rule.view', platformOnly: true },
      { key: 'platform-orders', label: '订单与开通', path: '/admin/platform/orders', moduleCode: 'PLATFORM', permissionKey: 'platform.order.view', platformOnly: true },
      { key: 'platform-notices', label: '平台公告', path: '/admin/platform/notices', moduleCode: 'PLATFORM', permissionKey: 'platform.notice.view', platformOnly: true },
      { key: 'platform-security', label: '安全与审计', path: '/admin/platform/security', moduleCode: 'PLATFORM', permissionKey: 'platform.security.view', platformOnly: true },
      { key: 'platform-ops', label: '平台运营', path: '/admin/platform', moduleCode: 'PLATFORM', permissionKey: 'platform.dashboard.view', platformOnly: true }
    ]
  }
]

/** 角色类型 → 可见模块 moduleCode 白名单（数据范围/职责边界，可被真实权限体系替换） */
const ROLE_MODULE_ALLOW = {
  // 说明：本轮导航重组只「新增」虚拟模块 WORKBENCH（我的工作台，人人可见），
  // 其余各业务 moduleCode 的角色可见性一字未改 —— 不扩大任何角色的数据/菜单权限。
  [ROLE_TYPE.PLATFORM]: ['PLATFORM'],
  [ROLE_TYPE.SCHOOL_ADMIN]: ['WORKBENCH', 'WORKFLOW', 'STUDENT_AFFAIRS', 'STUDENT', 'ORIENTATION', 'CAMPUS_SERVICE', 'ACADEMIC', 'INTERNSHIP', 'GRADUATION', 'EMPLOYMENT', 'DATA_CENTER', 'APPROVAL', 'SYSTEM'],
  [ROLE_TYPE.ACADEMIC_STAFF]: ['WORKBENCH', 'STUDENT', 'ACADEMIC', 'DATA_CENTER', 'APPROVAL', 'INTERNSHIP', 'GRADUATION', 'EMPLOYMENT'],
  [ROLE_TYPE.COUNSELOR]: ['WORKBENCH', 'STUDENT_AFFAIRS', 'STUDENT', 'ORIENTATION', 'CAMPUS_SERVICE', 'ACADEMIC', 'INTERNSHIP'],
  [ROLE_TYPE.AUDITOR]: ['WORKBENCH', 'SYSTEM', 'DATA_CENTER', 'APPROVAL']
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

/**
 * 旧一级/分组 key → 新一级模块 key 的兼容映射（PC-NAV-6MODULE-REGROUP）。
 * 说明：权限过滤依赖的是叶子 moduleCode（本轮完全未改），不依赖分组 key，
 * 故此表仅用于：① 老代码/书签若引用旧分组 key 时的定位兜底；② 顶部搜索旧名称跳转。
 * 不参与任何权限校验，纯数据。
 */
export const LEGACY_GROUP_KEY_MAP = {
  'student-center': 'student-affairs', // 学生中心 → 学工中心
  practice: 'graduation', // 教学实践（毕设/实习/就业已拆分）→ 默认落毕业设计中心
  'data-center': 'workbench', // 数据中心 → 工作台（领导驾驶舱）
  'wf-center': 'system' // 权限与流程 → 系统管理
}

/**
 * 顶部搜索别名表：旧名称 / 新名称 → 目标路径（供 ⌘K 搜索功能施工时消费）。
 * ⚠️ 现状：顶部 ⌘K 搜索为静态占位、暂无交互逻辑（见「待施工清单」），
 * 本表先行备好，功能施工时直接读取即可，不新增假入口。
 */
export const SEARCH_ALIASES = [
  { keywords: ['工作台', '我的工作台', '首页'], path: '/', label: '工作台 / 我的工作台' },
  { keywords: ['学工中心', '学工看板', '学工总览', '辅导员待办'], path: '/admin/student-affairs/dashboard', label: '学工中心 / 学工看板' },
  { keywords: ['学生中心', '学生画像', '学生主档'], path: '/admin/student-affairs/profile', label: '学工中心 / 学生画像' },
  { keywords: ['班级管理', '班级学生', '辅导员绑定', '班干部'], path: '/admin/student-affairs/classes', label: '学工中心 / 班级管理' },
  { keywords: ['宿舍管理', '楼栋', '房间', '床位', '夜不归宿'], path: '/admin/student-affairs/dormitory', label: '学工中心 / 宿舍管理' },
  { keywords: ['????', '????', '????', '????'], path: '/admin/student-affairs/leave', label: '???? / ????' },
  { keywords: ['????', '????', '????', '????'], path: '/admin/student-affairs/risk', label: '???? / ????' },
  { keywords: ['数字迎新', '迎新', '新生报到'], path: '/admin/orientation', label: '学工中心 / 数字迎新' },
  { keywords: ['在校服务', '请假', '奖助', '宿舍', '违纪'], path: '/admin/campus-service', label: '学工中心 / 在校服务' },
  { keywords: ['学业过程', '教务中心', '成绩', '课程', '学业预警'], path: '/admin/academic', label: '教务中心 / 学业过程' },
  { keywords: ['教学实践', '毕业设计', '毕设', '选题', '答辩'], path: '/admin/graduation', label: '毕业设计中心' },
  { keywords: ['岗位实习', '实习', '打卡', '周报'], path: '/admin/internship', label: '岗位实习中心' },
  { keywords: ['企业库', '合作企业', '企业列表'], path: '/admin/internship/enterprises', label: '岗位实习中心 / 企业库' },
  { keywords: ['企业岗位', '岗位库', '岗位资源'], path: '/admin/internship/positions', label: '岗位实习中心 / 岗位库' },
  { keywords: ['岗位匹配', '学生意向', '专业匹配', '匹配确认'], path: '/admin/internship/match', label: '岗位实习中心 / 岗位匹配' },
  { keywords: ['就业服务', '就业', '未就业帮扶'], path: '/admin/employment', label: '岗位实习中心 / 就业服务' },
  { keywords: ['数据中心', '数据驾驶舱', '领导驾驶舱', '生命周期'], path: '/admin/data-center', label: '工作台 / 领导驾驶舱' },
  { keywords: ['审批中心', '我的待办', '待办', '已办'], path: '/admin/approval', label: '工作台 / 审批中心' },
  { keywords: ['权限与流程', '流程配置', '审批模板', '角色', '权限'], path: '/admin/workflow', label: '系统管理 / 权限与流程' },
  { keywords: ['系统管理', '用户', '菜单', '数据范围', '品牌'], path: '/admin/system', label: '系统管理' },
  { keywords: ['安全审计', '日志', '安全与审计'], path: '/admin/system/logs', label: '系统管理 / 安全与审计' }
]

export default ADMIN_MENU
