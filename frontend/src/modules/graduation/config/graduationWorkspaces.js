/**
 * 毕业设计中心 · 总览 + 6 个阶段 + 更多，共 8 个工作区（单一事实源）；阶段页的页签就是原有页面。
 * navPlan.js 的 graduation 组由此投影；AdminGraduationLayout 不再维护固定 MENUS。
 */

/** @typedef {{ label: string, path: string, permissionKey?: string, entryType?: string, hidden?: boolean }} GradLeaf */
/** @typedef {{ key: string, label: string, path: string, permissionKey?: string, children: GradLeaf[] }} GradWorkspace */

/**
 * `workspace=...` 只区分公共工作台中“快捷入口”和“正式三级入口”的 UI 身份。
 * Vue Router 仍命中原 path，业务页忽略该参数，旧书签继续兼容；不产生第二套路由或业务状态。
 */

/**
 * 菜单“只给管理者看”的口径（只影响菜单显示，不影响路由权限；旧页面、旧链接照常可进）。
 * 普通老师的毕设权限全部来自业务关系自动带出的导师/评阅/评委/秘书身份，
 * 这些身份没有下列任何一项；学校/学院/专业/成绩管理员至少有一项。
 * 老师在菜单里只看到：我的毕设工作、题目库、过程指导台——其余事情都从“我的毕设工作”一键进入。
 */
export const GRADUATION_MANAGER_KEYS = [
  'graduationDesign.student.manage',
  'graduationDesign.batch.update',
  'graduationDesign.grade.calculate',
  'graduationDesign.grade.publish',
  'graduationDesign.defense.groupManage',
  'graduationDesign.review.assign',
  'graduationDesign.template.manage'
]
const MANAGER = GRADUATION_MANAGER_KEYS

/** 当前权限集是否属于毕设管理者（用于菜单与首页落点，不用于任何数据/写权限判断）。 */
export function isGraduationManager(patterns, match) {
  return Array.isArray(patterns) && GRADUATION_MANAGER_KEYS.some((key) => match(patterns, key))
}

/** @type {GradWorkspace[]} */
export const GRADUATION_WORKSPACES = [
  // 总览：接下来要做 + 首次使用的开工检查；老师只看到“我的毕设工作”
  {
    key: 'gd-workbench', label: '总览', path: '/admin/graduation',
    children: [
      { label: '毕设总览', path: '/admin/graduation', permissionKey: 'graduationDesign.dashboard.view', entryType: 'WORKBENCH', menuRequiresAny: MANAGER },
      { label: '开工检查', path: '/admin/graduation/setup', permissionKey: 'graduationDesign.student.manage', entryType: 'WORKBENCH', menuRequiresAny: MANAGER },
      { label: '我的毕设工作', path: '/admin/graduation/my-work', permissionKey: 'graduationDesign.dashboard.view', entryType: 'WORKBENCH' }
    ]
  },
  // ① 准备：批次时间、学生、导师
  {
    key: 'gd-batch-impl', label: '① 准备', path: '/admin/graduation/batches?panel=list',
    children: [
      { label: '批次与时间节点', path: '/admin/graduation/batches?panel=list', permissionKey: 'graduationDesign.batch.view', entryType: 'CONFIG_VIEW', menuRequiresAny: MANAGER },
      { label: '学生与进度', path: '/admin/graduation/students?panel=roster', permissionKey: 'graduationDesign.student.view', entryType: 'TASK_QUEUE', menuRequiresAny: MANAGER },
      { label: '导师与分配', path: '/admin/graduation/mentors?panel=list', permissionKey: 'graduationDesign.student.manage', entryType: 'TASK_QUEUE', menuRequiresAny: MANAGER },
      { label: '材料规则', path: '/admin/graduation/material-rules', permissionKey: 'graduationDesign.student.manage', entryType: 'CONFIG_VIEW', menuRequiresAny: MANAGER },
      { label: '分配冲突检测', path: '/admin/graduation/mentors/conflicts', permissionKey: 'graduationDesign.student.manage', entryType: 'TASK_QUEUE', menuRequiresAny: MANAGER }
    ]
  },
  // ② 选题：出题、审题、定题、换题
  {
    key: 'gd-topic-select', label: '② 选题', path: '/admin/graduation/topic-lib',
    children: [
      { label: '题目库', path: '/admin/graduation/topic-lib?panel=list', permissionKey: 'graduationDesign.topic.view', entryType: 'TASK_QUEUE' },
      { label: '选题轮次', path: '/admin/graduation/topic-rounds?panel=rounds', permissionKey: 'graduationDesign.topic.view', entryType: 'TASK_QUEUE', menuRequiresAny: MANAGER },
      { label: '题目调整申请', path: '/admin/graduation/topic-changes', permissionKey: 'graduationDesign.topic.view', entryType: 'TASK_QUEUE', menuRequiresAny: MANAGER }
    ]
  },
  // ③ 过程与中期：任务书、开题、指导记录、中期检查
  {
    key: 'gd-process', label: '③ 过程与中期', path: '/admin/graduation/proposals?workspace=proposal-final',
    children: [
      { label: '开题报告批阅', path: '/admin/graduation/proposals?workspace=proposal-final', permissionKey: 'graduationDesign.proposal.view', entryType: 'TASK_QUEUE', menuRequiresAny: MANAGER },
      { label: '中期检查（按导师）', path: '/admin/graduation/midterm-by-mentor', permissionKey: 'graduationDesign.midterm.review', entryType: 'TASK_QUEUE', menuRequiresAny: MANAGER },
      { label: '过程指导台', path: '/admin/graduation/process?panel=taskbook', permissionKey: 'graduationDesign.guidance.view', entryType: 'WORKBENCH' }
    ]
  },
  // ④ 论文与评阅：初稿/定稿、查重、评阅、材料
  {
    key: 'gd-proposal-final', label: '④ 论文与评阅', path: '/admin/graduation/finals?workspace=proposal-final',
    children: [
      { label: '论文提交与批阅', path: '/admin/graduation/finals?workspace=proposal-final', permissionKey: 'graduationDesign.final.view', entryType: 'TASK_QUEUE', menuRequiresAny: MANAGER },
      { label: '查重记录', path: '/admin/graduation/plagiarism-ledger', permissionKey: 'graduationDesign.plagiarism.view', entryType: 'TASK_QUEUE', menuRequiresAny: MANAGER },
      { label: '统一评阅中心', path: '/admin/graduation/review-tasks', permissionKey: 'graduationDesign.review.view', entryType: 'TASK_QUEUE', menuRequiresAny: MANAGER },
      { label: '毕设材料中心', path: '/admin/graduation/material-center', permissionKey: 'graduationDesign.student.view', entryType: 'WORKBENCH', menuRequiresAny: MANAGER }
    ]
  },
  // ⑤ 答辩：分组排期、评分、秘书确认
  {
    key: 'gd-defense', label: '⑤ 答辩', path: '/admin/graduation/defense',
    children: [
      { label: '答辩安排', path: '/admin/graduation/defense', permissionKey: 'graduationDesign.defense.view', entryType: 'TASK_QUEUE', menuRequiresAny: MANAGER },
      { label: '答辩评分', path: '/admin/graduation/defense-scoring?workspace=defense-grade', permissionKey: 'graduationDesign.defense.score', entryType: 'TASK_QUEUE', menuRequiresAny: MANAGER },
      { label: '答辩秘书确认', path: '/admin/graduation/defense-confirmation', permissionKey: 'graduationDesign.defense.scoreConfirm', entryType: 'TASK_QUEUE', menuRequiresAny: MANAGER }
    ]
  },
  // ⑥ 成绩与归档：算分复核发布、问题学生、归档
  {
    key: 'gd-risk-archive', label: '⑥ 成绩与归档', path: '/admin/graduation/grade-ledger',
    children: [
      { label: '导师评分', path: '/admin/graduation/advisor-score', permissionKey: 'graduationDesign.grade.advisorScore', entryType: 'TASK_QUEUE', menuRequiresAny: MANAGER },
      { label: '成绩台账', path: '/admin/graduation/grade-ledger', permissionKey: 'graduationDesign.grade.view', entryType: 'TASK_QUEUE', menuRequiresAny: MANAGER },
      { label: '问题预警', path: '/admin/graduation/risk-archive?panel=risk', permissionKey: 'graduationDesign.risk.view', entryType: 'TASK_QUEUE', menuRequiresAny: MANAGER },
      { label: '毕设材料归档', path: '/admin/graduation/risk-archive?panel=archive', permissionKey: 'graduationDesign.archive.view', entryType: 'TASK_QUEUE', menuRequiresAny: MANAGER }
    ]
  },
  // 更多：模板与旧的快捷入口（保留一个批次周期，确认没人用再清理）
  {
    key: 'gd-templates', label: '更多', path: '/admin/graduation/templates',
    children: [
      { label: '全部模板', path: '/admin/graduation/templates', permissionKey: 'graduationDesign.template.manage', entryType: 'CONFIG_VIEW', menuRequiresAny: MANAGER },
      { label: '待评阅开题', path: '/admin/graduation/proposals?tab=PENDING_REVIEW', permissionKey: 'graduationDesign.proposal.view', entryType: 'TASK_QUEUE', menuRequiresAny: MANAGER },
      { label: '待评阅成果', path: '/admin/graduation/finals?tab=PENDING_REVIEW', permissionKey: 'graduationDesign.final.view', entryType: 'TASK_QUEUE', menuRequiresAny: MANAGER },
      { label: '我的答辩评分', path: '/admin/graduation/defense-scoring', permissionKey: 'graduationDesign.defense.score', entryType: 'TASK_QUEUE', menuRequiresAny: MANAGER }
    ]
  }
]

export function buildGraduationNavMods(I, mod) {
  return GRADUATION_WORKSPACES.map((ws) => mod(
    ws.key, ws.label, ws.path,
    ws.children.map((c) => I(c.label, c.path, c.permissionKey, c.entryType,
      c.menuRequiresAny ? { menuRequiresAny: c.menuRequiresAny } : undefined)),
    ws.permissionKey
  ))
}
