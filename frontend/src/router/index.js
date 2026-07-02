import { createRouter, createWebHistory } from 'vue-router'

/**
 * 路由表（对齐 docs/frontend/route-freeze.md）：
 * - `/` 与 `/dev/components` 为冻结路由，不改。
 * - `/security/*` 为 00-SEC 安全错误页（meta.public）。
 * - `/admin/workflow/*` 为 11 权限与流程中心。
 * - `/admin/student/*` 为 01 学生主档与身份中心（route-freeze/page-map 未定义 01 细分路由，按任务兜底路由接入）。
 *   meta 供 P8 统一路由守卫消费，本阶段不注册全局 beforeEach。
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
      path: '/security/401',
      name: 'security-401',
      component: () => import('../views/security/Error401View.vue'),
      meta: { public: true, title: '未登录' }
    },
    {
      path: '/security/403',
      name: 'security-403',
      component: () => import('../views/security/Error403View.vue'),
      meta: { public: true, title: '无权访问' }
    },
    {
      path: '/security/419',
      name: 'security-419',
      component: () => import('../views/security/Error419View.vue'),
      meta: { public: true, title: '会话超时' }
    },
    {
      path: '/security/500',
      name: 'security-500',
      component: () => import('../views/security/Error500View.vue'),
      meta: { public: true, title: '服务异常' }
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
    },
    {
      path: '/admin/student',
      component: () => import('../views/admin/student/AdminStudentLayout.vue'),
      meta: { moduleCode: 'STUDENT' },
      children: [
        {
          path: '',
          name: 'student-overview',
          component: () => import('../views/admin/student/StudentOverviewView.vue'),
          meta: { moduleCode: 'STUDENT', title: '学生主档', requiresAuth: true, permissionKey: 'student.profile.view' }
        },
        {
          path: 'list',
          name: 'student-list',
          component: () => import('../views/admin/student/StudentListView.vue'),
          meta: { moduleCode: 'STUDENT', title: '学生列表', requiresAuth: true, permissionKey: 'student.profile.view' }
        },
        {
          path: 'identity',
          name: 'student-identity',
          component: () => import('../views/admin/student/StudentIdentityView.vue'),
          meta: { moduleCode: 'STUDENT', title: '身份认证管理', requiresAuth: true, permissionKey: 'student.identity.view' }
        },
        {
          path: 'status',
          name: 'student-status',
          component: () => import('../views/admin/student/StudentStatusView.vue'),
          meta: { moduleCode: 'STUDENT', title: '学生状态管理', requiresAuth: true, permissionKey: 'student.status.update' }
        },
        {
          path: 'import-export',
          name: 'student-import-export',
          component: () => import('../views/admin/student/StudentImportExportView.vue'),
          meta: { moduleCode: 'STUDENT', title: '导入导出', requiresAuth: true, permissionKey: 'student.export' }
        },
        {
          path: ':studentId',
          name: 'student-detail',
          component: () => import('../views/admin/student/StudentDetailView.vue'),
          meta: { moduleCode: 'STUDENT', title: '学生详情', requiresAuth: true, permissionKey: 'student.profile.view' }
        }
      ]
    }
  ]
})

export default router
