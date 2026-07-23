/** 教师端数据服务：真实后端优先（主链：学生/审批/待办/消息/学生360），失败自动回退 mock。 */
import { mockRequest, realFirst, realFirstStrict } from './request'
import * as real from './realApi'
import * as M from '@/mock'

export const teacherApi = {
  getWorkbench: (roleKey) =>
    realFirstStrict('teacher.workbench',
      () => real.enrichTeacherWorkbench(M.workbenchByRole[roleKey] || M.workbenchByRole.counselor),
      () => mockRequest(M.workbenchByRole[roleKey] || M.workbenchByRole.counselor)),
  // 待办：mobile 范围接口（替代 PC /todos）
  getTodos: () =>
    realFirst('teacher.todos',
      () => real.teacherTodosReal(),
      () => mockRequest({ filters: M.todoFilters, list: M.teacherTodos })),
  // 审批列表：mobile 范围接口（替代通用 /approvals 全量）
  getApprovals: () =>
    realFirst('teacher.approvals',
      () => real.teacherApprovalsReal(M.approvals),
      () => mockRequest(M.approvals)),
  /** 审批操作沿用真实审批接口（数字 id）；已确认仅处理本人可见任务 */
  actApproval: (id, type, reason) => real.actApproval(id, type, reason),
  /** 教师写操作：真实后端（范围校验+审计），业务错误透出，不回退 mock */
  reviewWeekly: (id, action, comment) => real.reviewWeeklyReal(id, action, comment),
  reviewProposal: (id, action, comment) => real.reviewProposalReal(id, action, comment),
  handleWarning: (id, action, note) => real.handleWarningReal(id, action, note),
  handleCheckin: (id, action, comment) => real.handleCheckinReal(id, action, comment),
  remindWeekly: (id) => real.remindWeeklyReal(id),
  createFollowup: (body) => real.createFollowupReal(body),
  // 13A 学工待办卡 + 13B 教师课表（P7，真实优先无 mock 兜底）
  getAffairs: () => real.teacherAffairs(),
  getMySchedule: () => real.acadTeacherScheduleMy(),
  // 风险学生：后端范围过滤（不再调用 PC /students?pageSize=100）
  getRiskStudents: () =>
    realFirst('teacher.risk',
      () => real.teacherRiskStudents(),
      () => mockRequest(M.students.filter((s) => s.risk === 'HIGH' || s.risk === 'MEDIUM'))),
  // getStudents 已弃用：不再打 PC 全列表；保留纯 mock 兜底以防旧引用（页面已不使用）
  getStudents: () => mockRequest(M.students),
  // 学生360：mobile 范围接口 + 权限校验（403/404 由业务错抛出，不兜底成功）
  getStudent360: (id) =>
    realFirstStrict('teacher.student360',
      () => real.teacherStudent360(id),
      () => mockRequest(M.student360[id] || null)),
  // 我的班级 / 我的学生（真实接口，无 mock 兜底）
  getMyClasses: () => real.teacherMyClasses(),
  getMyStudents: (classId) => real.teacherMyStudents(classId),
  // 谈心谈话（真实接口，无 mock 兜底）
  getTalkList: (params) => real.teacherTalkList(params),
  getTalkDetail: (talkId) => real.teacherTalkDetail(talkId),
  createTalk: (body) => real.teacherTalkCreate(body),
  recordTalk: (talkId, body) => real.teacherTalkRecord(talkId, body),
  talkFollowUp: (talkId, action, content) => real.teacherTalkFollowUp(talkId, action, content),
  // 心理关注（真实接口，无 mock 兜底，严格保留遮蔽+授权原因红线）
  getMentalList: (level) => real.teacherMentalList(level),
  getMentalDetail: (refId, reason) => real.teacherMentalDetail(refId, reason),
  createMentalReferral: (body) => real.teacherMentalCreate(body),
  followMentalReferral: (refId, content) => real.teacherMentalFollow(refId, content),
  escalateMentalReferral: (refId, content) => real.teacherMentalEscalate(refId, content),
  closeMentalReferral: (refId, conclusion) => real.teacherMentalClose(refId, conclusion),
  // 消息通知设置（真实接口，无 mock 兜底）
  getNotifyPreferences: () => real.teacherNotifyPreferences(),
  setNotifyPreference: (key, enabled) => real.teacherNotifySetPreference(key, enabled),
  publishNotice: (body) => real.teacherNotifyPublish(body),
  getDashboard: () => real.teacherDashboard(),
  // 实习批阅：mobile 范围真实数据
  getWeeklyReports: () =>
    realFirst('teacher.internship',
      () => real.teacherInternshipReal({ reports: M.weeklyReports, abnormal: M.abnormalCheckins }),
      () => mockRequest({ reports: M.weeklyReports, abnormal: M.abnormalCheckins })),
  // 单份周报正文（列表只回摘要，正文按需拉取，范围安全）；业务错误透出，不 mock 兜底
  getWeeklyDetail: (id) => real.teacherWeeklyDetail(id),
  // 毕设指导：mobile 范围真实数据
  getGdStudents: () =>
    realFirst('teacher.graduation',
      () => real.teacherGraduationReal({ list: M.gdStudents, detail: M.gdReviewDetail }),
      () => mockRequest({ list: M.gdStudents, detail: M.gdReviewDetail })),
  // 毕设指导：移动端快速新增指导记录（真实接口，不 mock 冒充成功）
  createGuidance: (gdStudentId, body) => real.teacherGraduationGuidanceCreate(gdStudentId, body),
  // 毕设开题：批阅前真实查看开题详情（背景/方案/成果+历史版本，范围校验）
  getGraduationProposalDetail: (id) => real.gdTeacherProposalDetail(id),
  // 毕设成果：详情 + 批阅（查重超标不可通过）
  getGraduationFinalDetail: (id) => real.gdTeacherFinalDetail(id),
  reviewFinal: (id, action, comment) => real.gdTeacherFinalReview(id, action, comment),
  // 毕设中期检查：队列 / 详情 / 结论 / 复核整改
  getGraduationMidtermQueue: () => real.gdTeacherMidtermQueue(),
  getGraduationMidtermDetail: (id) => real.gdTeacherMidtermDetail(id),
  midtermCheck: (id, conclusion, comment, deadline) => real.gdTeacherMidtermCheck(id, conclusion, comment, deadline),
  midtermRectifyReview: (id, action, comment) => real.gdTeacherMidtermRectifyReview(id, action, comment),
  // 毕设评阅：本人任务 / 提交评分+意见
  getGraduationMyReviews: () => real.gdTeacherReviewsMy(),
  submitReview: (id, score, opinion) => real.gdTeacherReviewSubmit(id, score, opinion),
  // 毕设选题志愿确认（本人指导题目下待确认 + CONFIRM/REJECT，真实接口，无 mock 兜底）
  getGraduationChoicesPending: () => real.gdTeacherChoicesPending(),
  reviewGraduationChoice: (choiceId, action, reason) => real.gdTeacherChoiceReview(choiceId, action, reason),
  // 毕设选题变更审核（与本人相关的待审变更 + APPROVE/REJECT，真实接口，无 mock 兜底）
  getGraduationChangeRequestsPending: () => real.gdTeacherChangeRequestsPending(),
  reviewGraduationChangeRequest: (requestId, action, comment) => real.gdTeacherChangeRequestReview(requestId, action, comment),
  // 学工统计（谈话工作量 / 心理关注，仅聚合，真实接口，无 mock 兜底）
  getTalkStats: () => real.teacherTalkStats(),
  getMentalStats: () => real.teacherMentalStats(),
  // 在校服务待处理 / 学业预警待处理列表（真实接口，范围过滤，无 mock 兜底）
  getCampusServicePending: () => real.teacherCampusServicePending(),
  getAcademicWarnings: () => real.teacherAcademicWarnings(),
  // 毕设答辩安排（只读）
  getGraduationDefenseArrangements: () => real.gdTeacherDefenseArrangements(),
  // 毕设成绩：队列 / 详情 / 复核
  getGraduationGradeQueue: () => real.gdTeacherGradeQueue(),
  getGraduationGradeDetail: (id) => real.gdTeacherGradeDetail(id),
  reviewGrade: (id, action, comment) => real.gdTeacherGradeReview(id, action, comment),
  // 就业跟进：mobile 范围真实数据
  getEmployment: () =>
    realFirst('teacher.employment',
      () => real.teacherEmploymentReal({ stats: M.employmentStats, tabs: M.employmentTabs, list: M.employmentStudents, jobs: M.jobPool }),
      () => mockRequest({ stats: M.employmentStats, tabs: M.employmentTabs, list: M.employmentStudents, jobs: M.jobPool })),
  // 就业老师·转交学生（我负责的学生 + 转交给他人，真实接口，无 mock 兜底；仅限本人负责的学生）
  getEmploymentMyStudents: () => real.teacherEmploymentMyStudents(),
  transferEmploymentStudent: (studentId, newTeacher) => real.teacherEmploymentTransferStudent(studentId, newTeacher),
  // 就业老师·企业/岗位库（校级共享主数据，新增/停用，门禁在后端路由 employment.company/job.manage）
  getEmploymentCompanies: (status) => real.teacherEmploymentCompanies(status),
  createEmploymentCompany: (body) => real.teacherEmploymentCompanyCreate(body),
  disableEmploymentCompany: (companyId, reason) => real.teacherEmploymentCompanyDisable(companyId, reason),
  getEmploymentJobs: (companyId, status) => real.teacherEmploymentJobs(companyId, status),
  createEmploymentJob: (body) => real.teacherEmploymentJobCreate(body),
  disableEmploymentJob: (jobId, reason) => real.teacherEmploymentJobDisable(jobId, reason),
  // 消息：mobile 范围接口（替代通用 /messages）
  getMessages: () =>
    realFirstStrict('teacher.messages',
      () => real.teacherMessagesReal({ tabs: M.teacherMessageTabs, groups: M.teacherMessages }),
      () => mockRequest({ tabs: M.teacherMessageTabs, groups: M.teacherMessages })),
  // 迎新·现场报到核验（真实写操作，业务错误透出，不 mock 兜底）
  orientationCheckin: (admissionNo) => real.teacherOrientationCheckin(admissionNo),
  getOrientationTodayCheckins: () => real.teacherOrientationTodayCheckins(),
  getOrientationDashboard: () => real.teacherOrientationDashboard(),
  // 指导巡访：本月计划学生列表 + 记录巡访（真实写操作，业务错误透出）
  getInternshipVisitPlans: () => real.teacherInternshipVisitPlans(),
  recordInternshipVisit: (internshipId) => real.teacherInternshipVisitRecord(internshipId),
  // 补卡审批：待处理队列 + APPROVE/REJECT（owner+范围校验，真实接口，无 mock 兜底）
  getMakeupPending: () => real.teacherMakeupPending(),
  reviewMakeup: (makeupId, action, comment) => real.teacherMakeupReview(makeupId, action, comment),
  // 实习请假审批：待处理队列 + APPROVE/REJECT（owner+范围校验，真实接口，无 mock 兜底）
  getLeavePending: () => real.teacherLeavePending(),
  reviewLeave: (leaveId, action, comment) => real.teacherLeaveReview(leaveId, action, comment),
  // 指导记录：本人指导学生名单 + 新增记录（owner 校验，真实接口，无 mock 兜底）
  getInternshipMyStudents: () => real.teacherInternshipMyStudents(),
  createInternshipGuidance: (body) => real.teacherInternshipGuidanceCreate(body),
  // 学生实习鉴定：队列 + 详情 + 填写意见 + 审核（owner 校验，真实接口，无 mock 兜底）
  getStudentEvalPending: () => real.teacherStudentEvalPending(),
  getStudentEvalDetail: (evalId) => real.teacherStudentEvalDetail(evalId),
  submitStudentEvalAdvisorComment: (evalId, body) => real.teacherStudentEvalAdvisorComment(evalId, body),
  reviewStudentEval: (evalId, action, comment) => real.teacherStudentEvalReview(evalId, action, comment),
  // 企业评价：教师端列表 + 录入(五维评分) + 审核（owner 校验，真实接口，无 mock 兜底）
  getEnterpriseEvalPending: () => real.teacherEnterpriseEvalPending(),
  createEnterpriseEval: (body) => real.teacherEnterpriseEvalCreate(body),
  reviewEnterpriseEval: (evalId, action, comment) => real.teacherEnterpriseEvalReview(evalId, action, comment),
  // 实习保险：待核验队列 + 核验（owner 校验，真实接口，无 mock 兜底）
  getInsurancePending: () => real.teacherInsurancePending(),
  verifyInsurance: (insuranceId, action, comment) => real.teacherInsuranceVerify(insuranceId, action, comment),
  // 调岗/退岗初审：待处理队列 + 审核（owner 校验，真实接口，无 mock 兜底）
  getInternshipChangePending: () => real.teacherInternshipChangePending(),
  reviewInternshipChange: (changeId, action, comment) => real.teacherInternshipChangeReview(changeId, action, comment),
  // 实习成绩：教师端列表 + 核算(五项加权) + 发布（owner 校验，真实接口，无 mock 兜底）
  getInternshipScoreList: () => real.teacherInternshipScoreList(),
  computeInternshipScore: (body) => real.teacherInternshipScoreCompute(body),
  publishInternshipScore: (scoreId) => real.teacherInternshipScorePublish(scoreId),
  // 三方协议：待学校确认队列 + 学校确认生效（owner 校验，真实接口，无 mock 兜底）
  getAgreementPendingSchool: () => real.teacherAgreementPendingSchool(),
  confirmAgreementSchool: (agreementId) => real.teacherAgreementSchoolConfirm(agreementId),
  // 过程报告(日报/月报/总结)：教师端待批阅队列 + 详情 + 批阅（owner 校验，真实接口，无 mock 兜底）
  getProcessReportPending: () => real.teacherProcessReportPending(),
  getProcessReportDetail: (reportId) => real.teacherProcessReportDetail(reportId),
  reviewProcessReport: (reportId, action, comment) => real.teacherProcessReportReview(reportId, action, comment),
  // 实习计划任务完成度：教师端待确认队列 + 确认（owner 校验，真实接口，无 mock 兜底）
  getPlanTaskPending: () => real.teacherPlanTaskPending(),
  reviewPlanTask: (progressId, action, comment) => real.teacherPlanTaskReview(progressId, action, comment),
  // 实习申请：教师端待审核队列 + 审核（owner 校验，真实接口，无 mock 兜底）
  getInternshipApplicationPending: () => real.teacherInternshipApplicationPending(),
  reviewInternshipApplication: (applicationId, action, comment) => real.teacherInternshipApplicationReview(applicationId, action, comment),
  // 毕设任务书：教师端列表 + 下达 + 变更（owner 校验，真实接口，无 mock 兜底）
  getGraduationMyStudents: () => real.gdTeacherMyStudents(),
  getGraduationTaskbookList: () => real.teacherGraduationTaskbookList(),
  issueGraduationTaskbook: (gdStudentId, body) => real.teacherGraduationTaskbookIssue(gdStudentId, body),
  changeGraduationTaskbook: (gdStudentId, body) => real.teacherGraduationTaskbookChange(gdStudentId, body),
  // 答辩评委·本人待评分学生名单 + 录入评分（judgeName 服务端强制，真实接口，无 mock 兜底）
  getGraduationDefenseScorePending: () => real.teacherGraduationDefenseScorePending(),
  submitGraduationDefenseScore: (gdStudentId, body) => real.teacherGraduationDefenseScoreEntry(gdStudentId, body),
  // 家校联系：可登记学生名单 + 记录列表 + 登记联系 + 登记回执（owner 校验，真实接口，无 mock 兜底）
  getFamilyContactStudents: () => real.teacherFamilyContactStudents(),
  getFamilyContactList: (receiptStatus) => real.teacherFamilyContactList(receiptStatus),
  createFamilyContact: (studentId, body) => real.teacherFamilyContactCreate(studentId, body),
  markFamilyContactReceipt: (contactId, note) => real.teacherFamilyContactReceipt(contactId, note),
  // 学工请假审批链：待审批+后续处理台账+详情+审批+销假+逾期+续假（owner+节点校验，真实接口，无 mock 兜底）
  getAffairsLeavePending: () => real.teacherAffairsLeavePending(),
  getAffairsLeaveFollowup: () => real.teacherAffairsLeaveFollowup(),
  getAffairsLeaveDetail: (leaveId) => real.teacherAffairsLeaveDetail(leaveId),
  approveAffairsLeave: (leaveId, comment) => real.teacherAffairsLeaveApprove(leaveId, comment),
  rejectAffairsLeave: (leaveId, reason) => real.teacherAffairsLeaveReject(leaveId, reason),
  returnAffairsLeave: (leaveId, reason) => real.teacherAffairsLeaveReturn(leaveId, reason),
  cancelConfirmAffairsLeave: (leaveId, action, body) => real.teacherAffairsLeaveCancelConfirm(leaveId, action, body),
  proxyCancelAffairsLeave: (leaveId, actualReturnAt, note) => real.teacherAffairsLeaveProxyCancel(leaveId, actualReturnAt, note),
  overdueHandleAffairsLeave: (leaveId, handleType, note) => real.teacherAffairsLeaveOverdueHandle(leaveId, handleType, note),
  extensionApproveAffairsLeave: (leaveId, action, reason) => real.teacherAffairsLeaveExtensionApprove(leaveId, action, reason),
  getAffairsAidPending: () => real.teacherAffairsAidPending(),
  reviewAffairsAid: (applyId, body) => real.teacherAffairsAidReview(applyId, body),
  getAffairsFundingPending: () => real.teacherAffairsFundingPending(),
  reviewAffairsFunding: (appId, body) => real.teacherAffairsFundingReview(appId, body),
  getAffairsDisciplinePending: () => real.teacherAffairsDisciplinePending(),
  reviewAffairsDiscipline: (caseId, body) => real.teacherAffairsDisciplineReview(caseId, body),
  getAffairsRiskPending: () => real.teacherAffairsRiskPending(),
  processAffairsRisk: (riskId, content) => real.teacherAffairsRiskProcess(riskId, content),
  closeAffairsRisk: (riskId, conclusion) => real.teacherAffairsRiskClose(riskId, conclusion),
  // 班干部任命/免去：我的班级 + 班级学生名单 + 班干部名单 + 任命 + 免去（owner+范围校验，真实接口，无 mock 兜底）
  getAffairsMyClasses: () => real.teacherAffairsMyClasses(),
  getAffairsClassStudents: (classId) => real.teacherAffairsClassStudents(classId),
  getAffairsCadreList: (classId) => real.teacherAffairsCadreList(classId),
  appointAffairsCadre: (classId, body) => real.teacherAffairsCadreAppoint(classId, body),
  removeAffairsCadre: (cadreId, reason) => real.teacherAffairsCadreRemove(cadreId, reason),
  // 班级材料（辅导员本班查看/新增/作废，范围校验在服务层完成，真实接口，无 mock 兜底）
  getAffairsClassMaterials: (classId, materialType) => real.teacherAffairsClassMaterials(classId, materialType),
  addAffairsClassMaterial: (classId, body) => real.teacherAffairsClassMaterialAdd(classId, body),
  voidAffairsClassMaterial: (materialId, reason) => real.teacherAffairsClassMaterialVoid(materialId, reason),
  // 教务·教学任务确认（我的任务按 teacherKey 收敛+确认/退回，归属校验在服务层完成，真实接口，无 mock 兜底）
  getAcademicMyTasks: (status) => real.teacherAcademicMyTasks(status),
  actAcademicTask: (taskId, action, reason) => real.teacherAcademicTaskAct(taskId, action, reason),
  // 教务·发起调停课（我的课表选原课位 + 冲突预检 + 提交 + 我的申请列表 + 详情(移动端补归属校验) + 撤销，真实接口，无 mock 兜底）
  getAcademicMySchedule: (termId, week) => real.teacherAcademicMySchedule(termId, week),
  academicScheduleConflictCheck: (body) => real.teacherAcademicScheduleConflictCheck(body),
  submitAcademicScheduleChange: (body) => real.teacherAcademicScheduleSubmit(body),
  getAcademicScheduleChanges: (status) => real.teacherAcademicScheduleChanges(status),
  getAcademicScheduleChangeDetail: (changeId) => real.teacherAcademicScheduleChangeDetail(changeId),
  cancelAcademicScheduleChange: (changeId, reason) => real.teacherAcademicScheduleCancel(changeId, reason),
  // 缓考审批（辅导员初审+任课教师确认两节点身份共用，按当前身份自动收敛为对应节点队列，真实接口，无 mock 兜底）
  getAcademicDeferPending: () => real.teacherAcademicDeferPending(),
  reviewAcademicDefer: (deferId, action, reason) => real.teacherAcademicDeferReview(deferId, action, reason),
  // 教学评价（自评/同行/督导 + 我的结果(跨批次聚合) + 申诉(移动端补归属校验)，真实接口，无 mock 兜底）
  getAcademicEvaluationBatches: () => real.teacherAcademicEvaluationBatches(),
  getAcademicEvaluationMyTasks: (evaluatorType, batchId) => real.teacherAcademicEvaluationMyTasks(evaluatorType, batchId),
  submitAcademicEvaluation: (taskId, body) => real.teacherAcademicEvaluationSubmit(taskId, body),
  getAcademicEvaluationResults: () => real.teacherAcademicEvaluationResults(),
  appealAcademicEvaluation: (resultId, reason) => real.teacherAcademicEvaluationAppeal(resultId, reason),
  // 教务·成绩录入（真实接口，仅本人授课任务）
  getGradeTasks: (status) => real.teacherGradeTasks(status),
  getGradeRoster: (taskId) => real.teacherGradeRoster(taskId),
  enterGradeScore: (taskId, body) => real.teacherGradeEnterScore(taskId, body),
  submitGradeTask: (taskId) => real.teacherGradeSubmitTask(taskId),
  // 教务·课堂考勤（真实接口，移动端首创）
  getAttendanceSessions: () => real.teacherAttendanceSessions(),
  getAttendanceClassOptions: () => real.teacherAttendanceClassOptions(),
  createAttendanceSession: (body) => real.teacherAttendanceCreate(body),
  getAttendanceDetail: (sessionId) => real.teacherAttendanceDetail(sessionId),
  markAttendance: (sessionId, studentId, status) => real.teacherAttendanceMark(sessionId, studentId, status),
  submitAttendanceSession: (sessionId) => real.teacherAttendanceSubmit(sessionId),
  getWorkloadDeclarations: () => real.teacherWorkloadMy(),
  submitWorkload: (body) => real.teacherWorkloadSubmit(body)
}
export default teacherApi
