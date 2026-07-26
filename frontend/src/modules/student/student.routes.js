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

/*
 * 权限码口径（学生主档统一整改 阶段 A）：
 * - 只使用后端真实注册的码。学籍维护动作已拆细：
 *   student.profile.create / update / restore / view（见 backend/app/core/permissions.py），
 *   manage 作为存量兼容码并列接受，但「恢复」不接受 manage 兜底。
 * - STUDENT 已纳入 permissionGate.GUARDED_MODULES，写不存在的码会对所有人 fail-closed。
 * - status / corrections / risk-tags 三页已接真实后端（教务学籍异动、教务信息更正、
 *   学工风险中枢），权限码已收紧为各自后端端点的真实集合。
 * - identity（身份核验）依赖学校未采购的第三方实名/人脸核验服务，后端无表无端点，
 *   真实环境返回空台账并说明，权限暂用查看口径 STU_VIEW_ANY。
 */

/** 查看类页面的权限口径：与 navPlan._STU_VIEW_ANY / 后端 list_students 三处一致。
 *  student.profile.view=完整字段；studentAffairs.student.view=最小字段，后端均放行。 */
const STU_VIEW_ANY = ['student.profile.view', 'studentAffairs.student.view']

/* 以下三页已接真实后端，权限口径与其后端端点保持同一集合：
 * - 学籍异动台账 → GET /academic-affairs/status-changes（require_any_permission 四选一）
 * - 信息更正审核 → GET /academic-affairs/roster/corrections（view 或 review）
 * - 风险标签     → GET /student-affairs/risk/records（studentAffairs.risk.view）
 * 前端与后端不一致会造成「菜单可见但接口 403」。 */
const SC_VIEW_ANY = [
  'academicAffairs.statusChange.view',
  'academicAffairs.statusChange.counselorReview',
  'academicAffairs.statusChange.collegeReview',
  'academicAffairs.statusChange.officeReview'
]
const CORRECTION_ANY = [
  'academicAffairs.roster.correction.view',
  'academicAffairs.roster.correction.review'
]

/* 学籍维护动作口径，与后端 api/v1/student.py 的 _P_CREATE/_P_UPDATE 同集合。
 * 恢复作废档案（student.profile.restore）不并列 manage——那是高危动作，
 * 只授予 学校/教务处/学院 管理员。 */
const STU_CREATE_ANY = ['student.profile.create', 'student.profile.manage']
const STU_UPDATE_ANY = ['student.profile.update', 'student.profile.manage']
/** 恢复作废档案的权限码（页面内按钮据此显示；后端 /students/restore 是最终边界）。 */
export const STU_RESTORE_PERM = 'student.profile.restore'

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
        meta: { moduleCode: 'STUDENT', title: '学生中心看板', requiresAuth: true, permissionAny: STU_VIEW_ANY }
      },
      {
        path: 'list',
        name: 'student-list',
        component: () => import('@/views/admin/student/StudentListView.vue'),
        meta: { moduleCode: 'STUDENT', title: '学生主档', requiresAuth: true, permissionAny: STU_VIEW_ANY }
      },
      {
        /* 学生补录（原「新增学生主档」）：单个学生建档归属教务学籍维护职责，
           不再是学工侧的独立建档口子；后端同样强制组织完整性。 */
        path: 'list/new',
        name: 'student-create',
        component: () => import('@/views/admin/student/StudentEditView.vue'),
        meta: { moduleCode: 'STUDENT', title: '学生补录', requiresAuth: true,
          permissionAny: STU_CREATE_ANY }
      },
      {
        path: 'status',
        name: 'student-status',
        component: () => import('@/views/admin/student/StudentStatusView.vue'),
        meta: {
          moduleCode: 'STUDENT', title: '学籍异动台账', requiresAuth: true,
          permissionAny: SC_VIEW_ANY
        }
      },
      {
        path: 'identity',
        name: 'student-identity',
        component: () => import('@/views/admin/student/StudentIdentityView.vue'),
        meta: { moduleCode: 'STUDENT', title: '身份核验记录', requiresAuth: true, permissionAny: STU_VIEW_ANY }
      },
      {
        path: 'corrections',
        name: 'student-corrections',
        component: () => import('@/views/admin/student/StudentCorrectionListView.vue'),
        meta: {
          moduleCode: 'STUDENT', title: '信息更正审核', requiresAuth: true,
          permissionAny: CORRECTION_ANY
        }
      },
      {
        path: 'risk-tags',
        name: 'student-risk-tags',
        component: () => import('@/views/admin/student/StudentRiskTagListView.vue'),
        meta: { moduleCode: 'STUDENT', title: '学生风险标签', requiresAuth: true,
          permissionKey: 'studentAffairs.risk.view' }
      },
      {
        /* 导入分流页：只解释与跳转，不上传不写库（学生主档只有两条正式写入路径） */
        path: 'import',
        name: 'student-import-gateway',
        component: () => import('@/views/admin/student/StudentImportGatewayView.vue'),
        meta: {
          moduleCode: 'STUDENT', title: '导入学生', requiresAuth: true,
          permissionAny: STU_VIEW_ANY
        }
      },
      {
        /* 路径保持不变以免旧链接 404；页面已收敛为纯导出 */
        path: 'import-export',
        name: 'student-import-export',
        component: () => import('@/views/admin/student/StudentImportExportView.vue'),
        meta: {
          moduleCode: 'STUDENT', title: '数据导出', requiresAuth: true,
          permissionKey: 'student.export'
        }
      },
      {
        /* 2026-07-10 第二批交互改造：编辑主档独立编辑页（?no=学号 供刷新定位；页面内按 editStudent 权限控制） */
        path: ':studentId/edit',
        name: 'student-edit',
        component: () => import('@/views/admin/student/StudentEditView.vue'),
        meta: { moduleCode: 'STUDENT', title: '编辑学生信息', requiresAuth: true,
          permissionAny: STU_UPDATE_ANY }
      },
      {
        path: ':studentId',
        name: 'student-detail',
        component: () => import('@/views/admin/student/StudentDetailView.vue'),
        meta: { moduleCode: 'STUDENT', title: '学生360', requiresAuth: true, permissionAny: STU_VIEW_ANY }
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
      meta: { moduleCode: 'STUDENT', title: '信息更正审核', requiresAuth: true, permissionAny: CORRECTION_ANY }
    },
    {
      path: '/admin/student/risk-tags',
      name: 'student-risk-tags',
      childPath: '',
      component: () => import('@/views/admin/student/StudentRiskTagListView.vue'),
      meta: { moduleCode: 'STUDENT', title: '学生风险标签', requiresAuth: true,
        permissionKey: 'studentAffairs.risk.view' }
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
