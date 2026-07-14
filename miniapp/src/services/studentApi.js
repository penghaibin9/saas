/** 学生端数据服务：真实后端优先（主链：首页/档案/消息），其余仍 mock；失败自动回退。 */
import { mockRequest, realFirst, realFirstStrict } from './request'
import * as real from './realApi'
import * as M from '@/mock'

export const studentApi = {
  getHome: () =>
    realFirst('student.home',
      () => mockRequest(M.studentHome).then((d) => real.enrichHome(d)),
      () => mockRequest(M.studentHome)),
  getProfile: () =>
    realFirstStrict('student.profile',
      () => real.enrichProfileReal(M.studentProfile),
      () => mockRequest(M.studentProfile)),
  getOrientation: () =>
    realFirstStrict('student.orientation',
      () => real.enrichOrientation(M.studentOrientation),
      () => mockRequest(M.studentOrientation)),
  getOrientationBatchStatus: () => real.orientationBatchStatus(),
  submitOrientationCollect: (body) => real.orientationCollectSubmit(body),
  submitOrientationGreenChannel: (body) => real.orientationGreenChannelSubmit(body),
  getServices: () =>
    realFirstStrict('student.campus',
      () => real.enrichCampusService({ categories: M.serviceCategories, items: M.serviceItems }),
      () => mockRequest({ categories: M.serviceCategories, items: M.serviceItems })),
  getAcademic: () =>
    realFirstStrict('student.academic',
      () => real.enrichAcademic(M.studentAcademic),
      () => mockRequest(M.studentAcademic)),
  getInternship: () =>
    realFirstStrict('student.internship',
      () => real.enrichInternship(M.studentInternship),
      () => mockRequest(M.studentInternship)),
  getGraduation: () =>
    realFirstStrict('student.graduation',
      () => real.enrichGraduation(M.studentGraduation),
      () => mockRequest(M.studentGraduation)),
  // 毕业设计·选题/任务书/开题/中期/成果/答辩/成绩（真实接口，无 mock 兜底，业务错误透出）
  getGraduationActiveRound: () => real.gdActiveRound(),
  getGraduationTopics: () => real.gdTopics(),
  getMyGraduationChangeRequests: () => real.gdMyChangeRequests(),
  submitGraduationChoices: (roundId, choices) => real.gdSubmitChoices(roundId, choices),
  withdrawGraduationChoices: (roundId) => real.gdWithdrawChoices(roundId),
  requestGraduationTopicChange: (newTopicId, reason) => real.gdRequestChange(newTopicId, reason),
  getGraduationProposal: () => real.gdProposal(),
  submitGraduationProposal: (body) => real.gdSubmitProposal(body),
  getGraduationFinal: () => real.gdFinal(),
  submitGraduationFinal: (body) => real.gdSubmitFinal(body),
  getGraduationTaskbook: () => real.gdTaskbook(),
  confirmGraduationTaskbook: () => real.gdTaskbookConfirm(),
  getGraduationMidterm: () => real.gdMidterm(),
  submitGraduationMidtermRectify: (content) => real.gdMidtermRectify(content),
  getGraduationDefense: () => real.gdDefense(),
  getGraduationGrade: () => real.gdGrade(),
  appealGraduationGrade: (reason) => real.gdGradeAppeal(reason),
  getEmployment: () =>
    realFirstStrict('student.employment',
      () => real.enrichEmployment(M.studentEmployment),
      () => mockRequest(M.studentEmployment)),
  getApplications: () =>
    realFirst('student.applications',
      () => real.selfApplications(),
      () => mockRequest({ tabs: M.applicationTabs, list: M.applications })),
  getMessages: () =>
    realFirstStrict('student.messages',
      () => real.selfMessages({ tabs: M.studentMessageTabs, groups: M.studentMessages }),
      () => mockRequest({ tabs: M.studentMessageTabs, groups: M.studentMessages })),
  // 写操作：业务错误（401/403/409/422）透出，不兜底成成功
  submitServiceApply: (body) => real.submitServiceApply(body),
  submitWeeklyReport: (body) => real.submitWeeklyReport(body),
  submitCheckin: (body) => real.submitCheckin(body),
  getCheckinWeek: () => real.internshipCheckinWeek(),
  getInternshipEnterprises: (city) => real.internshipEnterprises(city),
  markMessageRead: (id) => real.markMessageRead(id),
  // 岗位实习·学生自助（三方协议 / 请假 / 意向 / 自评 / 调岗退岗 / 保险 / 计划 / 过程报告）
  // 真实优先无 mock 兜底，业务错误（401/403/409/422）透出
  getInternshipAgreements: () => real.internshipAgreements(),
  getInternshipAgreementDetail: (id) => real.internshipAgreementDetail(id),
  confirmInternshipAgreement: (id, body) => real.confirmInternshipAgreement(id, body),
  getInternshipLeaves: () => real.internshipLeaves(),
  applyInternshipLeave: (body) => real.applyInternshipLeave(body),
  withdrawInternshipLeave: (id) => real.withdrawInternshipLeave(id),
  getInternshipSelfEval: () => real.internshipSelfEval(),
  submitInternshipSelfEval: (body) => real.submitInternshipSelfEval(body),
  getInternshipIntention: () => real.internshipIntentionMy(),
  saveInternshipIntention: (body) => real.saveInternshipIntention(body),
  submitInternshipIntention: () => real.submitInternshipIntention(),
  withdrawInternshipIntention: () => real.withdrawInternshipIntention(),
  getInternshipChangeRequests: () => real.internshipChangeRequests(),
  applyInternshipChange: (body) => real.applyInternshipChange(body),
  getInternshipInsurance: () => real.internshipInsuranceMy(),
  submitInternshipInsurance: (body) => real.submitInternshipInsurance(body),
  getInternshipPlan: () => real.internshipPlanMy(),
  getInternshipPlanTasks: () => real.internshipPlanTasksMy(),
  ackInternshipPlan: () => real.ackInternshipPlan(),
  submitInternshipPlanTask: (sortOrder, body) => real.submitInternshipPlanTask(sortOrder, body),
  submitProcessReport: (body) => real.submitProcessReport(body),
  // 13A 学工中心（P7 多端收口，真实优先无 mock 兜底，业务错误透出）
  getAffairsOverview: () => real.affairsOverview(),
  getMyLeaves: () => real.affairsLeaveMy(),
  getMyAid: () => real.affairsAidMy(),
  getMyFunding: () => real.affairsFundingMy(),
  getMyDiscipline: () => real.affairsDisciplineMy(),
  getMyDorm: () => real.affairsDormMy(),
  getDormOptions: () => real.affairsDormOptions(),
  getDormRooms: (buildingId, floor) => real.affairsDormRooms(buildingId, floor),
  getDormBeds: (roomId) => real.affairsDormBeds(roomId),
  selfSelectBed: (bedId) => real.affairsDormSelfSelect(bedId),
  // 学工中心·学生活动与第二课堂（真实接口，无 mock 兜底）
  getMyActivities: () => real.affairsMyActivities(),
  enrollActivity: (activityId, action) => real.affairsActivityEnroll(activityId, action),
  checkinActivity: (activityId, method) => real.affairsActivityCheckin(activityId, method),
  // 13B 教务中心（P7 真实优先无 mock 兜底）
  getMySchedule: () => real.acadScheduleMy(),
  getMyTranscript: () => real.acadTranscriptMy(),
  getMyAcadStatus: () => real.acadStatusMy(),
  submitStatusChange: (body) => real.acadStatusChange(body),
  getMyGraduation: () => real.acadGraduationMy(),
  // 教务中心·学分修读/学业预警/补考重修/网上选课（真实接口，无 mock 兜底）
  getMyCredits: () => real.acadCreditsMy(),
  getMyWarnings: () => real.acadWarningMy(),
  getMyMakeup: () => real.acadMakeupMy(),
  applyRetake: (courseName, termCode, reason) => real.acadRetakeApply(courseName, termCode, reason),
  getSelectionCourses: (batchId) => real.acadSelectionCourses(batchId),
  enrollSelection: (selectionCourseId) => real.acadSelectionEnroll(selectionCourseId),
  dropSelection: (selectionCourseId) => real.acadSelectionDrop(selectionCourseId),
  getMySelections: (batchId) => real.acadSelectionMy(batchId)
}
export default studentApi
