/**
 * 毕业设计中心 · 8 个高频工作区（单一事实源）。
 * navPlan.js 的 graduation 组由此投影；AdminGraduationLayout 不再维护固定 MENUS。
 */

/** @typedef {{ label: string, path: string, permissionKey?: string, entryType?: string, hidden?: boolean }} GradLeaf */
/** @typedef {{ key: string, label: string, path: string, permissionKey?: string, children: GradLeaf[] }} GradWorkspace */

/** @type {GradWorkspace[]} */
export const GRADUATION_WORKSPACES = [
  {
    key: 'gd-workbench', label: '我的工作台', path: '/admin/graduation',
    children: [
      { label: '毕设总览', path: '/admin/graduation', permissionKey: 'graduationDesign.dashboard.view', entryType: 'WORKBENCH' },
      { label: '待评阅开题', path: '/admin/graduation/proposals?tab=PENDING_REVIEW', permissionKey: 'graduationDesign.proposal.view', entryType: 'TASK_QUEUE' },
      { label: '待评阅成果', path: '/admin/graduation/finals?tab=PENDING_REVIEW', permissionKey: 'graduationDesign.final.view', entryType: 'TASK_QUEUE' },
      { label: '我的答辩评分', path: '/admin/graduation/defense-scoring', permissionKey: 'graduationDesign.defense.score', entryType: 'TASK_QUEUE' }
    ]
  },
  {
    key: 'gd-batch-impl', label: '批次与实施', path: '/admin/graduation/batches?panel=list',
    children: [
      { label: '批次与规则', path: '/admin/graduation/batches?panel=list', permissionKey: 'graduationDesign.batch.view', entryType: 'CONFIG_VIEW' },
      { label: '学生与进度', path: '/admin/graduation/students?panel=roster', permissionKey: 'graduationDesign.student.view', entryType: 'TASK_QUEUE' },
      { label: '导师与分配', path: '/admin/graduation/mentors?panel=list', permissionKey: 'graduationDesign.student.manage', entryType: 'TASK_QUEUE' },
      { label: '分配冲突检测', path: '/admin/graduation/mentors/conflicts', permissionKey: 'graduationDesign.student.manage', entryType: 'TASK_QUEUE' }
    ]
  },
  {
    key: 'gd-topic-select', label: '题目与选题', path: '/admin/graduation/topic-lib',
    children: [
      { label: '题目库', path: '/admin/graduation/topic-lib?panel=list', permissionKey: 'graduationDesign.topic.view', entryType: 'TASK_QUEUE' },
      { label: '选题轮次', path: '/admin/graduation/topic-rounds?panel=rounds', permissionKey: 'graduationDesign.topic.view', entryType: 'TASK_QUEUE' },
      { label: '题目调整申请', path: '/admin/graduation/topic-changes', permissionKey: 'graduationDesign.topic.view', entryType: 'TASK_QUEUE' }
    ]
  },
  {
    key: 'gd-process', label: '过程指导', path: '/admin/graduation/process?panel=taskbook', permissionKey: 'graduationDesign.guidance.view',
    children: [
      { label: '过程指导台', path: '/admin/graduation/process?panel=taskbook', permissionKey: 'graduationDesign.guidance.view', entryType: 'WORKBENCH' }
    ]
  },
  {
    key: 'gd-proposal-final', label: '开题与成果', path: '/admin/graduation/proposals',
    children: [
      { label: '开题报告批阅', path: '/admin/graduation/proposals', permissionKey: 'graduationDesign.proposal.view', entryType: 'TASK_QUEUE' },
      { label: '成果提交与批阅', path: '/admin/graduation/finals', permissionKey: 'graduationDesign.final.view', entryType: 'TASK_QUEUE' },
      { label: '毕设材料中心', path: '/admin/graduation/material-center', permissionKey: 'graduationDesign.student.view', entryType: 'WORKBENCH' },
      { label: '查重记录', path: '/admin/graduation/plagiarism-ledger', permissionKey: 'graduationDesign.plagiarism.view', entryType: 'TASK_QUEUE' },
      { label: '统一评阅中心', path: '/admin/graduation/review-tasks', permissionKey: 'graduationDesign.review.view', entryType: 'TASK_QUEUE' }
    ]
  },
  {
    key: 'gd-defense', label: '答辩与成绩', path: '/admin/graduation/defense',
    children: [
      { label: '答辩安排', path: '/admin/graduation/defense', permissionKey: 'graduationDesign.defense.view', entryType: 'TASK_QUEUE' },
      { label: '答辩评分', path: '/admin/graduation/defense-scoring', permissionKey: 'graduationDesign.defense.score', entryType: 'TASK_QUEUE' },
      { label: '答辩秘书确认', path: '/admin/graduation/defense-confirmation', permissionKey: 'graduationDesign.defense.scoreConfirm', entryType: 'TASK_QUEUE' },
      { label: '成绩台账', path: '/admin/graduation/grade-ledger', permissionKey: 'graduationDesign.grade.view', entryType: 'TASK_QUEUE' }
    ]
  },
  {
    key: 'gd-risk-archive', label: '风险与归档', path: '/admin/graduation/risk-archive?panel=risk',
    children: [
      { label: '问题预警', path: '/admin/graduation/risk-archive?panel=risk', permissionKey: 'graduationDesign.risk.view', entryType: 'TASK_QUEUE' },
      { label: '毕设材料归档', path: '/admin/graduation/risk-archive?panel=archive', permissionKey: 'graduationDesign.archive.view', entryType: 'TASK_QUEUE' }
    ]
  },
  {
    key: 'gd-templates', label: '模板与设置', path: '/admin/graduation/templates', permissionKey: 'graduationDesign.template.manage',
    children: [
      { label: '全部模板', path: '/admin/graduation/templates', permissionKey: 'graduationDesign.template.manage', entryType: 'CONFIG_VIEW' }
    ]
  }
]

export function buildGraduationNavMods(I, mod) {
  return GRADUATION_WORKSPACES.map((ws) => mod(
    ws.key, ws.label, ws.path,
    ws.children.map((c) => I(c.label, c.path, c.permissionKey, c.entryType)),
    ws.permissionKey
  ))
}
