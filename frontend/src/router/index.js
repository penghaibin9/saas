import { createRouter, createWebHistory } from 'vue-router'

/**
 * 路由表（对齐 docs/frontend/route-freeze.md）：
 * - `/` 与 `/dev/components` 为冻结路由，不改。
 * - `/admin/workflow/*` 为 11 权限与流程中心（全系统底座，先于业务模块落地）。
 *   meta.permissionKey / meta.moduleCode 供 P8 统一路由守卫（workflow.guards.checkRoutePermission）消费，
 *   本阶段不注册全局守卫。
 */
const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      name: 'ui-preview',
      component: () => import('../views/UiPreview.vue')
    },
    {
      path: '/dev/components',
      name: 'component-dev',
      component: () => import('../views/ComponentDevPreview.vue')
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
})

export default router
