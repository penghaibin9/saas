/**
 * 学工中心前端权限目录。
 * 这是导航、路由和按钮权限的可审计索引，不替代后端 require_permission 校验。
 */
const ROLE_TEMPLATES = {
  read: ['SCHOOL_ADMIN', 'STUDENT_AFFAIRS_ADMIN', 'COUNSELOR'],
  manage: ['SCHOOL_ADMIN', 'STUDENT_AFFAIRS_ADMIN'],
  counselorWrite: ['SCHOOL_ADMIN', 'STUDENT_AFFAIRS_ADMIN', 'COUNSELOR'],
  dormWrite: ['SCHOOL_ADMIN', 'STUDENT_AFFAIRS_ADMIN', 'COUNSELOR', 'DORM_MANAGER'],
  sensitive: ['SCHOOL_ADMIN', 'STUDENT_AFFAIRS_ADMIN', 'PSYCHOLOGY_TEACHER']
}

function permission(permissionCode, label, domain, riskLevel = 'LOW', allowedRolesTemplate = ROLE_TEMPLATES.read, routeUsages = [], apiUsages = []) {
  return { permissionCode, label, domain, riskLevel, allowedRolesTemplate, routeUsages, apiUsages }
}

export const STUDENT_AFFAIRS_PERMISSION_CATALOG = [
  permission('studentAffairs.dashboard.view', '学工看板', 'dashboard', 'LOW', ROLE_TEMPLATES.read, ['/admin/student-affairs/dashboard'], ['GET /student-affairs/dashboard']),
  permission('studentAffairs.stats.view', '学工统计', 'stats', 'MEDIUM', ROLE_TEMPLATES.read, ['/admin/student-affairs/stats', '/admin/student-affairs/stats/cockpit'], ['GET /student-affairs/stats/cockpit']),
  permission('studentAffairs.student.view', '学生主档查看', 'student', 'HIGH', ROLE_TEMPLATES.read, ['/admin/student/list', '/admin/student-affairs/profile'], ['GET /students/*']),
  permission('studentAffairs.class.view', '班级查看', 'class', 'MEDIUM', ROLE_TEMPLATES.read, ['/admin/campus-service/classes'], ['GET /student-affairs/classes']),
  permission('studentAffairs.class.create', '班级材料维护', 'class', 'MEDIUM', ROLE_TEMPLATES.manage, [], ['POST /student-affairs/classes/*/materials']),
  permission('studentAffairs.class.cadre.manage', '班干部维护', 'class', 'MEDIUM', ROLE_TEMPLATES.manage, [], ['POST|DELETE /student-affairs/classes/*/cadres']),
  permission('studentAffairs.counselorEval.view', '辅导员考评查看', 'counselorEval', 'MEDIUM', ROLE_TEMPLATES.read, ['/admin/student-affairs/counselor-eval'], ['GET /student-affairs/counselor-eval/*']),
  permission('studentAffairs.counselorEval.manage', '辅导员考评维护', 'counselorEval', 'MEDIUM', ROLE_TEMPLATES.manage, [], ['POST|PATCH /student-affairs/counselor-eval/*']),
  permission('studentAffairs.orientation.view', '数字迎新查看', 'orientation', 'MEDIUM', ROLE_TEMPLATES.read, ['/admin/orientation'], ['GET /orientation/*']),

  permission('studentAffairs.leave.view', '请假查看', 'leave', 'MEDIUM', ROLE_TEMPLATES.read, ['/admin/campus-service/leave', '/admin/campus-service/leave-stats'], ['GET /student-affairs/leaves']),
  permission('studentAffairs.leave.create', '请假发起', 'leave', 'MEDIUM', ROLE_TEMPLATES.read, [], ['POST /student-affairs/leaves']),
  permission('studentAffairs.leave.approve', '请假审批', 'leave', 'HIGH', ROLE_TEMPLATES.manage, [], ['POST /student-affairs/leaves/*/approve']),
  permission('studentAffairs.leave.export', '请假导出', 'leave', 'HIGH', ROLE_TEMPLATES.manage, [], ['GET /student-affairs/leaves/export']),
  permission('studentAffairs.leave.cancelLeaveConfirm', '销假确认', 'leave', 'MEDIUM', ROLE_TEMPLATES.counselorWrite, [], ['POST /student-affairs/leaves/*/cancel-confirm', 'POST /mobile/teacher/affairs/leaves/*/proxy-cancel']),
  permission('studentAffairs.leave.overdue.handle', '逾期请假处置', 'leave', 'HIGH', ROLE_TEMPLATES.counselorWrite, [], ['POST /student-affairs/leaves/*/overdue', 'POST /mobile/teacher/affairs/leaves/*/overdue-handle']),
  permission('studentAffairs.leave.extension.approve', '续假审批', 'leave', 'HIGH', ROLE_TEMPLATES.counselorWrite, [], ['POST /student-affairs/leaves/*/extension-approve']),

  permission('studentAffairs.dorm.view', '宿舍查看', 'dorm', 'MEDIUM', ROLE_TEMPLATES.read, ['/admin/student-affairs/dorm/stats'], ['GET /student-affairs/dorm/*']),
  permission('studentAffairs.dorm.resource.manage', '宿舍资源维护', 'dorm', 'MEDIUM', ROLE_TEMPLATES.manage, [], ['POST|PATCH /student-affairs/dorm/buildings']),
  permission('studentAffairs.dorm.inspection.manage', '宿舍检查维护', 'dorm', 'MEDIUM', ROLE_TEMPLATES.dormWrite, [], ['POST /student-affairs/dorm/checks']),
  permission('studentAffairs.dorm.allocation.manage', '宿舍入住与床位分配', 'dorm', 'HIGH', ROLE_TEMPLATES.dormWrite, [], ['POST /student-affairs/dorm/beds/*', 'POST /mobile/teacher/affairs/dorm/*']),
  permission('studentAffairs.dorm.transfer.approve', '调宿审批', 'dorm', 'HIGH', ROLE_TEMPLATES.dormWrite, [], ['POST /student-affairs/dorm/transfers/*/review', 'POST /mobile/teacher/affairs/dorm/transfers/*/review']),
  permission('studentAffairs.dorm.exception.handle', '宿舍异常处置', 'dorm', 'HIGH', ROLE_TEMPLATES.dormWrite, [], ['POST /student-affairs/dorm/exceptions/*/handle', 'POST /mobile/teacher/affairs/dorm/exceptions/*/handle']),
  permission('studentAffairs.risk.view', '风险预警查看', 'risk', 'HIGH', ROLE_TEMPLATES.read, ['/admin/student-affairs/risk', '/admin/student-affairs/mental/summary'], ['GET /student-affairs/risks']),
  permission('studentAffairs.risk.psyDetail.view', '心理敏感明细查看', 'mental', 'CRITICAL', ROLE_TEMPLATES.sensitive, ['/admin/student-affairs/mental'], ['GET /student-affairs/mental/*']),
  permission('studentAffairs.risk.assign', '风险指派', 'risk', 'HIGH', ROLE_TEMPLATES.manage, [], ['POST /student-affairs/risks/*/assign']),
  permission('studentAffairs.risk.handle', '风险处置', 'risk', 'HIGH', ROLE_TEMPLATES.manage, [], ['POST /student-affairs/risks/*/handle']),
  permission('studentAffairs.risk.transfer', '风险转交', 'risk', 'HIGH', ROLE_TEMPLATES.manage, [], ['POST /student-affairs/risks/*/transfer']),
  permission('studentAffairs.risk.escalate', '风险升级', 'risk', 'CRITICAL', ROLE_TEMPLATES.manage, [], ['POST /student-affairs/risks/*/escalate']),
  permission('studentAffairs.risk.close', '风险关闭', 'risk', 'HIGH', ROLE_TEMPLATES.manage, [], ['POST /student-affairs/risks/*/close']),
  permission('studentAffairs.risk.reopen', '风险重开', 'risk', 'HIGH', ROLE_TEMPLATES.manage, [], ['POST /student-affairs/risks/*/reopen']),
  permission('studentAffairs.mental.manage', '心理转介与危机维护', 'mental', 'CRITICAL', ROLE_TEMPLATES.sensitive, ['/admin/student-affairs/mental/referrals', '/admin/student-affairs/mental/crisis'], ['POST|PATCH /student-affairs/mental/*']),

  permission('studentAffairs.aid.view', '困难认定查看', 'aid', 'HIGH', ROLE_TEMPLATES.read, ['/admin/student-affairs/aid'], ['GET /student-affairs/aid/*']),
  permission('studentAffairs.aid.create', '困难认定申请', 'aid', 'HIGH', ROLE_TEMPLATES.read, [], ['POST /student-affairs/aid/applications']),
  permission('studentAffairs.aid.approve', '困难认定审批', 'aid', 'HIGH', ROLE_TEMPLATES.manage, [], ['POST /student-affairs/aid/*/review']),
  permission('studentAffairs.aid.counselorReview', '困难认定辅导员审核', 'aid', 'HIGH', ROLE_TEMPLATES.counselorWrite, [], ['POST /student-affairs/aid/*/counselor-review']),
  permission('studentAffairs.aid.adjust', '困难认定调整', 'aid', 'HIGH', ROLE_TEMPLATES.manage, [], ['POST /student-affairs/aid/*/adjust']),
  permission('studentAffairs.aid.batch.manage', '困难认定批次维护', 'aid', 'HIGH', ROLE_TEMPLATES.manage, [], ['POST /student-affairs/aid/batches']),
  permission('studentAffairs.funding.view', '资助查看', 'funding', 'HIGH', ROLE_TEMPLATES.read, ['/admin/student-affairs/funding'], ['GET /student-affairs/funding/*']),
  permission('studentAffairs.funding.create', '资助申请', 'funding', 'HIGH', ROLE_TEMPLATES.read, [], ['POST /student-affairs/funding/applications']),
  permission('studentAffairs.funding.approve', '资助审批', 'funding', 'HIGH', ROLE_TEMPLATES.manage, [], ['POST /student-affairs/funding/*/review']),
  permission('studentAffairs.funding.project.manage', '资助项目维护', 'funding', 'HIGH', ROLE_TEMPLATES.manage, [], ['POST|PATCH /student-affairs/funding/projects']),
  permission('studentAffairs.funding.publicity.manage', '资助公示维护', 'funding', 'HIGH', ROLE_TEMPLATES.manage, [], ['POST /student-affairs/funding/*/publicity']),
  permission('studentAffairs.funding.workstudy.manage', '勤工助学维护', 'funding', 'HIGH', ROLE_TEMPLATES.manage, ['/admin/student-affairs/funding/work-study'], ['POST|PATCH /student-affairs/funding/work-study/*']),
  permission('studentAffairs.funding.loan.manage', '助学贷款维护', 'funding', 'HIGH', ROLE_TEMPLATES.manage, ['/admin/student-affairs/funding/loans'], ['POST|PATCH /student-affairs/funding/loans/*']),
  permission('studentAffairs.funding.reduction.manage', '减免临补维护', 'funding', 'HIGH', ROLE_TEMPLATES.manage, ['/admin/student-affairs/funding/fee-reductions'], ['POST|PATCH /student-affairs/funding/fee-reductions/*']),
  permission('studentAffairs.funding.disburse.manage', '资助发放维护', 'funding', 'HIGH', ROLE_TEMPLATES.manage, [], ['POST /student-affairs/funding/disbursements/*']),

  permission('studentAffairs.discipline.view', '处分查看', 'discipline', 'HIGH', ROLE_TEMPLATES.read, ['/admin/student-affairs/discipline'], ['GET /student-affairs/discipline/*']),
  permission('studentAffairs.discipline.create', '处分登记', 'discipline', 'HIGH', ROLE_TEMPLATES.manage, [], ['POST /student-affairs/discipline/cases']),
  permission('studentAffairs.discipline.approve', '处分审批与生效', 'discipline', 'CRITICAL', ROLE_TEMPLATES.manage, [], ['POST /student-affairs/discipline/*/review', 'POST /mobile/teacher/affairs/discipline/*']),
  permission('studentAffairs.discipline.appeal.create', '处分申诉', 'discipline', 'HIGH', ROLE_TEMPLATES.read, [], ['POST /student-affairs/discipline/*/appeals']),
  permission('studentAffairs.discipline.appeal.review', '处分申诉复核', 'discipline', 'CRITICAL', ROLE_TEMPLATES.manage, [], ['POST /student-affairs/discipline/appeals/*/review', 'POST /mobile/teacher/affairs/appeals/DISCIPLINE_APPEAL/*/review']),
  permission('studentAffairs.talk.view', '谈心谈话查看', 'talk', 'HIGH', ROLE_TEMPLATES.read, ['/admin/student-affairs/talk'], ['GET /student-affairs/talk/*']),
  permission('studentAffairs.talk.create', '谈心谈话登记', 'talk', 'HIGH', ROLE_TEMPLATES.counselorWrite, [], ['POST /student-affairs/talk/*', 'POST /mobile/teacher/talk/*']),
  permission('studentAffairs.homeSchool.view', '家校联系查看', 'homeSchool', 'HIGH', ROLE_TEMPLATES.read, ['/admin/student-affairs/family'], ['GET /student-affairs/family/*']),
  permission('studentAffairs.homeSchool.record.create', '家校联系记录', 'homeSchool', 'HIGH', ROLE_TEMPLATES.counselorWrite, [], ['POST /student-affairs/family/*/contacts']),
  permission('studentAffairs.activity.view', '学生活动查看', 'activity', 'MEDIUM', ROLE_TEMPLATES.read, ['/admin/student-affairs/activity', '/admin/student-affairs/activity/second-class'], ['GET /student-affairs/activity/*']),
  permission('studentAffairs.activity.create', '学生活动创建', 'activity', 'MEDIUM', ROLE_TEMPLATES.manage, [], ['POST /student-affairs/activity/*']),
  permission('studentAffairs.activity.publish', '学生活动发布', 'activity', 'MEDIUM', ROLE_TEMPLATES.manage, [], ['POST /student-affairs/activity/*/publish']),
  permission('studentAffairs.activity.confirm', '学生活动确认', 'activity', 'MEDIUM', ROLE_TEMPLATES.manage, [], ['POST /student-affairs/activity/*/confirm']),
  permission('studentAffairs.club.view', '社团查看', 'club', 'MEDIUM', ROLE_TEMPLATES.read, ['/admin/student-affairs/activity/clubs'], ['GET /student-affairs/clubs']),
  permission('studentAffairs.club.manage', '社团维护', 'club', 'MEDIUM', ROLE_TEMPLATES.manage, [], ['POST|PATCH /student-affairs/clubs/*']),
  permission('studentAffairs.org.view', '学生组织查看', 'organization', 'MEDIUM', ROLE_TEMPLATES.read, ['/admin/student-affairs/activity/organizations'], ['GET /student-affairs/organizations']),
  permission('studentAffairs.org.manage', '学生组织维护', 'organization', 'MEDIUM', ROLE_TEMPLATES.manage, [], ['POST|PATCH /student-affairs/organizations/*']),
  permission('studentAffairs.league.view', '党团建设查看', 'partyLeague', 'MEDIUM', ROLE_TEMPLATES.read, ['/admin/student-affairs/activity/party-league'], ['GET /student-affairs/league/*']),
  permission('studentAffairs.league.manage', '党团建设维护', 'partyLeague', 'MEDIUM', ROLE_TEMPLATES.manage, [], ['POST|PATCH /student-affairs/league/*']),
  permission('studentAffairs.archive.view', '学工归档查看', 'archive', 'HIGH', ROLE_TEMPLATES.read, ['/admin/student-affairs/archive'], ['GET /student-affairs/archive/*']),
  permission('studentAffairs.archive.batch.manage', '学工归档批次维护', 'archive', 'HIGH', ROLE_TEMPLATES.manage, [], ['POST|PATCH /student-affairs/archive/*'])
]
