/**
 * 岗位实习中心模块路由（自包含，未接入全局 router）。
 * 接入方式（由负责全局 router 的任务/人执行）：
 *   import internshipRoutes from '@/modules/internship/routes'
 *   routes: [...existing, internshipRoutes]
 *
 * meta.title：页面标题（与 12 个冻结二级目录对齐）
 * meta.navModule：所属二级目录（面包屑 / 文档口径）
 */
import { INTERNSHIP_MODULE, INTERNSHIP_PAGE } from '@/modules/internship/constants/pageMeta'

const M = INTERNSHIP_MODULE
const P = INTERNSHIP_PAGE
const internshipRoutes = {
  path: '/admin/internship',
  component: () => import('@/views/admin/internship/AdminInternshipLayout.vue'),
  meta: { moduleCode: 'INTERNSHIP' },
  children: [
    {
      path: '',
      name: 'internship-dashboard',
      component: () => import('@/views/admin/internship/InternshipDashboardView.vue'),
      meta: { moduleCode: 'INTERNSHIP', navModule: M.WORKBENCH, title: P.DASHBOARD, requiresAuth: true, permissionKey: 'internship.dashboard.view' }
    },
    {
      path: 'workbench',
      name: 'internship-workbench',
      redirect: '/admin/internship'
    },
    {
      path: 'batch-rules',
      name: 'internship-batch-rules',
      redirect: '/admin/internship/batches?panel=list'
    },
    {
      path: 'batches',
      name: 'internship-batches',
      component: () => import('@/views/admin/internship/InternshipBatchListView.vue'),
      meta: { moduleCode: 'INTERNSHIP', navModule: M.BATCH_RULES, title: M.BATCH_RULES, requiresAuth: true, permissionKey: 'internship.batch.manage' }
    },
    {
      path: 'students',
      name: 'internship-students',
      component: () => import('@/views/admin/internship/InternshipStudentListView.vue'),
      meta: { moduleCode: 'INTERNSHIP', navModule: M.STUDENTS, title: M.STUDENTS, requiresAuth: true, permissionKey: 'internship.student.view' }
    },
    {
      path: 'enterprise-position',
      name: 'internship-enterprise-position',
      redirect: '/admin/internship/enterprises?panel=list'
    },
    {
      path: 'match-assign',
      name: 'internship-match-assign',
      redirect: '/admin/internship/match?panel=intention'
    },
    {
      path: 'apply-agreement',
      name: 'internship-apply-agreement',
      redirect: '/admin/internship/agreements'
    },
    {
      path: 'students/:id',
      name: 'internship-student-detail',
      component: () => import('@/views/admin/internship/InternshipStudentDetailView.vue'),
      meta: { moduleCode: 'INTERNSHIP', navModule: M.STUDENTS, title: '实习学生详情', requiresAuth: true, permissionKey: 'internship.student.view' }
    },
    {
      path: 'attendance',
      name: 'internship-attendance',
      component: () => import('@/views/admin/internship/AttendanceView.vue'),
      meta: { moduleCode: 'INTERNSHIP', navModule: M.ATTENDANCE_LEAVE, title: M.ATTENDANCE_LEAVE, requiresAuth: true, permissionKey: 'internship.checkin.handle' }
    },
    {
      path: 'attendance-leave',
      name: 'internship-attendance-leave',
      redirect: '/admin/internship/attendance'
    },
    {
      path: 'exceptions',
      name: 'internship-exceptions',
      component: () => import('@/views/admin/internship/AttendanceExceptionListView.vue'),
      meta: { moduleCode: 'INTERNSHIP', navModule: M.ATTENDANCE_LEAVE, title: P.ATTENDANCE_EXCEPTION, requiresAuth: true, permissionKey: 'internship.checkin.handle' }
    },
    {
      path: 'exceptions/:id',
      name: 'internship-exception-detail',
      component: () => import('@/views/admin/internship/AttendanceExceptionDetailView.vue'),
      meta: { moduleCode: 'INTERNSHIP', navModule: M.ATTENDANCE_LEAVE, title: '打卡异常处理', requiresAuth: true, permissionKey: 'internship.checkin.handle' }
    },
    {
      path: 'guidance',
      name: 'internship-guidance',
      component: () => import('@/views/admin/internship/GuidanceVisitView.vue'),
      meta: { moduleCode: 'INTERNSHIP', navModule: M.GUIDANCE_VISIT, title: M.GUIDANCE_VISIT, requiresAuth: true, permissionKey: 'internship.guidance.view' }
    },
    {
      path: 'weekly-task',
      name: 'internship-weekly-task',
      redirect: '/admin/internship/reports'
    },
    {
      path: 'guidance-visit',
      name: 'internship-guidance-visit',
      redirect: '/admin/internship/guidance'
    },
    {
      path: 'reports',
      name: 'internship-reports',
      component: () => import('@/views/admin/internship/WeeklyReportListView.vue'),
      meta: { moduleCode: 'INTERNSHIP', navModule: M.WEEKLY_TASK, title: M.WEEKLY_TASK, requiresAuth: true, permissionKey: 'internship.report.review' }
    },
    {
      path: 'reports/:id',
      name: 'internship-report-detail',
      component: () => import('@/views/admin/internship/WeeklyReportDetailView.vue'),
      meta: { moduleCode: 'INTERNSHIP', navModule: M.WEEKLY_TASK, title: '周报批阅详情', requiresAuth: true, permissionKey: 'internship.report.review' }
    },
    {
      path: 'risks',
      name: 'internship-risks',
      component: () => import('@/views/admin/internship/InternshipRiskView.vue'),
      meta: { moduleCode: 'INTERNSHIP', navModule: M.RISK, title: P.RISK_BOARD, requiresAuth: true, permissionKey: 'internship.risk.view' }
    },
    {
      path: 'risk-disposal',
      name: 'internship-risk-disposal',
      component: () => import('@/views/admin/internship/RiskDisposalView.vue'),
      meta: { moduleCode: 'INTERNSHIP', navModule: M.RISK, title: M.RISK, requiresAuth: true, permissionKey: 'internship.risk.handle' }
    },
    {
      path: 'leaves',
      name: 'internship-leaves',
      component: () => import('@/views/admin/internship/LeaveReviewView.vue'),
      meta: { moduleCode: 'INTERNSHIP', navModule: M.ATTENDANCE_LEAVE, title: P.LEAVE_REVIEW, requiresAuth: true, permissionKey: 'internship.leave.review' }
    },
    {
      path: 'enterprises',
      name: 'internship-enterprises',
      component: () => import('@/views/admin/internship/InternshipEnterpriseListView.vue'),
      meta: { moduleCode: 'INTERNSHIP', navModule: M.ENTERPRISE_POSITION, title: P.ENTERPRISE_LIST, requiresAuth: true, permissionKey: 'internship.enterprise.view' }
    },
    {
      path: 'enterprises/:id',
      name: 'internship-enterprise-detail',
      component: () => import('@/views/admin/internship/InternshipEnterpriseDetailView.vue'),
      meta: { moduleCode: 'INTERNSHIP', navModule: M.ENTERPRISE_POSITION, title: '企业详情', requiresAuth: true, permissionKey: 'internship.enterprise.view' }
    },
    {
      path: 'positions',
      name: 'internship-positions',
      component: () => import('@/views/admin/internship/InternshipPositionListView.vue'),
      meta: { moduleCode: 'INTERNSHIP', navModule: M.ENTERPRISE_POSITION, title: P.POSITION_LIST, requiresAuth: true, permissionKey: 'internship.position.view' }
    },
    {
      path: 'positions/:id',
      name: 'internship-position-detail',
      component: () => import('@/views/admin/internship/InternshipPositionDetailView.vue'),
      meta: { moduleCode: 'INTERNSHIP', navModule: M.ENTERPRISE_POSITION, title: '岗位详情', requiresAuth: true, permissionKey: 'internship.position.view' }
    },
    {
      path: 'agreements',
      name: 'internship-agreements',
      component: () => import('@/views/admin/internship/AgreementView.vue'),
      meta: { moduleCode: 'INTERNSHIP', navModule: M.APPLY_AGREEMENT, title: P.AGREEMENT, requiresAuth: true, permissionKey: 'internship.agreement.view' }
    },
    {
      path: 'enterprise-evals',
      name: 'internship-enterprise-evals',
      component: () => import('@/views/admin/internship/EnterpriseEvalView.vue'),
      meta: { moduleCode: 'INTERNSHIP', navModule: M.EVAL_SCORE, title: P.ENTERPRISE_EVAL, requiresAuth: true, permissionKey: 'internship.enterpriseEval.view' }
    },
    {
      path: 'student-evals',
      name: 'internship-student-evals',
      component: () => import('@/views/admin/internship/StudentEvalView.vue'),
      meta: { moduleCode: 'INTERNSHIP', navModule: M.EVAL_SCORE, title: P.STUDENT_EVAL, requiresAuth: true, permissionKey: 'internship.studentEval.view' }
    },
    {
      path: 'scores',
      name: 'internship-scores',
      component: () => import('@/views/admin/internship/ScoreView.vue'),
      meta: { moduleCode: 'INTERNSHIP', navModule: M.EVAL_SCORE, title: P.SCORE, requiresAuth: true, permissionKey: 'internship.score.view' }
    },
    {
      path: 'eval-score',
      name: 'internship-eval-score',
      redirect: '/admin/internship/scores'
    },
    {
      path: 'employment-archive-stats',
      name: 'internship-employment-archive-stats',
      redirect: '/admin/employment'
    },
    {
      path: 'agreement-templates',
      name: 'internship-agreement-templates',
      component: () => import('@/views/admin/internship/InternshipAgreementTemplateListView.vue'),
      meta: { moduleCode: 'INTERNSHIP', navModule: M.APPLY_AGREEMENT, title: P.AGREEMENT_TEMPLATE, requiresAuth: true, permissionKey: 'internship.agreementTemplate.view' }
    },
    {
      path: 'match',
      name: 'internship-match',
      component: () => import('@/views/admin/internship/InternshipMatchListView.vue'),
      meta: { moduleCode: 'INTERNSHIP', navModule: M.MATCH_ASSIGN, title: M.MATCH_ASSIGN, requiresAuth: true, permissionKey: 'internship.match.view' }
    }
  ]
}

export default internshipRoutes
