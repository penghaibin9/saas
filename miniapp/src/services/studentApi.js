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
  // 13B 教务中心（P7 真实优先无 mock 兜底）
  getMySchedule: () => real.acadScheduleMy(),
  getMyTranscript: () => real.acadTranscriptMy(),
  getMyAcadStatus: () => real.acadStatusMy(),
  submitStatusChange: (body) => real.acadStatusChange(body),
  getMyGraduation: () => real.acadGraduationMy()
}
export default studentApi
