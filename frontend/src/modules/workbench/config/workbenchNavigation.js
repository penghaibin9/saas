// Existing page routes remain unchanged; only their navigation ownership moves.
export const WORKBENCH_PAGE_TABS = [
  { section: 'approval', label: '待办看板', path: '/admin/approval', permissionKey: 'approval.todo.view' },
  { section: 'approval', label: '我的待办', path: '/admin/approval/todos', permissionKey: 'approval.todo.view' },
  { section: 'approval', label: '已办 · 抄送', path: '/admin/approval/done', permissionKey: 'approval.done.view' },
  { section: 'approval', label: '退回记录', path: '/admin/approval/returned', permissionKey: 'approval.returned.view' },
  { section: 'approval', label: '审批模板', path: '/admin/approval/templates', permissionKey: 'approval.template.view' },
  { section: 'messages', label: '我的消息', path: '/admin/messages/inbox', permissionKey: 'workbench.message.view' },
  { section: 'messages', label: '通知发布', path: '/admin/messages/compose', permissionKey: 'workbench.message.publish' },
  { section: 'messages', label: '发布记录', path: '/admin/messages/outbox', permissionKey: 'workbench.message.publish' },
  { section: 'messages', label: '发送统计', path: '/admin/messages/statistics', permissionKey: 'workbench.message.statistics.view' },
  { section: 'messages', label: '消息模板', path: '/admin/messages/templates', permissionKey: 'workbench.message.template.manage' },
  { section: 'messages', label: '消息设置', path: '/admin/messages/settings', permissionKey: 'workbench.message.view' },
  { section: 'messages', label: '投递运维', path: '/admin/messages/ops', permissionKey: 'workbench.message.statistics.view' },
  { section: 'analytics', label: '生命周期总览', path: '/admin/data-center/lifecycle', permissionKey: 'dataCenter.lifecycle.view' },
  { section: 'analytics', label: '排行分析', path: '/admin/data-center/rankings', permissionKey: 'dataCenter.ranking.view' },
  { section: 'analytics', label: '风险预警', path: '/admin/data-center/risk', permissionKey: 'dataCenter.risk.view' },
  { section: 'analytics', label: '专题报表', path: '/admin/data-center/reports', permissionKey: 'dataCenter.report.view' }
]

export function workbenchSection(path) {
  if (/^\/admin\/approval(?:\/|$)/.test(path)) return 'approval'
  if (/^\/admin\/messages(?:\/|$)/.test(path)) return 'messages'
  if (/^\/admin\/data-center(?:\/|$)/.test(path)) return 'analytics'
  return ''
}
