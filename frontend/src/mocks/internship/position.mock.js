/**
 * 岗位实习中心 · 岗位库 mock（独立文件，与 internship.mock 隔离，避免与「实习批次」并行任务冲突）。
 * 页面禁止直接 import，必须经 modules/internship/api/position.api 获取。
 */

export const POSITION_STATUS = [
  { value: 'DRAFT', label: '草稿' },
  { value: 'PENDING', label: '待审核' },
  { value: 'PUBLISHED', label: '已上架' },
  { value: 'OFFLINE', label: '已下架' },
  { value: 'SUSPENDED', label: '已暂停' },
  { value: 'FULL', label: '已满员' },
  { value: 'RISK', label: '风险岗位' },
  { value: 'ARCHIVED', label: '已归档' }
]
const META = {
  DRAFT: { label: '草稿', tone: 'default' }, PENDING: { label: '待审核', tone: 'warning' },
  PUBLISHED: { label: '已上架', tone: 'success' }, OFFLINE: { label: '已下架', tone: 'default' },
  SUSPENDED: { label: '已暂停', tone: 'warning' }, FULL: { label: '已满员', tone: 'primary' },
  RISK: { label: '风险岗位', tone: 'danger' }, ARCHIVED: { label: '已归档', tone: 'default' }
}
export const positionMeta = (s) => META[s] || { label: s, tone: 'default' }

/** 企业选择器（岗位关联企业用；真实态走 /internship/enterprises，mock 用此静态表） */
export const enterpriseOptions = [
  { id: 'ent-001', name: '华信智能科技有限公司', coopStatus: 'ACTIVE', blacklist: false },
  { id: 'ent-002', name: '星辰网络技术有限公司', coopStatus: 'PENDING', blacklist: false },
  { id: 'ent-003', name: '瑞丰物流有限公司', coopStatus: 'BLACKLIST', blacklist: true }
]
export const enterpriseMentorMap = {
  'ent-001': [{ id: 'ec-2', name: '陈工', contactTypeLabel: '企业导师' }],
  'ent-002': [], 'ent-003': []
}

function row(o) {
  const m = positionMeta(o.status)
  return {
    id: o.id, companyId: o.companyId, companyName: o.companyName, batchId: o.batchId || '',
    title: o.title, category: o.category || '', majorRequirement: o.major || '',
    gradeRequirement: o.grade || '', workLocation: o.location || '', salaryRange: o.salary || '',
    subsidy: o.subsidy || '', headcount: o.headcount, allocatedCount: o.allocated || 0,
    remaining: Math.max(0, o.headcount - (o.allocated || 0)),
    mentorContactId: o.mentorContactId || '', mentorName: o.mentorName || '',
    riskFlag: !!o.risk, riskNote: o.riskNote || '',
    status: o.status, statusLabel: m.label, statusTone: m.tone,
    remark: o.remark || '', publishAt: o.publishAt || null, archivedAt: null, archivedBy: '',
    updatedAt: o.updatedAt || '2026-06-30'
  }
}

export const positionList = [
  row({ id: 'pos-001', companyId: 'ent-001', companyName: '华信智能科技有限公司', title: '前端开发实习生', category: '技术', major: '软件技术', grade: '2024级', location: '上海浦东', salary: '3k-4k', headcount: 5, allocated: 2, mentorContactId: 'ec-2', mentorName: '陈工', status: 'PUBLISHED', publishAt: '2026-06-01' }),
  row({ id: 'pos-002', companyId: 'ent-001', companyName: '华信智能科技有限公司', title: '测试实习生', category: '技术', major: '软件技术', grade: '2024级', location: '上海浦东', salary: '3k', headcount: 3, allocated: 0, status: 'PENDING' }),
  row({ id: 'pos-003', companyId: 'ent-001', companyName: '华信智能科技有限公司', title: '运维实习生（高空作业）', category: '技术', major: '计算机网络', grade: '2023级', location: '苏州', salary: '4k', headcount: 2, allocated: 0, status: 'RISK', risk: true, riskNote: '涉及高空作业，安全条件待企业整改' })
]
export const positionDetailMap = Object.fromEntries(positionList.map((p) => [p.id, { ...p, company: { id: p.companyId, name: p.companyName, coopStatus: 'ACTIVE', coopStatusLabel: '合作中', blacklist: false }, auditTrail: [] }]))
