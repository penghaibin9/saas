/**
 * 学生中心模块路由描述文件（PC-STUDENT-DATA-RUN）。
 * 说明：
 * 1. 本文件不接入全局 router（router/index.js 为冻结主文件，由集成阶段统一合并）。
 * 2. 全局 router 已存在 /admin/student 的 6 条冻结子路由（overview/list/identity/status/import-export/:studentId）。
 *    本任务新增 2 个页面（信息更正审核 corrections、风险标签 risk-tags），其完整建议见 studentRoutes。
 * 3. registerStudentRoutes(router)：模块内运行时兜底注册（仅补注全局缺失的 2 条新页面路由，
 *    静态路径优先级高于 :studentId 动态路由，不影响既有路由），由 AdminStudentLayout 调用；
 *    集成阶段将 studentRoutes 合入全局 router 后，该兜底自动跳过。
 */

/** 完整路由建议（供集成阶段合入全局 router 使用） */
export const studentRoutes = [
  {
    path: '/admin/student',
    component: () => import('@/views/admin/student/AdminStudentLayout.vue'),
    meta: { moduleCode: 'STUDENT' },
    children: [
      {
        path: '',
        name: 'student-overview',
        component: () => import('@/views/admin/student/StudentOverviewView.vue'),
        meta: { moduleCode: 'STUDENT', title: '学生中心看板', requiresAuth: true, permissionKey: 'student.profile.view' }
      },
      {
        path: 'list',
        name: 'student-list',
        component: () => import('@/views/admin/student/StudentListView.vue'),
        meta: { moduleCode: 'STUDENT', title: '学生主档', requiresAuth: true, permissionKey: 'student.profile.view' }
      },
      {
        /* 2026-07-10 第二批交互改造：新增主档独立编辑页（原列表抽屉表单字段多，改独立页） */
        path: 'list/new',
        name: 'student-create',
        component: () => import('@/views/admin/student/StudentEditView.vue'),
        meta: { moduleCode: 'STUDENT', title: '新增学生主档', requiresAuth: true, permissionKey: 'student.profile.view' }
      },
      {
        path: 'status',
        name: 'student-status',
        component: () => import('@/views/admin/student/StudentStatusView.vue'),
        meta: { moduleCode: 'STUDENT', title: '学籍状态管理', requiresAuth: true, permissionKey: 'student.status.update' }
      },
      {
        path: 'identity',
        name: 'student-identity',
        component: () => import('@/views/admin/student/StudentIdentityView.vue'),
        meta: { moduleCode: 'STUDENT', title: '身份核验记录', requiresAuth: true, permissionKey: 'student.identity.view' }
      },
      {
        path: 'corrections',
        name: 'student-corrections',
        component: () => import('@/views/admin/student/StudentCorrectionListView.vue'),
        meta: { moduleCode: 'STUDENT', title: '信息更正审核', requiresAuth: true, permissionKey: 'student.correction.review' }
      },
      {
        path: 'risk-tags',
        name: 'student-risk-tags',
        component: () => import('@/views/admin/student/StudentRiskTagListView.vue'),
        meta: { moduleCode: 'STUDENT', title: '学生风险标签', requiresAuth: true, permissionKey: 'student.risk.view' }
      },
      {
        path: 'import-export',
        name: 'student-import-export',
        component: () => import('@/views/admin/student/StudentImportExportView.vue'),
        meta: { moduleCode: 'STUDENT', title: '导入导出管理', requiresAuth: true, permissionKey: 'student.export' }
      },
      {
        /* 2026-07-10 第二批交互改造：编辑主档独立编辑页（?no=学号 供刷新定位；页面内按 editStudent 权限控制） */
        path: ':studentId/edit',
        name: 'student-edit',
        component: () => import('@/views/admin/student/StudentEditView.vue'),
        meta: { moduleCode: 'STUDENT', title: '编辑学生信息', requiresAuth: true, permissionKey: 'student.profile.view' }
      },
      {
        path: ':studentId',
        name: 'student-detail',
        component: () => import('@/views/admin/student/StudentDetailView.vue'),
        meta: { moduleCode: 'STUDENT', title: '学生360', requiresAuth: true, permissionKey: 'student.profile.view' }
      }
    ]
  }
]

/**
 * 运行时兜底注册（模块内自注册，不修改全局 router 文件）。
 * 仅当全局 router 缺少对应命名路由时补注；补注为顶层静态路由（外壳仍用 AdminStudentLayout），
 * vue-router 静态段优先级高于 /admin/student/:studentId，不会被详情路由劫持。
 */
export function registerStudentRoutes(router) {
  const fallback = [
    {
      path: '/admin/student/corrections',
      name: 'student-corrections',
      childPath: '',
      component: () => import('@/views/admin/student/StudentCorrectionListView.vue'),
      meta: { moduleCode: 'STUDENT', title: '信息更正审核', requiresAuth: true, permissionKey: 'student.correction.review' }
    },
    {
      path: '/admin/student/risk-tags',
      name: 'student-risk-tags',
      childPath: '',
      component: () => import('@/views/admin/student/StudentRiskTagListView.vue'),
      meta: { moduleCode: 'STUDENT', title: '学生风险标签', requiresAuth: true, permissionKey: 'student.risk.view' }
    }
  ]
  fallback.forEach((r) => {
    if (router.hasRoute(r.name)) return
    router.addRoute({
      path: r.path,
      component: () => import('@/views/admin/student/AdminStudentLayout.vue'),
      meta: { moduleCode: 'STUDENT' },
      children: [{ path: r.childPath, name: r.name, component: r.component, meta: r.meta }]
    })
  })
}
