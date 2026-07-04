/**
 * P3 · 真实后端适配层：字段映射为各 mock 契约形状，页面零结构改动。
 * 全部经 realFirst() 使用：后端挂了自动回退 mock。
 */
import { ENV } from '@/config/env'
import { realRequest, setRefreshToken, setToken } from './request'

/* 小程序角色 key → 后端演示账号（切换角色=重新 mock-login 对应账号） */
const ROLE_ACCOUNT = {
  student: 'student01',
  counselor: 'counselor01',
  gd_mentor: 'teacher01',
  intern_mentor: 'teacher01',
  employment: 'employment01',
  academic: 'academic01',
  college_admin: 'college_admin01'
}

export function accountOf(roleKey, side) {
  return ROLE_ACCOUNT[roleKey] || (side === 'teacher' ? 'counselor01' : 'student01')
}

export async function loginReal(roleKey, side) {
  const data = await realRequest('/auth/mock-login', {
    method: 'POST',
    auth: false,
    data: { loginName: accountOf(roleKey, side), password: 'demo' }
  })
  setToken(data.accessToken)
  setRefreshToken(data.refreshToken || '')
  return data
}

export const brand = () => realRequest('/tenant/brand')
export const me = () => realRequest('/auth/me')

const STAGE_TEXT = {
  ORIENTATION: '迎新', ON_CAMPUS: '在校', INTERNSHIP: '实习',
  GRADUATION_DESIGN: '毕设', EMPLOYMENT: '就业'
}

function studentItem(r) {
  return {
    id: String(r.id),
    name: r.realName,
    studentNo: r.studentNo,
    className: r.className || '—',
    major: r.majorName || '—',
    stage: STAGE_TEXT[r.currentStage] || '在校',
    task: '',
    risk: r.riskLevel === 'NONE' ? 'LOW' : r.riskLevel,
    pending: 0,
    last: (r.updatedAt || '').slice(0, 16).replace('T', ' '),
    intern: r.currentStage === 'INTERNSHIP',
    gd: r.currentStage === 'GRADUATION_DESIGN'
  }
}

export async function students() {
  const d = await realRequest('/students', { data: { page: 1, pageSize: 100 } })
  return d.items.map(studentItem)
}

export async function riskStudents() {
  const list = await students()
  return list.filter((s) => s.risk === 'HIGH' || s.risk === 'MEDIUM')
}

export async function student360(id) {
  const d = await realRequest(`/students/${id}`)
  return {
    base: {
      name: d.realName, studentNo: d.studentNo, className: d.className || '—',
      major: d.majorName || '—', stage: STAGE_TEXT[d.currentStage] || '在校',
      phone: d.phoneMasked || ''
    },
    risk: {
      level: d.riskLevel === 'NONE' ? 'LOW' : d.riskLevel,
      types: d.riskLevel === 'NONE' ? [] : ['存在风险信号（演示）'],
      since: (d.updatedAt || '').slice(0, 10)
    },
    tags: [STAGE_TEXT[d.currentStage] || '在校'],
    timeline: (d.timeline || []).map((e, i) => ({
      id: 'tl' + i,
      time: (e.occurredAt || '').replace('T', ' ').slice(0, 16),
      text: e.title || '',
      type: 'normal'
    }))
  }
}

const BIZ_LABEL = {
  PROFILE_CORRECTION: '学籍 · 信息更正', COMPANY_CHANGE: '实习 · 单位变更',
  MATERIAL_VERIFY: '就业 · 材料核验', LEAVE: '在校 · 请假'
}

export async function approvals() {
  const d = await realRequest('/approvals/tasks', { data: { page: 1, pageSize: 50 } })
  return d.items.map((t) => ({
    id: String(t.taskId),
    title: t.title || '审批任务',
    type: BIZ_LABEL[t.sourceBizType] || t.sourceBizType || '审批',
    student: t.applicantName || '—',
    className: '',
    submitTime: (t.submittedAt || '').replace('T', ' ').slice(0, 16),
    status: 'PENDING_REVIEW',
    level: t.urgency === 'OVERDUE' || t.urgency === 'NEAR_DEADLINE' ? 'high' : 'normal',
    fields: [
      { label: '来源模块', value: t.sourceModule || '—' },
      { label: '当前节点', value: t.nodeName || t.nodeCode || '—' },
      { label: '提交时间', value: (t.submittedAt || '').replace('T', ' ').slice(0, 16) }
    ],
    flow: [
      { node: '学生提交', time: (t.submittedAt || '').slice(5, 16).replace('T', ' '), done: true },
      { node: t.nodeName || '审核', time: '待处理', done: false, current: true },
      { node: '办结', time: '—', done: false }
    ]
  }))
}

/** 审批操作：approve / reject / return（return 映射为后端 reject，原因必填） */
export function actApproval(id, type, reason) {
  if (type === 'approve') {
    return realRequest(`/approvals/tasks/${id}/approve`, { method: 'POST', data: { comment: reason || '' } })
  }
  return realRequest(`/approvals/tasks/${id}/reject`, {
    method: 'POST',
    data: { reason: reason && reason.trim().length >= 5 ? reason : '移动端驳回（未填详细原因）' }
  })
}

const TODO_GROUP = { APPROVAL: 'approve', REVIEW: 'review', RISK: 'risk', SUBMIT: 'confirm', CONFIRM: 'confirm' }

export async function todos() {
  const d = await realRequest('/todos', { data: { page: 1, pageSize: 50 } })
  return d.items.map((t) => ({
    id: String(t.todoId),
    group: t.status === 'DONE' ? 'done' : TODO_GROUP[t.todoType] || 'approve',
    title: t.title,
    student: '',
    module: t.sourceModule || '—',
    deadline: (t.dueAt || '').replace('T', ' ').slice(0, 16),
    level: 'normal',
    status: t.status === 'DONE' ? 'DONE' : 'PENDING_REVIEW',
    soon: false
  }))
}

/** 消息：合入 mock 的 tabs/groups 结构（真实条目放进第一个 tab，徽标重算） */
export async function enrichMessages(mockData) {
  const d = await realRequest('/messages', { data: { page: 1, pageSize: 50 } })
  const items = d.items.map((m) => ({
    id: String(m.messageId),
    title: m.title,
    module: m.messageType === 'ANNOUNCEMENT' ? '公告' : m.messageType === 'SYSTEM' ? '系统' : '待办通知',
    level: 'normal',
    time: (m.createdAt || '').replace('T', ' ').slice(0, 16),
    read: m.readStatus === 'READ',
    actionable: false
  }))
  const tabs = mockData.tabs || []
  const firstKey = tabs.length ? tabs[0].key : 'todo'
  mockData.groups = { ...mockData.groups, [firstKey]: items }
  tabs.forEach((t) => {
    const list = mockData.groups[t.key] || []
    t.badge = list.filter((x) => !x.read).length
  })
  mockData.realApi = true
  return mockData
}

/** 学生「我的档案」：真实学生（演示绑定 student_id=1）合入 mock 结构 */
export async function enrichProfile(mockProfile) {
  const d = await realRequest('/students/1')
  mockProfile.base = { ...mockProfile.base, name: d.realName, studentNo: d.studentNo, gender: d.gender || mockProfile.base.gender }
  mockProfile.contact = { ...mockProfile.contact, phone: d.phoneMasked || mockProfile.contact.phone }
  mockProfile.org = {
    ...mockProfile.org,
    college: d.collegeName || mockProfile.org.college,
    major: d.majorName || mockProfile.org.major,
    className: d.className || mockProfile.org.className
  }
  mockProfile.status = { ...mockProfile.status, stageText: STAGE_TEXT[d.currentStage] || mockProfile.status.stageText }
  mockProfile.realApi = true
  return mockProfile
}

/** 学生首页：真实阶段 + 待办计数合入 mock 结构 */
export async function enrichHome(mockHome) {
  const [stu, summary] = await Promise.all([
    realRequest('/students/1'),
    realRequest('/todos/summary').catch(() => null)
  ])
  if (mockHome.stageCard) {
    mockHome.stageCard.stageText = STAGE_TEXT[stu.currentStage] || mockHome.stageCard.stageText
    mockHome.stageCard.title = `你正处于「${mockHome.stageCard.stageText}」阶段`
  }
  if (summary && mockHome.todoOverview) {
    mockHome.todoOverview.pending = summary.pending
  }
  mockHome.realApi = true
  return mockHome
}
