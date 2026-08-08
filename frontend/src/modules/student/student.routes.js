/**
 * 学生中心模块路由描述文件（PC-STUDENT-DATA-RUN）。
 * 说明：
 * 1. 本文件不接入全局 router（router/index.js 为冻结主文件，由集成阶段统一合并）。
 * 2. 全局 router 已存在 /admin/student 的冻结子路由；模块内继续维护扩展页兼容注册。
 * 3. registerStudentRoutes(router) 仅补全全局缺失的静态扩展页。
 */

const STU_VIEW_ANY = ['student.profile.view', 'studentAffairs.student.view']
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
const STU_CREATE_ANY = ['student.profile.create', 'student.profile.manage']
const STU_UPDATE_ANY = ['student.profile.update', 'student.profile.manage']
export const STU_RESTORE_PERM = 'student.profile.restore'

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
        path: 'list/new',
        name: 'student-create',
        component: () => import('@/views/admin/student/StudentEditView.vue'),
        meta: { moduleCode: 'STUDENT', title: '学生补录', requiresAuth: true, permissionAny: STU_CREATE_ANY }
      },
      {
        path: 'status',
        name: 'student-status',
        component: () => import('@/views/admin/student/StudentStatusView.vue'),
        meta: { moduleCode: 'STUDENT', title: '学籍异动台账', requiresAuth: true, permissionAny: SC_VIEW_ANY }
      },
      {
        // Stage B / B5：正式身份核验入口先读取服务端 capability，明确区分
        // NOT_CONFIGURED / EMPTY / FORBIDDEN / ERROR；只有 READY 才进入连续复核工作区。
        path: 'identity',
        name: 'student-identity',
        component: () => import('@/views/admin/student/StudentIdentityCapabilityView.vue'),
        meta: { moduleCode: 'STUDENT', title: '身份核验记录', requiresAuth: true, permissionAny: STU_VIEW_ANY }
      },
      {
        path: 'corrections',
        name: 'student-corrections',
        component: () => import('@/views/admin/student/StudentCorrectionListView.vue'),
        meta: { moduleCode: 'STUDENT', title: '信息更正审核', requiresAuth: true, permissionAny: CORRECTION_ANY }
      },
      {
        path: 'risk-tags',
        name: 'student-risk-tags',
        component: () => import('@/views/admin/student/StudentRiskTagListView.vue'),
        meta: { moduleCode: 'STUDENT', title: '学生风险标签', requiresAuth: true, permissionKey: 'studentAffairs.risk.view' }
      },
      {
        path: 'import',
        name: 'student-import-gateway',
        component: () => import('@/views/admin/student/StudentImportGatewayView.vue'),
        meta: { moduleCode: 'STUDENT', title: '导入学生', requiresAuth: true, permissionAny: STU_VIEW_ANY }
      },
      {
        path: 'import-export',
        name: 'student-import-export',
        component: () => import('@/views/admin/student/StudentImportExportView.vue'),
        meta: { moduleCode: 'STUDENT', title: '数据导出', requiresAuth: true, permissionKey: 'student.export' }
      },
      {
        path: ':studentId/edit',
        name: 'student-edit',
        component: () => import('@/views/admin/student/StudentEditView.vue'),
        meta: { moduleCode: 'STUDENT', title: '编辑学生信息', requiresAuth: true, permissionAny: STU_UPDATE_ANY }
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
      meta: { moduleCode: 'STUDENT', title: '学生风险标签', requiresAuth: true, permissionKey: 'studentAffairs.risk.view' }
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
