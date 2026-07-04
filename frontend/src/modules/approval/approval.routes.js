/**
 * 审批中心模块路由描述（/admin/approval，moduleCode: APPROVAL）。
 * 本文件为模块路由描述，待集成阶段接入全局 router，本任务不修改全局 router。
 * 集成方式：在 router/index.js 中 `...approvalRoutes` 展开接入；
 * 禁止在集成阶段之前被任何现有文件 import。
 */
export const approvalRoutes = [
  {
    path: '/admin/approval',
    component: () => import('@/views/admin/approval/AdminApprovalLayout.vue'),
    meta: { moduleCode: 'APPROVAL' },
    children: [
      {
        path: '',
        name: 'approval-dashboard',
        component: () => import('@/views/admin/approval/ApprovalDashboardView.vue'),
        meta: { moduleCode: 'APPROVAL', title: '待办看板', permissionKey: 'approval.todo.view' }
      },
      {
        path: 'todos',
        name: 'approval-todos',
        component: () => import('@/views/admin/approval/ApprovalTodoListView.vue'),
        meta: { moduleCode: 'APPROVAL', title: '我的待办', permissionKey: 'approval.todo.view' }
      },
      {
        path: 'todos/:taskId',
        name: 'approval-detail',
        component: () => import('@/views/admin/approval/ApprovalDetailView.vue'),
        meta: { moduleCode: 'APPROVAL', title: '审批详情', permissionKey: 'approval.task.handle' }
      },
      {
        path: 'done',
        name: 'approval-done',
        component: () => import('@/views/admin/approval/ApprovalDoneListView.vue'),
        meta: { moduleCode: 'APPROVAL', title: '已办与抄送', permissionKey: 'approval.done.view' }
      },
      {
        path: 'returned',
        name: 'approval-returned',
        component: () => import('@/views/admin/approval/ApprovalReturnedListView.vue'),
        meta: { moduleCode: 'APPROVAL', title: '退回记录', permissionKey: 'approval.returned.view' }
      },
      {
        path: 'templates',
        name: 'approval-templates',
        component: () => import('@/views/admin/approval/ApprovalTemplateListView.vue'),
        meta: { moduleCode: 'APPROVAL', title: '审批模板', permissionKey: 'approval.template.view' }
      }
    ]
  }
]

export default approvalRoutes
