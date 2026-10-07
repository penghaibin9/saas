import { safeBusinessMessage, safeLocalizedText } from '../../../utils/presentationSafety.js'

// Presentation only. Stages, responsibility, actions and gate decisions come from the server.
export const ACADEMIC_FLOW_STAGES = Object.freeze([
  ['F10_TERM_SETUP', '学期准备'], ['F20_REGISTRATION', '学籍与注册'],
  ['F30_PROGRAM_COURSE', '培养方案与课程'], ['F40_TEACHING_TASK', '教学任务落实'],
  ['F50_SCHEDULE', '排课与课表'], ['F60_SELECTION', '选课'],
  ['F70_TEACHING_OPERATION', '日常教学'], ['F80_EXAM', '考务'],
  ['F90_GRADE', '成绩'], ['F100_GRADUATION', '毕业审核'],
  ['F110_QUALITY', '教学质量'], ['F120_ARCHIVE', '学期归档']
].map(([stageCode, label]) => Object.freeze({ stageCode, label })))

export const ACADEMIC_FLOW_STATUS = Object.freeze({
  NOT_STARTED: { label: '尚未开始', type: 'default' },
  ACTION_REQUIRED: { label: '待办理', type: 'warning' },
  BLOCKED: { label: '存在阻断', type: 'danger' },
  READY: { label: '已就绪', type: 'success' },
  DONE: { label: '已完成', type: 'success' },
  NOT_APPLICABLE: { label: '不适用', type: 'info' }
})
const BLOCKERS = Object.freeze({
  RESPONSIBILITY_UNRESOLVED: '责任尚未配置，请由组织与任职管理人员核对责任岗位',
  OFFERING_UNIT_UNRESOLVED: '开课单位尚未明确，请核对课程和教学任务归属',
  COLLEGE_NOT_READY: '责任学院尚未完成准备',
  SCHOOL_GATE_NOT_READY: '学校统一办理条件尚未满足',
  CROSS_COLLEGE_CONFLICT: '存在跨学院冲突，请交校教务处协调',
  ASSIGNMENT_EXPIRED: '责任任职已到期，请核对当前有效任职',
  DELEGATION_REQUIRED: '须明确代办授权后才能办理'
})
const ROLES = Object.freeze({ ACADEMIC_ADMIN: '校教务处', COLLEGE_ADMIN: '学院教务人员', ACADEMIC_TEACHER: '任课教师', LEADER: '只读领导', SCHOOL_ADMIN: '学校管理员' })
const ASSIGNMENTS = Object.freeze({ SECRETARY: '教学秘书', LEADER: '负责人', TEACHER: '任课教师' })
const ORGS = Object.freeze({ SCHOOL: '学校', COLLEGE: '学院', MAJOR: '专业', CLASS: '班级', TEACHER: '任课教师' })
const SCOPES = Object.freeze({ TENANT_ALL: '全校授权范围', SCHOOL: '全校授权范围', COLLEGE: '本学院授权范围', MAJOR: '本专业授权范围', CLASS: '本班级授权范围', ASSIGNED: '本人教学范围', SELF: '本人范围', NONE: '尚未配置范围' })
const list = value => Array.isArray(value) ? value : []
const record = value => value !== null && typeof value === 'object' && !Array.isArray(value)

export function academicFlowText(value, fallback = '请进入责任工作区核对') {
  const localized = safeLocalizedText({ value, unknownLabel: fallback })
  return !value ? fallback : safeBusinessMessage(localized.replace(/\bBLOCKER(?=\s*\d+\s*项)/g, '阻断').replace(/\bBLOCKER\b/g, '阻断项').replace(/\bHARD(?=\s*冲突)/g, '严重'), fallback)
}
export function academicFlowStatus(value) {
  return ACADEMIC_FLOW_STATUS[value] || { label: '状态待核对', type: 'info' }
}
export function academicFlowStageLabel(stage) {
  return academicFlowText(stage?.label, ACADEMIC_FLOW_STAGES.find(item => item.stageCode === stage?.stageCode)?.label || '责任事项')
}
export function academicFlowScopeLabel(viewer) { return SCOPES[viewer?.scopeType] || '授权范围待核对' }
export function academicFlowRoleLabel(viewer) { return ROLES[viewer?.roleCode] || '当前岗位' }
export function academicFlowBlockerMessage(blocker) {
  return academicFlowText(blocker?.message, BLOCKERS[blocker?.code] || '办理条件尚未满足，请核对责任事项')
}
export function academicFlowResponsibility(responsibility) {
  const value = record(responsibility) ? responsibility : {}
  const names = list(value.assigneeNames).filter(name => typeof name === 'string' && name.trim())
  const jobs = list(value.assignmentTypes).map(code => ASSIGNMENTS[code]).filter(Boolean)
  const roles = list(value.roleCodes).map(code => ROLES[code]).filter(Boolean)
  return {
    orgName: typeof value.orgName === 'string' && value.orgName ? value.orgName : (ORGS[value.orgType] || '责任组织待明确'),
    assigneeLabel: value.resolved === true && names.length ? names.join('、') : '具体责任人待配置',
    positionLabel: [...new Set([...jobs, ...roles])].join('、') || '责任岗位待明确',
    resolved: value.resolved === true,
    reason: value.resolved === true ? '' : academicFlowText(value.reason, BLOCKERS[value.reason] || '责任尚未配置，请由组织与任职管理人员核对')
  }
}
export function academicFlowCount(value) { return Number.isSafeInteger(value) && value >= 0 ? String(value) : '待核对' }

export function academicFlowOwner(responsibility) {
  const display = academicFlowResponsibility(responsibility)
  return [display.orgName, display.positionLabel, display.assigneeLabel, display.reason].filter(Boolean).join(' · ')
}
export function academicFlowNextOwner(nextStep) {
  const label = academicFlowText(nextStep?.label, '下一责任事项待明确')
  return nextStep?.responsibility ? `${label}；${academicFlowOwner(nextStep.responsibility)}` : label
}

export function validateAcademicFlow(data, { termId = '' } = {}) {
  if (!record(data) || !record(data.term) || !record(data.viewer) ||
      !['unitProgress', 'currentResponsibilities', 'stages', 'schoolGates'].every(key => Array.isArray(data[key])) ||
      typeof data.viewer.scopeType !== 'string' || !Array.isArray(data.viewer.collegeIds)) {
    throw new Error('责任进度返回不完整，请重新读取')
  }
  if (termId && data.term.termId !== termId) throw new Error('返回的学期与所选学期不一致，请重新读取')
  if (data.viewer.majorIds !== undefined && (!Array.isArray(data.viewer.majorIds) || data.viewer.majorIds.some(value => typeof value !== 'string' || !value))) throw new Error('专业责任范围无法安全读取，请重新确认身份')
  const identifiers = [...data.viewer.collegeIds, ...(data.viewer.majorIds || []), data.term.termId].filter(value => value != null)
  for (const unit of data.unitProgress) {
    if (!record(unit) || !Array.isArray(unit.stages) || !Array.isArray(unit.blockers)) throw new Error('学院进度返回不完整，请重新读取')
    identifiers.push(unit.collegeId)
    if (!['TENANT_ALL', 'SCHOOL'].includes(data.viewer.scopeType) && !data.viewer.collegeIds.includes(unit.collegeId)) {
      throw new Error('学院进度与当前授权范围不一致，请重新确认身份')
    }
  }
  const selectedStages = [data.schoolStage, data.myStage].filter(stage => stage != null && (!record(stage) || Object.keys(stage).length))
  const stages = [...data.stages, ...data.currentResponsibilities, ...data.unitProgress.flatMap(unit => unit.stages), ...selectedStages]
  for (const stage of stages) {
    if (!record(stage) || typeof stage.stageCode !== 'string' || typeof stage.status !== 'string' || !Array.isArray(stage.blockers)) {
      throw new Error('责任阶段返回不完整，请重新读取')
    }
    if (stage.termId != null) identifiers.push(stage.termId)
    if (stage.responsibility?.orgId != null) identifiers.push(stage.responsibility.orgId)
    identifiers.push(...list(stage.responsibility?.assigneeUserIds))
  }
  if (data.schoolGates.some(gate => !record(gate) || !Array.isArray(gate.blockers))) throw new Error('学校办理条件返回不完整，请重新读取')
  if (identifiers.some(value => typeof value !== 'string')) throw new Error('责任对象标识无法安全读取，请重新读取')
  return data
}
