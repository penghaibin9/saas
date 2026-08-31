/** Router-owned production workspaces that are not supplied by a module routes file. */
export const coreControlRoutes = [
  {
    path: '/workbench',
    name: 'admin-workbench',
    component: () => import('../views/AdminWorkbenchView.vue'),
    meta: { requiresAuth: true, permissionKey: 'workbench.home.view' }
  },
  {
    path: '/admin/help',
    name: 'admin-help',
    component: () => import('../views/admin/help/AdminHelpView.vue'),
    meta: { title: '帮助中心' }
  },
  {
    path: '/admin/workflow',
    component: () => import('../views/admin/workflow/AdminWorkflowLayout.vue'),
    meta: { moduleCode: 'WORKFLOW' },
    children: [
      {
        path: '',
        name: 'workflow-home',
        component: () => import('../views/admin/workflow/WorkflowHomeView.vue'),
        meta: { moduleCode: 'WORKFLOW', permissionKey: 'workflow.home.view', title: '权限与流程中心' }
      },
      {
        path: 'processes',
        name: 'workflow-processes',
        component: () => import('../views/admin/workflow/WorkflowProcessesView.vue'),
        meta: { moduleCode: 'WORKFLOW', permissionKey: 'workflow.process.view', title: '流程模板管理' }
      },
      {
        path: 'tasks',
        name: 'workflow-tasks',
        component: () => import('../views/admin/workflow/WorkflowTasksView.vue'),
        meta: { moduleCode: 'WORKFLOW', permissionKey: 'workflow.task.view', title: '审批任务中心' }
      },
      {
        path: 'roles',
        name: 'workflow-roles',
        component: () => import('../views/admin/workflow/WorkflowRolesView.vue'),
        meta: { moduleCode: 'WORKFLOW', permissionKey: 'workflow.role.view', title: '角色管理' }
      },
      {
        path: 'permissions',
        name: 'workflow-permissions',
        component: () => import('../views/admin/workflow/WorkflowPermissionsView.vue'),
        meta: { moduleCode: 'WORKFLOW', permissionKey: 'workflow.permission.view', title: '权限点管理' }
      }
    ]
  }
]
