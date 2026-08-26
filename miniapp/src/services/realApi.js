import * as base from './realApiBase'
import { latestRequest } from './latestRequest'

export * from './realApiBase'

// 毕设学生端：同一投影重复刷新时只交付最新一次结果，防止下拉刷新/提交后刷新被旧响应覆盖。
export const enrichGraduation = () =>
  latestRequest('student:graduation:overview', () => base.enrichGraduation())
export const gdProposal = () =>
  latestRequest('student:graduation:proposal', () => base.gdProposal())
export const gdFinal = () =>
  latestRequest('student:graduation:final', () => base.gdFinal())
export const gdMidterm = () =>
  latestRequest('student:graduation:midterm', () => base.gdMidterm())
export const gdDefense = () =>
  latestRequest('student:graduation:defense', () => base.gdDefense())
export const gdGrade = () =>
  latestRequest('student:graduation:grade', () => base.gdGrade())
export const gdPeerTasks = () =>
  latestRequest('student:graduation:peer', () => base.gdPeerTasks())
export const gdArchive = () =>
  latestRequest('student:graduation:archive', () => base.gdArchive())

// 教师端详情：四类详情共用同一 latest key，因为页面同一时刻只允许一个“当前处理对象”。
// 快速上一条/下一条时，旧请求晚返回也会追随最新详情，避免“显示 A、动作打 B”的竞态窗口。
export const gdTeacherProposalDetail = (id) =>
  latestRequest('teacher:graduation:detail', () => base.gdTeacherProposalDetail(id))
export const gdTeacherFinalDetail = (id) =>
  latestRequest('teacher:graduation:detail', () => base.gdTeacherFinalDetail(id))
export const gdTeacherMidtermDetail = (id) =>
  latestRequest('teacher:graduation:detail', () => base.gdTeacherMidtermDetail(id))
export const gdTeacherGradeDetail = (id) =>
  latestRequest('teacher:graduation:detail', () => base.gdTeacherGradeDetail(id))
