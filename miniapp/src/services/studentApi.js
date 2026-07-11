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
  // 选题管理：浏览题目库/进行中轮次/提交志愿/发起课题变更申请（真实优先，业务错误透出，不 mock 冒充成功）
  getGraduationTopics: () => real.gdTopics(),
  getGraduationActiveRound: () => real.gdActiveRound(),
  submitGraduationChoices: (roundId, choices) => real.gdSubmitChoices(roundId, choices),
  withdrawGraduationChoices: (roundId) => real.gdWithdrawChoices(roundId),
  requestGraduationTopicChange: (newTopicId, reason) => real.gdRequestChange(newTopicId, reason),
  getMyGraduationChangeRequests: () => real.gdMyChangeRequests(),
  // 开题材料：查看本人开题报告状态、提交/重交（真实优先，业务错误透出，不 mock 冒充成功）
  getGraduationProposal: () => real.gdProposal(),
  submitGraduationProposal: (data) => real.gdSubmitProposal(data),
  // 成果提交：查看本人论文状态、提交初稿/定稿（真实优先，业务错误透出，不 mock 冒充成功）
  getGraduationFinal: () => real.gdFinal(),
  submitGraduationFinal: (data) => real.gdSubmitFinal(data),
  // 过程指导：任务书查看/确认、中期检查查看/提交整改、成绩查看（真实优先，业务错误透出，不 mock 冒充成功）
  getGraduationTaskbook: () => real.gdTaskbook(),
  confirmGraduationTaskbook: () => real.gdTaskbookConfirm(),
  getGraduationMidterm: () => real.gdMidterm(),
  submitGraduationMidtermRectify: (content) => real.gdMidtermRectify(content),
  // 答辩：查看本人答辩安排（已发布才显示时间/地点/评委）
  getGraduationDefense: () => real.gdDefense(),
  getGraduationGrade: () => real.gdGrade(),
  appealGraduationGrade: (reason) => real.gdGradeAppeal(reason),
  getGraduationPeerTasks: () => real.gdPeerTasks(),
  submitGraduationPeer: (pid, opinion) => real.gdPeerSubmit(pid, opinion),
  rectifyGraduationPeer: (pid, note) => real.gdPeerRectify(pid, note),
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
  getInternshipAgreements: () => real.internshipAgreements(),
  getInternshipAgreementDetail: (id) => real.internshipAgreementDetail(id),
  confirmInternshipAgreement: (id, body) => real.confirmInternshipAgreement(id, body),
  getInternshipLeaves: () => real.internshipLeaves(),
  applyInternshipLeave: (body) => real.applyInternshipLeave(body),
  withdrawInternshipLeave: (id) => real.withdrawInternshipLeave(id),
  getInternshipSelfEval: () => real.internshipSelfEval(),
  submitInternshipSelfEval: (body) => real.submitInternshipSelfEval(body),
  getInternshipIntention: () =>
    realFirstStrict('student.internship.intention', () => real.internshipIntentionMy(), () => Promise.reject(new Error('演示模式不可用'))),
  saveInternshipIntention: (body) => real.saveInternshipIntention(body),
  submitInternshipIntention: () => real.submitInternshipIntention(),
  withdrawInternshipIntention: () => real.withdrawInternshipIntention(),
  submitProcessReport: (body) => real.submitProcessReport(body),
  getInternshipChangeRequests: () => real.internshipChangeRequests(),
  applyInternshipChange: (body) => real.applyInternshipChange(body),
  getInternshipPlan: () => real.internshipPlanMy(),
  ackInternshipPlan: () => real.ackInternshipPlan(),
  getInternshipPlanTasks: () => real.internshipPlanTasksMy(),
  submitInternshipPlanTask: (sortOrder, body) => real.submitInternshipPlanTask(sortOrder, body),
  getInternshipInsurance: () => real.internshipInsuranceMy(),
  submitInternshipInsurance: (body) => real.submitInternshipInsurance(body),
  signInternshipAgreementEsign: (id) => real.signInternshipAgreementEsign(id),
  markMessageRead: (id) => real.markMessageRead(id),
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
