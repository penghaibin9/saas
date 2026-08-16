import { POSITION_MATCH_STATES } from './selectionContract.js'

const MATCH_LABELS = Object.freeze({
  MATCHED: '专业匹配',
  UNLIMITED: '不限专业',
  UNKNOWN: '匹配待确认',
  POSSIBLE_MISMATCH: '可能不匹配'
})

function valueOf(raw, ...keys) {
  for (const key of keys) {
    if (raw?.[key] !== undefined && raw?.[key] !== null && raw?.[key] !== '') return raw[key]
  }
  return null
}

function yesNo(value, yes = '是', no = '否') {
  if (value === true || value === 1 || value === 'true') return yes
  if (value === false || value === 0 || value === 'false') return no
  return '待确认'
}

export function normalizePosition(raw = {}) {
  const matchStateRaw = String(valueOf(raw, 'matchState', 'majorMatchState', 'eligibilityMatch') || 'UNKNOWN').toUpperCase()
  const matchState = POSITION_MATCH_STATES.includes(matchStateRaw) ? matchStateRaw : 'UNKNOWN'
  const company = raw.company || {}
  const rights = raw.rights || raw.laborConditions || {}

  return {
    id: valueOf(raw, 'id', 'positionId'),
    title: valueOf(raw, 'title', 'positionName') || '岗位名称待完善',
    remuneration: valueOf(raw, 'remunerationDisplay', 'salaryRange', 'remuneration') || '薪酬待确认',
    companyId: valueOf(raw, 'companyId') ?? company.id ?? null,
    companyName: valueOf(raw, 'companyName') || company.name || '企业信息待完善',
    companyVerified: Boolean(valueOf(raw, 'schoolVerified', 'companyVerified') ?? company.schoolVerified),
    workLocation: valueOf(raw, 'workLocation', 'address', 'city') || '地点待定',
    majors: raw.majors || raw.majorNames || [],
    grades: raw.grades || raw.gradeNames || [],
    accommodation: valueOf(raw, 'accommodationProvided') ?? rights.accommodationProvided,
    meal: valueOf(raw, 'mealProvided') ?? rights.mealProvided,
    benefits: raw.benefitTags || raw.rightsTags || [],
    remaining: Number(valueOf(raw, 'remaining', 'remainingQuota', 'remainingCount') ?? 0),
    publishedAt: valueOf(raw, 'publishedAt', 'publishTime') || '',
    matchState,
    matchLabel: MATCH_LABELS[matchState],
    description: valueOf(raw, 'description', 'jobDescription') || '',
    requirements: valueOf(raw, 'requirements', 'requirementText') || '',
    dailyHours: valueOf(raw, 'dailyHours') ?? rights.dailyHours,
    weeklyHours: valueOf(raw, 'weeklyHours') ?? rights.weeklyHours,
    shift: valueOf(raw, 'shift', 'shiftType') ?? rights.shift,
    nightShift: valueOf(raw, 'nightShift') ?? rights.nightShift,
    overtime: valueOf(raw, 'overtime', 'overtimePolicy') ?? rights.overtime,
    restDays: valueOf(raw, 'restDays', 'restDayPolicy') ?? rights.restDays,
    subsidy: valueOf(raw, 'subsidy', 'subsidyDisplay') ?? rights.subsidy,
    hazardous: valueOf(raw, 'hazardous', 'hazardousExposure') ?? rights.hazardous,
    equipment: valueOf(raw, 'equipment', 'protectiveEquipment') ?? rights.equipment,
    industry: valueOf(raw, 'industry') || company.industry || '',
    companyNature: valueOf(raw, 'companyNature') || company.nature || '',
    companyScale: valueOf(raw, 'companyScale') || company.scale || '',
    companyIntro: valueOf(raw, 'companyIntro') || company.shortIntro || ''
  }
}

export function conditionRows(position) {
  return [
    ['每日工时', position.dailyHours ?? '待确认'],
    ['每周工时', position.weeklyHours ?? '待确认'],
    ['班次', position.shift || '待确认'],
    ['夜班', yesNo(position.nightShift, '有', '无')],
    ['加班安排', position.overtime || '待确认'],
    ['休息日', position.restDays || '待确认'],
    ['岗位薪酬', position.remuneration || '待确认'],
    ['补贴', position.subsidy || '待确认'],
    ['住宿', yesNo(position.accommodation, '提供', '不提供')],
    ['餐食', yesNo(position.meal, '提供', '不提供')],
    ['危险因素', position.hazardous || '无明确危险因素说明'],
    ['劳动防护/设备', position.equipment || '待企业/学校确认']
  ]
}

export function formatPublishedAt(value) {
  if (!value) return '发布时间待定'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return String(value)
  return new Intl.DateTimeFormat('zh-CN', { month: '2-digit', day: '2-digit' }).format(date)
}
