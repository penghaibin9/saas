/**
 * 岗位实习中心模块路由（自包含）。已接入全局 router：见 `@/router/index.js`
 * （`import internshipRoutes` + `routes: [...internshipRoutes]`）。
 *
 * meta.title：页面标题（与 12 个冻结二级目录对齐）
 * meta.navModule：所属二级目录（面包屑 / 文档口径）
 */
import { INTERNSHIP_MODULE, INTERNSHIP_PAGE } from '@/modules/internship/constants/pageMeta'

const M = INTERNSHIP_MODULE
const P = INTERNSHIP_PAGE
const internshipRoutes = {
  path: '/admin/internship',
  component: () => import('@/modules/internship/views/AdminInternshipLayout.vue'),
  meta: { moduleCode: 'INTERNSHIP' },
  children: [
    {
      path: '',
      name: 'internship-dashboard',
      component: () => import('@/modules/internship/views/InternshipDashboardView.vue'),
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
      component: () => import('@/modules/internship/views/InternshipBatchListView.vue'),
      meta: { moduleCode: 'INTERNSHIP', navModule: M.BATCH_RULES, title: M.BATCH_RULES, requiresAuth: true, permissionKey: 'internship.batch.manage' }
    },
    {
      path: 'batches/new',
      name: 'internship-batch-new',
      component: () => import('@/modules/internship/views/BatchFormView.vue'),
      meta: { moduleCode: 'INTERNSHIP', navModule: M.BATCH_RULES, title: '新建实习批次', requiresAuth: true, permissionKey: 'internship.batch.manage' }
    },
    {
      path: 'batches/:id/edit',
      name: 'internship-batch-edit',
      component: () => import('@/modules/internship/views/BatchFormView.vue'),
      meta: { moduleCode: 'INTERNSHIP', navModule: M.BATCH_RULES, title: '编辑实习批次', requiresAuth: true, permissionKey: 'internship.batch.manage' }
    },
    {
      path: 'batches/:id',
      name: 'internship-batch-detail',
      component: () => import('@/modules/internship/views/BatchDetailView.vue'),
      meta: { moduleCode: 'INTERNSHIP', navModule: M.BATCH_RULES, title: '批次详情', requiresAuth: true, permissionKey: 'internship.batch.manage' }
    },
    {
      path: 'students',
      name: 'internship-students',
      component: () => import('@/modules/internship/views/InternshipStudentListView.vue'),
      meta: { moduleCode: 'INTERNSHIP', navModule: M.STUDENTS, title: M.STUDENTS, requiresAuth: true, permissionKey: 'internship.student.view' }
    },
    { path: 'assignment-logs', name: 'internship-assignment-logs', component: () => import('@/modules/internship/views/AssignmentLogView.vue'), meta: { moduleCode: 'INTERNSHIP', navModule: M.MATCH_ASSIGN, title: '分配日志', requiresAuth: true, permissionKey: 'internship.match.log.view' } },
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
      component: () => import('@/modules/internship/views/InternshipStudentDetailView.vue'),
      meta: { moduleCode: 'INTERNSHIP', navModule: M.STUDENTS, title: '实习学生详情', requiresAuth: true, permissionKey: 'internship.student.view' }
    },
    {
      path: 'attendance',
      name: 'internship-attendance',
      component: () => import('@/modules/internship/views/AttendanceView.vue'),
      meta: { moduleCode: 'INTERNSHIP', navModule: M.ATTENDANCE_LEAVE, title: M.ATTENDANCE_LEAVE, requiresAuth: true, permissionKey: 'internship.attendance.view' }
    },
    {
      path: 'attendance-leave',
      name: 'internship-attendance-leave',
      redirect: '/admin/internship/attendance'
    },
    {
      path: 'exceptions',
      name: 'internship-exceptions',
      component: () => import('@/modules/internship/views/AttendanceExceptionListView.vue'),
      meta: { moduleCode: 'INTERNSHIP', navModule: M.ATTENDANCE_LEAVE, title: P.ATTENDANCE_EXCEPTION, requiresAuth: true, permissionKey: 'internship.attendance.view' }
    },
    {
      path: 'exceptions/:id',
      name: 'internship-exception-detail',
      component: () => import('@/modules/internship/views/AttendanceExceptionDetailView.vue'),
      meta: { moduleCode: 'INTERNSHIP', navModule: M.ATTENDANCE_LEAVE, title: '打卡异常处理', requiresAuth: true, permissionKey: 'internship.attendance.view' }
    },
    {
      path: 'guidance',
      name: 'internship-guidance',
      component: () => import('@/modules/internship/views/GuidanceVisitView.vue'),
      meta: { moduleCode: 'INTERNSHIP', navModule: M.GUIDANCE_VISIT, title: M.GUIDANCE_VISIT, requiresAuth: true, permissionKey: 'internship.guidance.view' }
    },
    {
      path: 'guidance/new',
      name: 'internship-guidance-new',
      component: () => import('@/modules/internship/views/GuidanceRecordFormView.vue'),
      meta: { moduleCode: 'INTERNSHIP', navModule: M.GUIDANCE_VISIT, title: '新增指导/巡访记录', requiresAuth: true, permissionKey: 'internship.guidance.view' }
    },
    {
      path: 'guidance-plan',
      name: 'internship-guidance-plan',
      component: () => import('@/modules/internship/views/GuidancePlanView.vue'),
      meta: { moduleCode: 'INTERNSHIP', navModule: M.GUIDANCE_VISIT, title: '指导计划', requiresAuth: true, permissionKey: 'internship.guidance.view' }
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
      component: () => import('@/modules/internship/views/WeeklyReportListView.vue'),
      meta: { moduleCode: 'INTERNSHIP', navModule: M.WEEKLY_TASK, title: M.WEEKLY_TASK, requiresAuth: true, permissionKey: 'internship.report.review' }
    },
    {
      path: 'reports/:id',
      name: 'internship-report-detail',
      component: () => import('@/modules/internship/views/WeeklyReportDetailView.vue'),
      meta: { moduleCode: 'INTERNSHIP', navModule: M.WEEKLY_TASK, title: '周报批阅详情', requiresAuth: true, permissionKey: 'internship.report.review' }
    },
    {
      path: 'process-reports/:id',
      name: 'internship-process-report-detail',
      component: () => import('@/modules/internship/views/ProcessReportDetailView.vue'),
      meta: { moduleCode: 'INTERNSHIP', navModule: M.WEEKLY_TASK, title: '过程报告批阅', requiresAuth: true, permissionKey: 'internship.report.review' }
    },
    {
      path: 'changes',
      name: 'internship-changes',
      component: () => import('@/modules/internship/views/ChangeRequestListView.vue'),
      meta: { moduleCode: 'INTERNSHIP', navModule: M.MATCH_ASSIGN, title: P.CHANGE_LEDGER, requiresAuth: true, permissionKey: 'internship.student.manage' }
    },
    {
      path: 'plans',
      name: 'internship-plans',
      component: () => import('@/modules/internship/views/InternshipPlanView.vue'),
      meta: { moduleCode: 'INTERNSHIP', navModule: M.WEEKLY_TASK, title: '实习计划书', requiresAuth: true, permissionKey: 'internship.batch.manage' }
    },
    {
      path: 'insurance',
      name: 'internship-insurance',
      component: () => import('@/modules/internship/views/InsuranceVerifyView.vue'),
      meta: { moduleCode: 'INTERNSHIP', navModule: M.STUDENTS, title: '实习保险核验', requiresAuth: true, permissionKey: 'internship.insurance.view' }
    },
    {
      path: 'risks',
      name: 'internship-risks',
      component: () => import('@/modules/internship/views/InternshipRiskView.vue'),
      meta: { moduleCode: 'INTERNSHIP', navModule: M.RISK, title: P.RISK_BOARD, requiresAuth: true, permissionKey: 'internship.risk.view' }
    },
    {
      path: 'risk-disposal',
      name: 'internship-risk-disposal',
      component: () => import('@/modules/internship/views/RiskDisposalView.vue'),
      meta: { moduleCode: 'INTERNSHIP', navModule: M.RISK, title: M.RISK, requiresAuth: true, permissionKey: 'internship.risk.handle' }
    },
    {
      path: 'leaves',
      name: 'internship-leaves',
      component: () => import('@/modules/internship/views/LeaveReviewView.vue'),
      meta: { moduleCode: 'INTERNSHIP', navModule: M.ATTENDANCE_LEAVE, title: P.LEAVE_REVIEW, requiresAuth: true, permissionKey: 'internship.leave.review' }
    },
    {
      path: 'enterprises',
      name: 'internship-enterprises',
      component: () => import('@/modules/internship/views/InternshipEnterpriseListView.vue'),
      meta: { moduleCode: 'INTERNSHIP', navModule: M.ENTERPRISE_POSITION, title: P.ENTERPRISE_LIST, requiresAuth: true, permissionKey: 'internship.enterprise.view' }
    },
    {
      path: 'enterprises/new',
      name: 'internship-enterprise-new',
      component: () => import('@/modules/internship/views/EnterpriseFormView.vue'),
      meta: { moduleCode: 'INTERNSHIP', navModule: M.ENTERPRISE_POSITION, title: '新增企业', requiresAuth: true, permissionKey: 'internship.enterprise.view' }
    },
    {
      path: 'enterprises/:id/edit',
      name: 'internship-enterprise-edit',
      component: () => import('@/modules/internship/views/EnterpriseFormView.vue'),
      meta: { moduleCode: 'INTERNSHIP', navModule: M.ENTERPRISE_POSITION, title: '编辑企业', requiresAuth: true, permissionKey: 'internship.enterprise.view' }
    },
    {
      path: 'enterprises/:id',
      name: 'internship-enterprise-detail',
      component: () => import('@/modules/internship/views/InternshipEnterpriseDetailView.vue'),
      meta: { moduleCode: 'INTERNSHIP', navModule: M.ENTERPRISE_POSITION, title: '企业详情', requiresAuth: true, permissionKey: 'internship.enterprise.view' }
    },
    {
      path: 'positions',
      name: 'internship-positions',
      component: () => import('@/modules/internship/views/InternshipPositionListView.vue'),
      meta: { moduleCode: 'INTERNSHIP', navModule: M.ENTERPRISE_POSITION, title: P.POSITION_LIST, requiresAuth: true, permissionKey: 'internship.position.view' }
    },
    {
      path: 'positions/new',
      name: 'internship-position-new',
      component: () => import('@/modules/internship/views/PositionFormView.vue'),
      meta: { moduleCode: 'INTERNSHIP', navModule: M.ENTERPRISE_POSITION, title: '新增岗位', requiresAuth: true, permissionKey: 'internship.position.view' }
    },
    {
      path: 'positions/:id/edit',
      name: 'internship-position-edit',
      component: () => import('@/modules/internship/views/PositionFormView.vue'),
      meta: { moduleCode: 'INTERNSHIP', navModule: M.ENTERPRISE_POSITION, title: '编辑岗位', requiresAuth: true, permissionKey: 'internship.position.view' }
    },
    {
      path: 'positions/:id',
      name: 'internship-position-detail',
      component: () => import('@/modules/internship/views/InternshipPositionDetailView.vue'),
      meta: { moduleCode: 'INTERNSHIP', navModule: M.ENTERPRISE_POSITION, title: '岗位详情', requiresAuth: true, permissionKey: 'internship.position.view' }
    },
    {
      path: 'agreements',
      name: 'internship-agreements',
      component: () => import('@/modules/internship/views/AgreementView.vue'),
      meta: { moduleCode: 'INTERNSHIP', navModule: M.APPLY_AGREEMENT, title: P.AGREEMENT, requiresAuth: true, permissionKey: 'internship.agreement.view' }
    },
    {
      path: 'applications',
      name: 'internship-applications',
      component: () => import('@/modules/internship/views/InternshipApplicationReviewView.vue'),
      meta: { moduleCode: 'INTERNSHIP', navModule: M.APPLY_AGREEMENT, title: '实习申请审核', requiresAuth: true, permissionKey: 'internship.student.manage' }
    },
    {
      path: 'agreements/:id',
      name: 'internship-agreement-detail',
      component: () => import('@/modules/internship/views/AgreementDetailView.vue'),
      meta: { moduleCode: 'INTERNSHIP', navModule: M.APPLY_AGREEMENT, title: '三方协议档案', requiresAuth: true, permissionKey: 'internship.agreement.view' }
    },
    {
      path: 'enterprise-evals/new',
      name: 'internship-enterprise-eval-new',
      component: () => import('@/modules/internship/views/EnterpriseEvalFormView.vue'),
      meta: { moduleCode: 'INTERNSHIP', navModule: M.EVAL_SCORE, title: '录入企业评价', requiresAuth: true, permissionKey: 'internship.eval.enterprise.view' }
    },
    {
      path: 'enterprise-evals',
      name: 'internship-enterprise-evals',
      component: () => import('@/modules/internship/views/EnterpriseEvalView.vue'),
      meta: { moduleCode: 'INTERNSHIP', navModule: M.EVAL_SCORE, title: P.ENTERPRISE_EVAL, requiresAuth: true, permissionKey: 'internship.eval.enterprise.view' }
    },
    {
      path: 'student-evals',
      name: 'internship-student-evals',
      component: () => import('@/modules/internship/views/StudentEvalView.vue'),
      meta: { moduleCode: 'INTERNSHIP', navModule: M.EVAL_SCORE, title: P.STUDENT_EVAL, requiresAuth: true, permissionKey: 'internship.eval.self.view' }
    },
    {
      path: 'scores',
      name: 'internship-scores',
      component: () => import('@/modules/internship/views/ScoreView.vue'),
      meta: { moduleCode: 'INTERNSHIP', navModule: M.EVAL_SCORE, title: P.SCORE, requiresAuth: true, permissionKey: 'internship.score.view' }
    },
    {
      path: 'eval-score',
      name: 'internship-eval-score',
      redirect: '/admin/internship/scores'
    },
    {
      path: 'stats',
      name: 'internship-stats',
      component: () => import('@/modules/internship/views/StatsView.vue'),
      meta: { moduleCode: 'INTERNSHIP', navModule: M.EMPLOYMENT_ARCHIVE, title: '实习统计', requiresAuth: true, permissionKey: 'internship.stats.view' }
    },
    {
      path: 'archive',
      name: 'internship-archive',
      component: () => import('@/modules/internship/views/ArchiveView.vue'),
      meta: { moduleCode: 'INTERNSHIP', navModule: M.EMPLOYMENT_ARCHIVE, title: '实习归档', requiresAuth: true, permissionKey: 'internship.archive.view' }
    },
    {
      path: 'employment-archive-stats',
      name: 'internship-employment-archive-stats',
      redirect: '/admin/employment'
    },
    {
      path: 'agreement-templates/new',
      name: 'internship-agreement-template-new',
      component: () => import('@/modules/internship/views/AgreementTemplateFormView.vue'),
      meta: { moduleCode: 'INTERNSHIP', navModule: M.APPLY_AGREEMENT, title: '新建协议模板', requiresAuth: true, permissionKey: 'internship.agreement.template.manage' }
    },
    {
      path: 'agreement-templates/:id/edit',
      name: 'internship-agreement-template-edit',
      component: () => import('@/modules/internship/views/AgreementTemplateFormView.vue'),
      meta: { moduleCode: 'INTERNSHIP', navModule: M.APPLY_AGREEMENT, title: '编辑协议模板', requiresAuth: true, permissionKey: 'internship.agreement.template.manage' }
    },
    {
      path: 'agreement-templates/:id',
      name: 'internship-agreement-template-detail',
      component: () => import('@/modules/internship/views/AgreementTemplateDetailView.vue'),
      meta: { moduleCode: 'INTERNSHIP', navModule: M.APPLY_AGREEMENT, title: '协议模板详情', requiresAuth: true, permissionKey: 'internship.agreement.template.manage' }
    },
    {
      path: 'agreement-templates',
      name: 'internship-agreement-templates',
      component: () => import('@/modules/internship/views/InternshipAgreementTemplateListView.vue'),
      meta: { moduleCode: 'INTERNSHIP', navModule: M.APPLY_AGREEMENT, title: P.AGREEMENT_TEMPLATE, requiresAuth: true, permissionKey: 'internship.agreement.template.manage' }
    },
    {
      path: 'match',
      name: 'internship-match',
      component: () => import('@/modules/internship/views/InternshipMatchListView.vue'),
      meta: { moduleCode: 'INTERNSHIP', navModule: M.MATCH_ASSIGN, title: M.MATCH_ASSIGN, requiresAuth: true, permissionKey: 'internship.match.intention.view' }
    }
  ]
}

export default internshipRoutes
