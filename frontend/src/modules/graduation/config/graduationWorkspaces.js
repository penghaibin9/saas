/**
 * 毕业设计中心 · 8 个高频工作区（单一事实源）。
 * navPlan.js 的 graduation 组由此投影；AdminGraduationLayout 不再维护固定 MENUS。
 * 旧三级深链保留为叶子或隐藏叶子，刷新与旧书签继续可达。
 */

/** @typedef {{ label: string, path: string, permissionKey?: string, entryType?: string, hidden?: boolean }} GradLeaf */
/** @typedef {{ key: string, label: string, path: string, permissionKey?: string, children: GradLeaf[] }} GradWorkspace */

/** @type {GradWorkspace[]} */
export const GRADUATION_WORKSPACES = [
  {
    key: 'gd-workbench',
    label: '我的工作台',
    path: '/admin/graduation',
    children: [
      { label: '毕设总览', path: '/admin/graduation', permissionKey: 'graduationDesign.dashboard.view', entryType: 'WORKBENCH' },
      { label: '待评阅开题', path: '/admin/graduation/proposals?tab=PENDING_REVIEW', permissionKey: 'graduationDesign.proposal.view', entryType: 'TASK_QUEUE' },
      { label: '待评阅成果', path: '/admin/graduation/finals?tab=PENDING_REVIEW', permissionKey: 'graduationDesign.final.view', entryType: 'TASK_QUEUE' },
      { label: '我的答辩评分', path: '/admin/graduation/defense-scoring', permissionKey: 'graduationDesign.defense.score', entryType: 'TASK_QUEUE' },
      { label: '毕设统计报表', path: '/admin/graduation/stats-report', permissionKey: 'graduationDesign.stats.view', entryType: 'ANALYTICS_VIEW' },
      { label: '毕设操作日志', path: '/admin/graduation/audit-logs', permissionKey: 'graduationDesign.audit.view', entryType: 'CONFIG_VIEW' }
    ]
  },
  {
    key: 'gd-batch-impl',
    label: '批次与实施',
    path: '/admin/graduation/batches?panel=list',
    children: [
      { label: '批次列表', path: '/admin/graduation/batches?panel=list', permissionKey: 'graduationDesign.batch.view', entryType: 'CONFIG_VIEW' },
      { label: '阶段时间轴配置', path: '/admin/graduation/batches?panel=stages', permissionKey: 'graduationDesign.batch.update', entryType: 'CONFIG_VIEW' },
      { label: '规则配置', path: '/admin/graduation/batches?panel=rules', permissionKey: 'graduationDesign.batch.update', entryType: 'CONFIG_VIEW' },
      { label: '学生名单', path: '/admin/graduation/students?panel=roster', permissionKey: 'graduationDesign.student.view', entryType: 'TASK_QUEUE' },
      { label: '学生进度', path: '/admin/graduation/students?panel=progress', permissionKey: 'graduationDesign.student.view', entryType: 'TASK_QUEUE' },
      { label: '未选题学生', path: '/admin/graduation/students?panel=topic', permissionKey: 'graduationDesign.student.view', entryType: 'TASK_QUEUE' },
      { label: '毕设资格认定', path: '/admin/graduation/students?panel=eligibility', permissionKey: 'graduationDesign.student.manage', entryType: 'TASK_QUEUE' },
      { label: '导师名单', path: '/admin/graduation/mentors?panel=list', permissionKey: 'graduationDesign.mentor.manage', entryType: 'TASK_QUEUE' },
      { label: '学生分配', path: '/admin/graduation/mentors?panel=assign', permissionKey: 'graduationDesign.mentor.manage', entryType: 'TASK_QUEUE' },
      { label: '分配冲突检测', path: '/admin/graduation/mentors/conflicts', permissionKey: 'graduationDesign.mentor.manage', entryType: 'TASK_QUEUE' }
    ]
  },
  {
    key: 'gd-topic-select',
    label: '题目与选题',
    path: '/admin/graduation/topic-lib',
    children: [
      { label: '题目列表', path: '/admin/graduation/topic-lib?panel=list', permissionKey: 'graduationDesign.topic.lib', entryType: 'TASK_QUEUE' },
      { label: '待审核题目', path: '/admin/graduation/topic-lib?panel=pending', permissionKey: 'graduationDesign.topic.lib', entryType: 'TASK_QUEUE' },
      { label: '学生选题结果', path: '/admin/graduation/topics', permissionKey: 'graduationDesign.topic.manage', entryType: 'TASK_QUEUE' },
      { label: '选题轮次', path: '/admin/graduation/topic-rounds?panel=rounds', permissionKey: 'graduationDesign.topic.round', entryType: 'TASK_QUEUE' },
      { label: '学生志愿与确认', path: '/admin/graduation/topic-rounds?panel=choices', permissionKey: 'graduationDesign.topic.round', entryType: 'TASK_QUEUE' },
      { label: '匹配结果', path: '/admin/graduation/topic-rounds?panel=match', permissionKey: 'graduationDesign.topic.round', entryType: 'TASK_QUEUE' },
      { label: '容量冲突复核', path: '/admin/graduation/topic-rounds?panel=conflicts', permissionKey: 'graduationDesign.topic.round', entryType: 'TASK_QUEUE' },
      { label: '题目调整申请', path: '/admin/graduation/topic-changes', permissionKey: 'graduationDesign.topic.change', entryType: 'TASK_QUEUE' }
    ]
  },
  {
    key: 'gd-process',
    label: '过程指导',
    path: '/admin/graduation/process?panel=taskbook',
    permissionKey: 'graduationDesign.guidance.view',
    children: [
      { label: '规范流程', path: '/admin/graduation/process?panel=workflow', permissionKey: 'graduationDesign.guidance.view', entryType: 'CONFIG_VIEW' },
      { label: '任务书', path: '/admin/graduation/process?panel=taskbook', permissionKey: 'graduationDesign.guidance.view', entryType: 'TASK_QUEUE' },
      { label: '指导记录', path: '/admin/graduation/process?panel=guidance', permissionKey: 'graduationDesign.guidance.view', entryType: 'TASK_QUEUE' },
      { label: '指导计划', path: '/admin/graduation/process?panel=plan', permissionKey: 'graduationDesign.guidance.view', entryType: 'TASK_QUEUE' },
      { label: '导师评价', path: '/admin/graduation/process?panel=eval', permissionKey: 'graduationDesign.guidance.view', entryType: 'TASK_QUEUE' },
      { label: '中期检查', path: '/admin/graduation/process?panel=midterm', permissionKey: 'graduationDesign.guidance.view', entryType: 'TASK_QUEUE' }
    ]
  },
  {
    key: 'gd-proposal-final',
    label: '开题与成果',
    path: '/admin/graduation/proposals',
    children: [
      { label: '开题报告批阅', path: '/admin/graduation/proposals', permissionKey: 'graduationDesign.proposal.view', entryType: 'TASK_QUEUE' },
      { label: '成果提交与批阅', path: '/admin/graduation/finals', permissionKey: 'graduationDesign.final.view', entryType: 'TASK_QUEUE' },
      { label: '查重记录', path: '/admin/graduation/plagiarism-ledger', permissionKey: 'graduationDesign.plagiarism.view', entryType: 'TASK_QUEUE' },
      { label: '教师评阅', path: '/admin/graduation/review-tasks', permissionKey: 'graduationDesign.review.view', entryType: 'TASK_QUEUE' },
      { label: '成果互查整改', path: '/admin/graduation/more?panel=peer', permissionKey: 'graduationDesign.more.manage', entryType: 'TASK_QUEUE' }
    ]
  },
  {
    key: 'gd-defense',
    label: '答辩与成绩',
    path: '/admin/graduation/defense',
    children: [
      { label: '答辩安排', path: '/admin/graduation/defense', permissionKey: 'graduationDesign.defense.view', entryType: 'TASK_QUEUE' },
      { label: '答辩评分', path: '/admin/graduation/defense-scoring', permissionKey: 'graduationDesign.defense.score', entryType: 'TASK_QUEUE' },
      { label: '答辩秘书确认', path: '/admin/graduation/defense-confirmation', permissionKey: 'graduationDesign.defense.scoreConfirm', entryType: 'TASK_QUEUE' },
      { label: '成绩台账', path: '/admin/graduation/grade-ledger', permissionKey: 'graduationDesign.grade.view', entryType: 'TASK_QUEUE' },
      { label: '答辩专家库', path: '/admin/graduation/more?panel=experts', permissionKey: 'graduationDesign.more.manage', entryType: 'CONFIG_VIEW' },
      { label: '成绩更正申诉', path: '/admin/graduation/more?panel=appeals', permissionKey: 'graduationDesign.more.manage', entryType: 'TASK_QUEUE' }
    ]
  },
  {
    key: 'gd-risk-archive',
    label: '风险与归档',
    path: '/admin/graduation/risk-archive?panel=risk',
    children: [
      { label: '问题预警', path: '/admin/graduation/risk-archive?panel=risk', permissionKey: 'graduationDesign.riskArchive.manage', entryType: 'TASK_QUEUE' },
      { label: '毕设材料归档', path: '/admin/graduation/risk-archive?panel=archive', permissionKey: 'graduationDesign.riskArchive.manage', entryType: 'TASK_QUEUE' },
      { label: '毕设统计', path: '/admin/graduation/stats-report', permissionKey: 'graduationDesign.stats.view', entryType: 'ANALYTICS_VIEW' }
    ]
  },
  {
    key: 'gd-templates',
    label: '模板与设置',
    path: '/admin/graduation/templates',
    permissionKey: 'graduationDesign.template.manage',
    children: [
      { label: '材料模板', path: '/admin/graduation/templates?type=MATERIAL', permissionKey: 'graduationDesign.template.manage', entryType: 'CONFIG_VIEW' },
      { label: '任务书模板', path: '/admin/graduation/templates?type=TASKBOOK', permissionKey: 'graduationDesign.template.manage', entryType: 'CONFIG_VIEW' },
      { label: '开题模板', path: '/admin/graduation/templates?type=PROPOSAL', permissionKey: 'graduationDesign.template.manage', entryType: 'CONFIG_VIEW' },
      { label: '全部模板', path: '/admin/graduation/templates', permissionKey: 'graduationDesign.template.manage', entryType: 'CONFIG_VIEW' }
    ]
  }
]

/** 供 navPlan 投影：传入 I / mod 工厂，返回二级模块数组 */
export function buildGraduationNavMods(I, mod) {
  return GRADUATION_WORKSPACES.map((ws) =>
    mod(
      ws.key,
      ws.label,
      ws.path,
      ws.children.map((c) => I(c.label, c.path, c.permissionKey, c.entryType)),
      ws.permissionKey
    )
  )
}
