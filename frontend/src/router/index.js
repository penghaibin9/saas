import { createRouter, createWebHistory } from 'vue-router'
import { getToken, isPlatformSuperAdmin } from '@/services/http/client'

/**
 * 路由表（对齐 docs/frontend/route-freeze.md）：
 * - `/` 与 `/dev/components` 为冻结路由，不改。
 * - `/security/*` 为 00-SEC 安全错误页（meta.public）。
 * - `/admin/workflow/*` 为 11 权限与流程中心。
 * - `/admin/*` 10 个 PC 业务模块由 PC-10-MODULE-INTEGRATION-FINAL-RUN 统一接入，
 *   复用各模块 routes 文件，不重构 router 架构、不注册全局 beforeEach（守卫由 P8 消费 meta）。
 */

/* 10 个 PC 业务模块路由（复用模块内 routes 文件，最小接入） */
import { studentRoutes } from '@/modules/student/student.routes'
import orientationRoutes from '@/modules/orientation/orientation.routes'
import campusServiceRoutes from '@/modules/campusService/campusService.routes'
import academicRoutes from '@/modules/academic/academic.routes'
import internshipRoutes from '@/modules/internship/routes'
import graduationRoutes from '@/modules/graduation/routes'
import employmentRoutes from '@/modules/employment/employment.routes'
import dataCenterRoutes from '@/modules/dataCenter/dataCenter.routes'
import approvalRoutes from '@/modules/approval/approval.routes'
import systemRoutes from '@/modules/system/system.routes'
import platformRoutes from '@/modules/platform/platform.routes'
import studentAffairsRoutes from '@/modules/studentAffairs/studentAffairs.routes'

/**
 * 模块 routes 文件形态不一（部分为数组、部分为单个父路由对象），
 * 统一展平为一维顶层路由数组后并入总表。studentRoutes 内已含 8 条子路由
 * （含 corrections / risk-tags），AdminStudentLayout 的 registerStudentRoutes
 * 兜底注册以 router.hasRoute 为前置判断，正式接入后自动跳过，不会重复注册。
 */
const moduleRoutes = [
  studentRoutes,
  orientationRoutes,
  campusServiceRoutes,
  academicRoutes,
  internshipRoutes,
  graduationRoutes,
  employmentRoutes,
  dataCenterRoutes,
  approvalRoutes,
  systemRoutes,
  platformRoutes,
  studentAffairsRoutes
].flatMap((def) => (Array.isArray(def) ? def : [def]))

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      /* PC-10-MODULE-MENU-BRIDGE-P0-FIX：默认入口改为 PC 管理端工作台（10 模块入口可见），
         菜单数据源 config/adminMenu.js；旧产品体验页保留在 /dev/preview 仅作存档 */
      path: '/',
      name: 'admin-workbench',
      component: () => import('../views/AdminWorkbenchView.vue')
    },
    {
      /* /admin 裸路径兜底：重定向到管理端工作台，避免白屏 */
      path: '/admin',
      redirect: '/'
    },
    {
      /* 旧入口兼容（PC-NAV-6MODULE-REGROUP）：/admin/system/log（单数）→ 现行日志中心，避免旧书签 404 */
      path: '/admin/system/log',
      redirect: '/admin/system/logs'
    },
    {
      /* 旧就业企业页已下线：统一跳转岗位实习中心企业库 */
      path: '/admin/employment/companies',
      redirect: '/admin/internship/enterprises'
    },
    {
      /* §42 规划占位页：planned 菜单统一入口（只读展示 navPlan+施工图规划信息，无业务 API、无假按钮假数据） */
      path: '/admin/planned/:groupKey/:modKey/:leafIdx?',
      name: 'planned-placeholder',
      component: () => import('../views/admin/planned/PlannedPlaceholderView.vue'),
      meta: { title: '规划模块（待施工）' }
    },
    {
      /* 帮助中心（PC-HELP-CENTER）：功能帮助 + 业务流程图，由顶部「功能/帮助」搜索命中进入 */
      path: '/admin/help',
      name: 'admin-help',
      component: () => import('../views/admin/help/AdminHelpView.vue'),
      meta: { title: '帮助中心' }
    },
    {
      /* 登录页（账号密码走 /api/v1/auth/login；「进入演示环境」回工作台，不影响既有演示流程） */
      path: '/login',
      name: 'login',
      component: () => import('../views/LoginView.vue'),
      meta: { public: true, title: '登录' }
    },
    {
      path: '/dev/preview',
      name: 'ui-preview',
      component: () => import('../views/UiPreview.vue'),
      meta: { title: '旧产品体验页（存档）' }
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
    /* /admin/student/* 由 studentRoutes 提供（含 8 条子路由），并入 moduleRoutes 统一接入。 */
    ...moduleRoutes
  ]
})

/**
 * P6-SECURITY：平台总控台（老板运营端）路由守卫。
 * 仅拦截 /admin/platform/* —— 未以平台超级管理员身份登录者一律跳登录页。
 * 业务模块（学生/审批/迎新等对外演示页）与「进入演示环境」流程完全不受影响。
 * 说明：令牌为内存态，刷新后需重新登录；后端 /api/v1/platform/* 另有 403 强校验兜底。
 */
router.beforeEach((to, from, next) => {
  // P11：全站强制登录——未登录一律回登录页（账号密码=真实库 / 演示账号=演示租户）。
  // 登录页与安全错误页（meta.public）除外。
  const isPublic = to.path === '/login' || to.meta?.public
  if (!isPublic && !getToken()) {
    next({ path: '/login', query: to.fullPath !== '/' ? { redirect: to.fullPath } : {} })
    return
  }
  const isPlatform = to.path === '/admin/platform' || to.path.startsWith('/admin/platform/')
  if (isPlatform && !isPlatformSuperAdmin()) {
    next({ path: '/login', query: { redirect: to.fullPath, reason: 'platform-owner-only' } })
    return
  }
  next()
})

export default router
