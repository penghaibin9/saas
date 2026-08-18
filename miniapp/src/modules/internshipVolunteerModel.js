const CONTACT_MODES = ['MASKED_ONLY', 'AFTER_INTERVIEW', 'AFTER_ACCEPT_INTENT', 'IMMEDIATE']

function first(raw, ...keys) {
  for (const key of keys) {
    if (raw?.[key] !== undefined && raw?.[key] !== null && raw?.[key] !== '') return raw[key]
  }
  return null
}

function emptySlot(volunteerNo) {
  return { volunteerNo, positionId: null, positionName: '', companyName: '', workLocation: '', applicationStatement: '', version: 0 }
}

function cloneSlots(slots = []) {
  return [1, 2, 3].map((volunteerNo) => ({ ...(slots.find((slot) => Number(slot.volunteerNo) === volunteerNo) || emptySlot(volunteerNo)), volunteerNo }))
}

function optionalVersion(value) {
  if (value === undefined || value === null || value === '') return null
  const parsed = Number(value)
  return Number.isInteger(parsed) && parsed >= 0 ? parsed : null
}

function requireVersion(value, label) {
  const version = optionalVersion(value)
  if (version === null) throw new Error(`${label}缺失，请刷新后重试`)
  return version
}

function requireGroupVersion(group) {
  return requireVersion(group?.version, '志愿组版本')
}

export function normalizeMobilePositionDetail(raw = {}) {
  const rights = raw.rights || raw.laborConditions || {}
  return {
    id: first(raw, 'id', 'positionId'),
    title: first(raw, 'title', 'positionName') || '岗位名称待完善',
    remuneration: first(raw, 'remunerationDisplay', 'salaryRange', 'remuneration') || '薪酬待确认',
    companyId: first(raw, 'companyId') || raw.company?.id || null,
    companyName: first(raw, 'companyName') || raw.company?.name || '企业信息待完善',
    workLocation: first(raw, 'workLocation', 'address', 'city') || '地点待定',
    remaining: Number(first(raw, 'remaining', 'remainingQuota', 'remainingCount') || 0),
    description: first(raw, 'description', 'jobDescription') || '企业暂未补充岗位介绍。',
    requirements: first(raw, 'requirements', 'requirementText') || '企业暂未补充岗位要求。',
    dailyHours: first(raw, 'dailyHours') ?? rights.dailyHours ?? '待确认',
    weeklyHours: first(raw, 'weeklyHours') ?? rights.weeklyHours ?? '待确认',
    shift: first(raw, 'shift', 'shiftType') ?? rights.shift ?? '待确认',
    nightShift: first(raw, 'nightShift') ?? rights.nightShift,
    overtime: first(raw, 'overtime', 'overtimePolicy') ?? rights.overtime ?? '待确认',
    restDays: first(raw, 'restDays', 'restDayPolicy') ?? rights.restDays ?? '待确认',
    subsidy: first(raw, 'subsidy', 'subsidyDisplay') ?? rights.subsidy ?? '待确认',
    accommodation: first(raw, 'accommodationProvided') ?? rights.accommodationProvided,
    meal: first(raw, 'mealProvided') ?? rights.mealProvided,
    hazardous: first(raw, 'hazardous', 'hazardousExposure') ?? rights.hazardous ?? '无明确危险因素说明',
    equipment: first(raw, 'equipment', 'protectiveEquipment') ?? rights.equipment ?? '待企业/学校确认'
  }
}

export function mobileConditionRows(position = {}) {
  const yesNo = (value, yes, no) => value === true ? yes : value === false ? no : '待确认'
  return [
    ['每日工时', position.dailyHours], ['每周工时', position.weeklyHours], ['班次', position.shift],
    ['夜班', yesNo(position.nightShift, '有', '无')], ['加班安排', position.overtime], ['休息日', position.restDays],
    ['岗位薪酬', position.remuneration], ['补贴', position.subsidy], ['住宿', yesNo(position.accommodation, '提供', '不提供')],
    ['餐食', yesNo(position.meal, '提供', '不提供')], ['危险因素', position.hazardous], ['劳动防护/设备', position.equipment]
  ]
}

export function normalizeMobileVolunteerGroup(raw = {}) {
  const items = Array.isArray(raw.items) ? raw.items : Array.isArray(raw.volunteers) ? raw.volunteers : []
  const byNo = new Map(items.map((item) => [Number(item.volunteerNo), item]))
  const slots = [1, 2, 3].map((volunteerNo) => {
    const item = byNo.get(volunteerNo)
    if (!item) return emptySlot(volunteerNo)
    const p = item.position || item.positionSummary || {}
    return {
      volunteerNo,
      positionId: item.positionId ?? p.id ?? null,
      positionName: item.positionName || p.title || p.positionName || '',
      companyName: item.companyName || p.companyName || p.company?.name || '',
      workLocation: item.workLocation || p.workLocation || '',
      applicationStatement: String(item.applicationStatement || item.statement || ''),
      version: optionalVersion(item.version ?? item.applicationVersion)
    }
  })
  return {
    status: String(raw.status || raw.groupStatus || 'UNAVAILABLE').toUpperCase(),
    version: optionalVersion(raw.version ?? raw.groupVersion),
    recordVersion: optionalVersion(raw.recordVersion ?? raw.internshipRecordVersion),
    batchId: raw.batchId || null,
    internshipId: raw.internshipId || raw.recordId || null,
    lockedCompanyName: raw.lockedCompanyName || '',
    teacherConfirmDeadline: raw.teacherConfirmDeadline || '',
    slots
  }
}

export function canEditMobileVolunteers(group = {}) {
  return ['DRAFT', 'NEEDS_REVISION'].includes(String(group.status || '').toUpperCase())
}

export function addMobileVolunteer(slots, position) {
  const next = cloneSlots(slots)
  if (!position?.id) throw new Error('岗位信息无效')
  if (next.some((slot) => String(slot.positionId) === String(position.id))) return next
  const empty = next.find((slot) => !slot.positionId)
  if (!empty) throw new Error('三志愿已满，请先删除或替换一个志愿')
  Object.assign(empty, {
    positionId: position.id,
    positionName: position.title || position.positionName || '',
    companyName: position.companyName || '',
    workLocation: position.workLocation || '',
    applicationStatement: ''
  })
  return next
}

export function removeMobileVolunteer(slots, volunteerNo) {
  const active = cloneSlots(slots).filter((slot) => slot.positionId && slot.volunteerNo !== Number(volunteerNo))
    .map((slot, index) => ({ ...slot, volunteerNo: index + 1 }))
  while (active.length < 3) active.push(emptySlot(active.length + 1))
  return active
}

export function moveMobileVolunteer(slots, volunteerNo, direction) {
  const next = cloneSlots(slots)
  const from = Number(volunteerNo) - 1
  const to = direction === 'UP' ? from - 1 : from + 1
  if (from < 0 || from > 2 || to < 0 || to > 2 || !next[from]?.positionId || !next[to]?.positionId) return next
  const a = { ...next[from] }
  const b = { ...next[to] }
  next[from] = { ...b, volunteerNo: from + 1 }
  next[to] = { ...a, volunteerNo: to + 1 }
  return next
}

export function updateMobileStatement(slots, volunteerNo, statement) {
  const next = cloneSlots(slots)
  const index = Number(volunteerNo) - 1
  if (index >= 0 && index < 3) next[index].applicationStatement = String(statement || '')
  return next
}

export function buildMobileVolunteerSaveRequest(group, slots) {
  const allSlots = cloneSlots(slots)
  const active = allSlots.filter((slot) => slot.positionId)
  if (!active.length || active.length > 3) throw new Error('岗位志愿必须为 1–3 个')
  return {
    batchId: group.batchId,
    internshipId: group.internshipId,
    items: active.map((slot) => ({
      volunteerNo: slot.volunteerNo,
      positionId: slot.positionId,
      applicationStatement: slot.applicationStatement.trim()
    })),
    expectedGroupVersion: requireGroupVersion(group),
    expectedRecordVersion: requireVersion(group.recordVersion, '实习记录版本'),
    expectedApplicationVersions: Object.fromEntries(allSlots.map((slot) => [
      String(slot.volunteerNo),
      requireVersion(slot.version, `第${slot.volunteerNo}志愿版本`)
    ]))
  }
}

export function normalizeMobileMaterialPreview(raw = {}) {
  return {
    previewHash: String(raw.previewHash || raw.materialPreviewHash || ''),
    consentPolicyVersion: String(raw.consentPolicyVersion || raw.policyVersion || ''),
    profileVersion: optionalVersion(raw.profileVersion),
    maskedContact: String(raw.maskedContact || raw.contactPreview || '')
  }
}

export function buildMobileVolunteerSubmitRequest(group, preview, contactSharingMode = 'MASKED_ONLY') {
  const mode = CONTACT_MODES.includes(contactSharingMode) ? contactSharingMode : 'MASKED_ONLY'
  if (!preview.previewHash || !preview.consentPolicyVersion) throw new Error('请先确认企业视角投递材料')
  return {
    expectedGroupVersion: requireGroupVersion(group),
    expectedProfileVersion: requireVersion(preview.profileVersion, '实习档案版本'),
    consentPolicyVersion: preview.consentPolicyVersion,
    contactSharingMode: mode,
    confirmMaterialPreviewHash: preview.previewHash
  }
}
