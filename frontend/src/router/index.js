import { createRouter, createWebHistory } from 'vue-router'
import { getToken, request } from '@/services/http/client'
import {
  canEnterRoute,
  ensurePermissionPatterns,
  GUARDED_MODULES,
  getPermissionPatterns,
  getRbacLoadFailed,
} from '@/security/permissionGate'
import {
  ensurePlatformAccessContext,
  isPlatformPrincipal,
  resolvePlatformHome,
} from '@/security/platformAccessGate'

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
import academicRoutes from '@/modules/academicAffairs/routes/academic.routes'
import { academicAffairsRoutes } from '@/modules/academicAffairs/academic-affairs.routes'
import internshipRoutes from '@/modules/internship/routes'
import graduationRoutes from '@/modules/graduation/routes'
import employmentRoutes from '@/modules/employment/employment.routes'
import dataCenterRoutes from '@/modules/dataCenter/dataCenter.routes'
import approvalRoutes from '@/modules/approval/approval.routes'
import systemRoutes from '@/modules/system/system.routes'
import platformRoutes from '@/modules/platform/platform.routes'
import studentAffairsRoutes from '@/modules/studentAffairs/studentAffairs.routes'
import messageCenterRoutes from '@/modules/messageCenter/message-center.routes'

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
  academicAffairsRoutes,
  internshipRoutes,
  graduationRoutes,
  employmentRoutes,
  dataCenterRoutes,
  approvalRoutes,
  systemRoutes,
  platformRoutes,
  studentAffairsRoutes,
  messageCenterRoutes
].flatMap((def) => (Array.isArray(def) ? def : [def]))

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      /* PORTAL-ROOT：主域名根路径 = 对外统一门户首页（公开，不需登录）。
         门户只做身份分流与产品导航，不实现认证、不调业务接口。
         教师/管理端工作台已迁至 /workbench，旧地址 / 不再直达工作台。 */
      path: '/',
      name: 'portal-home',
      component: () => import('../views/PortalHomeView.vue'),
      meta: { public: true, title: '高校学生全生命周期管理平台' }
    },
    {
      /* PC-10-MODULE-MENU-BRIDGE-P0-FIX：PC 管理端工作台（10 模块入口可见），
         菜单数据源 config/adminMenu.js；旧产品体验页保留在 /dev/preview 仅作存档。
         PORTAL-ROOT 后由 / 迁到 /workbench，登录后默认落点即此路由。 */
      path: '/workbench',
      name: 'admin-workbench',
      component: () => import('../views/AdminWorkbenchView.vue')
    },
    {
      /* /admin 裸路径兜底：重定向到管理端工作台，避免白屏 */
      path: '/admin',
      redirect: '/workbench'
    },
    {
      /* 材料补交与安全批次独立工作区：沿用学工布局，不扩张正式菜单树。 */
      path: '/admin/student-affairs/material-operations',
      component: () => import('@/modules/studentAffairs/views/AdminStudentAffairsLayout.vue'),
      meta: { moduleCode: 'STUDENT_AFFAIRS' },
      children: [
        {
          path: '',
          name: 'student-affairs-material-operations',
          component: () => import('@/modules/studentAffairs/views/MaterialOperationsView.vue'),
          meta: { moduleCode: 'STUDENT_AFFAIRS', title: '材料缺项与安全批次', requiresAuth: true, permissionKey: 'studentAffairs.dashboard.view' }
        }
      ]
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
      /* 登录页（账号密码走浏览器 HttpOnly refresh transport；业务认证真值仍在后端） */
      path: '/login',
      name: 'login',
      component: () => import('../views/LoginView.vue'),
      meta: { public: true, title: '登录' }
    },
    {
      /* SaaS 运营方独立入口：成功后仍由后端角色与前端路由守卫双重校验。 */
      path: '/platform-login',
      name: 'platform-login',
      component: () => import('../views/PlatformLoginView.vue'),
      meta: { public: true, title: 'SaaS 运营平台登录' }
    },
    {
      path: '/dev/preview',
      name: 'ui-preview',
      component: () => import('../views/UiPreview.vue'),
      // P6：生产环境封闭 /dev/*（组件预览、旧 UI 存档），避免学校环境直链打开开发页
      meta: { title: '旧产品体验页（存档）', requiresDev: true }
    },
    {
      path: '/dev/components',
      name: 'component-dev',
      component: () => import('../views/ComponentDevPreview.vue'),
      meta: { title: '组件开发预览', requiresDev: true }
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
 * P6-SECURITY / P-02：平台控制面 identity-first + capability-second 路由守卫。
 * accessToken 只驻留内存；F5 先恢复对应 PLATFORM browser session，再读取 /platform/context。
 * 前端只做纵深防御和导航收敛，后端 capability dependency 始终是最终安全边界。
 */
router.beforeEach(async (to, from, next) => {
  const isPublic = to.path === '/login' || to.meta?.public
  const isPlatform = to.path === '/admin/platform' || to.path.startsWith('/admin/platform/')

  if (!isPublic && !getToken()) {
    try {
      await request('/auth/me')
    } catch {
      // 没有/失效 cookie 时才由下一段统一跳登录。
    }
  }
  if (!isPublic && !getToken()) {
    next({
      path: isPlatform ? '/platform-login' : '/login',
      query: to.fullPath !== '/' ? { redirect: to.fullPath } : {}
    })
    return
  }

  if (to.meta?.requiresDev && import.meta.env.PROD) {
    next({ path: '/workbench', replace: true })
    return
  }

  if (to.path === '/platform-login' && getToken() && isPlatformPrincipal() && to.query?.forcePasswordChange !== '1') {
    const context = await ensurePlatformAccessContext({ force: true })
    next(context ? { path: resolvePlatformHome(context), replace: true } : { path: '/security/403', replace: true })
    return
  }

  if (isPlatform) {
    if (!isPlatformPrincipal()) {
      next({ path: '/platform-login', query: { redirect: to.fullPath, reason: 'platform-principal-required' } })
      return
    }
    const context = await ensurePlatformAccessContext()
    if (!context) {
      next({
        path: '/security/403',
        query: { from: to.fullPath, reason: 'platform-capability-service', message: getRbacLoadFailed() || '平台主管能力上下文加载失败' }
      })
      return
    }
    if (to.path === '/admin/platform') {
      next({ path: resolvePlatformHome(context), replace: true })
      return
    }
  }

  // PLATFORM principal 与学校租户身份严格分离；任何平台职责账号都不能误入学校工作台。
  if (!isPublic && !isPlatform && isPlatformPrincipal()) {
    const context = await ensurePlatformAccessContext()
    next({ path: context ? resolvePlatformHome(context) : '/security/403', replace: true })
    return
  }

  if (
    !isPlatform && GUARDED_MODULES.has(to.meta?.moduleCode) && getToken() &&
    !Array.isArray(getPermissionPatterns())
  ) {
    await ensurePermissionPatterns(request)
  }
  if (!canEnterRoute(to.meta)) {
    const svcErr = getRbacLoadFailed()
    next({
      path: '/security/403',
      query: {
        from: to.fullPath,
        ...(svcErr ? { reason: 'permission-service', message: svcErr } : {})
      }
    })
    return
  }
  next()
})

export default router