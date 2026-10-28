const pages = [
  ['', '系统管理概览', 'overview'], ['organizations', '组织架构', 'org'],
  ['staff', '教职工资料', 'staff'], ['students', '学生资料', 'student'],
  ['accounts', '用户账号', 'account'], ['roles', '角色与权限', 'role'], ['scopes', '管理范围与责任关系', 'scope'],
  ['brand', '学校资料与品牌', 'brand'], ['dictionary', '基础字典', 'dictionary'],
  ['leave-policy', '请假审批配置', 'leave-policy'], ['notification', '通知与服务设置', 'notification'],
  ['identity-import/:kind(students|staff)', '师生导入与账号开通', 'identity-import'],
  ['tasks', '导入导出任务', 'task'], ['migration', '历史数据迁移', 'migration'],
  ['integrations', '外部服务与对接', 'integration'], ['audit', '登录与操作审计', 'audit'],
  ['runtime', '运行与备份状态', 'runtime'], ['delivery', '版本与交付资料', 'delivery']
]
export default {
  path: '/admin/system', component: () => import('./SystemLayout.vue'),
  children: pages.map(([path, title, resource]) => ({ path, name: `system-${resource}`,
    component: () => import('./SystemWorkspace.vue'), meta: { title, moduleCode: 'SYSTEM', permissionKey: `system.${resource}.view`, resource }
  }))
}
