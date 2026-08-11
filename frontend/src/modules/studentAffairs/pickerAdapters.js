/**
 * 学工中心业务选择器统一数据适配层。
 * 页面只声明业务实体；搜索、回显和数据范围均收敛在这里及后端接口。
 */
import { studentAffairsApi } from '@/modules/studentAffairs/api/studentAffairs.api'
import { assessmentApi } from '@/modules/studentAffairs/api/class.api'
import { createOrgPickerAdapters, createTeacherPickerAdapter } from '@/components/common/picker/orgAdapters'
import { safeEnumLabel } from '@/utils/presentationSafety'

const STATUS_LABELS = Object.freeze({
  DRAFT: '草稿', ACTIVE: '进行中', INACTIVE: '已停用', OPEN: '开放中', CLOSED: '已结束',
  PENDING: '待处理', PENDING_REVIEW: '待审核', APPROVED: '已通过', REJECTED: '已驳回',
  COMPLETED: '已完成', ARCHIVED: '已归档', VACANT: '空床', OCCUPIED: '已入住'
})
const PROJECT_TYPE_LABELS = Object.freeze({
  SCHOLARSHIP: '奖学金', GRANT: '助学金', WORK_STUDY: '勤工助学',
  LOAN: '助学贷款', TUITION_REDUCTION: '学费减免', TEMPORARY_AID: '临时补助'
})

function statusLabel(value) {
  return value ? safeEnumLabel({ value, dictionary: STATUS_LABELS, unknownLabel: '状态待确认' }) : ''
}

function projectTypeLabel(value) {
  return value ? safeEnumLabel({ value, dictionary: PROJECT_TYPE_LABELS, unknownLabel: '项目类型待确认' }) : ''
}

export function safeEntityOption({ value, label, desc = '', raw }) {
  const missingLabel = !String(label || '').trim() || /#\s*\d+/.test(String(label || ''))
  return {
    value: String(value || ''),
    label: missingLabel ? '名称待同步' : String(label),
    desc,
    disabled: missingLabel,
    invalidReason: missingLabel ? '名称尚未同步，请刷新后重试或联系管理员' : '',
    raw
  }
}

function assertOk(response) {
  if (!response || response.code !== 0) throw new Error(response?.message || '选择器数据加载失败')
  return response.data
}

function rowsOf(response) {
  const data = assertOk(response)
  if (Array.isArray(data)) return data
  return data?.items || data?.list || []
}

function firstDefined(row, keys, fallback = '') {
  for (const key of keys) {
    if (row?.[key] !== undefined && row?.[key] !== null && row?.[key] !== '') return row[key]
  }
  return fallback
}

function matches(row, keyword, fields) {
  const text = fields.map((field) => row?.[field] || '').join(' ').toLowerCase()
  return !keyword || text.includes(keyword.toLowerCase())
}

function entityAdapter(loader, config) {
  const search = async (keyword = '', query = {}) => {
    const rows = await loader(keyword, query)
    return rows.map((row) => safeEntityOption({
      value: firstDefined(row, config.value),
      label: config.label(row),
      desc: config.desc ? config.desc(row) : '',
      raw: row
    })).filter((item) => item.value)
  }
  const resolve = async (value, query = {}) => {
    const values = Array.isArray(value) ? value : [value]
    const options = await search('', query)
    const resolved = values.map((current) => options.find((item) => String(item.value) === String(current))).filter(Boolean)
    return Array.isArray(value) ? resolved : resolved[0]
  }
  return { search, resolve }
}

function optionAdapter(loader) {
  const search = async (keyword = '') => loader(keyword)
  const resolve = async (value) => {
    const values = Array.isArray(value) ? value : [value]
    const options = await search('')
    const resolved = values.map((current) => options.find((item) => String(item.value) === String(current))).filter(Boolean)
    return Array.isArray(value) ? resolved : resolved[0]
  }
  return { search, resolve }
}

const student = optionAdapter((keyword) => studentAffairsApi.searchStudents(keyword))
const riskOwner = optionAdapter((keyword) => studentAffairsApi.searchRiskOwners(keyword))

const aidBatch = entityAdapter(async (keyword) => {
  const rows = rowsOf(await studentAffairsApi.getAidBatches({ page: 1, pageSize: 100 }))
  return rows.filter((row) => matches(row, keyword, ['batchName', 'schoolYear', 'status']))
}, {
  value: ['batchId', 'id'],
  label: (row) => row.batchName,
  desc: (row) => [row.schoolYear, statusLabel(row.status)].filter(Boolean).join(' · ')
})

const fundingProject = entityAdapter(async (keyword) => {
  const rows = rowsOf(await studentAffairsApi.getFundingProjects({ page: 1, pageSize: 100 }))
  return rows.filter((row) => matches(row, keyword, ['projectName', 'projectType', 'status']))
}, {
  value: ['projectId', 'id'], label: (row) => row.projectName,
  desc: (row) => [projectTypeLabel(row.projectType), statusLabel(row.status)].filter(Boolean).join(' · ')
})

const fundingBatch = entityAdapter(async (keyword, query) => {
  const rows = rowsOf(await studentAffairsApi.getFundingBatches({ projectId: query.projectId || '', page: 1, pageSize: 100 }))
  return rows.filter((row) => matches(row, keyword, ['schoolYear', 'projectName', 'projectType', 'status']))
}, {
  value: ['batchId', 'id'], label: (row) => `${row.schoolYear || '未设学年'} · ${row.projectName || row.projectType || '资助批次'}`,
  desc: (row) => statusLabel(row.status)
})

const studentArchiveBatch = entityAdapter(async (keyword) => {
  const rows = rowsOf(await studentAffairsApi.getArchiveBatches({ page: 1, pageSize: 100 }))
  return rows.filter((row) => matches(row, keyword, ['batchName', 'yearCode', 'status']))
}, {
  value: ['batchId', 'id'], label: (row) => row.batchName,
  desc: (row) => [row.yearCode, statusLabel(row.status)].filter(Boolean).join(' · ')
})

const counselorAssessmentPeriod = entityAdapter(async (keyword) => {
  const rows = rowsOf(await assessmentApi.periods({ page: 1, pageSize: 100 }))
  return rows.filter((row) => matches(row, keyword, ['periodName', 'statusLabel', 'status']))
}, {
  value: ['id', 'periodId'], label: (row) => row.periodName,
  desc: (row) => row.statusLabel || statusLabel(row.status)
})

const dormBuilding = entityAdapter(async (keyword, query) => {
  const rows = rowsOf(await studentAffairsApi.getBuildings({ gender: query.gender || '', page: 1, pageSize: 100 }))
  return rows.filter((row) => matches(row, keyword, ['buildingName', 'buildingCode']))
}, {
  value: ['buildingId', 'id'], label: (row) => row.buildingName,
  desc: (row) => row.vacantBeds != null ? `空床 ${row.vacantBeds}` : ''
})

const dormRoom = entityAdapter(async (keyword, query) => {
  if (!query.buildingId) return []
  const rows = rowsOf(await studentAffairsApi.getRooms(query.buildingId, { page: 1, pageSize: 200 }))
  return rows.filter((row) => matches(row, keyword, ['roomNo', 'roomName', 'floor']))
}, {
  value: ['roomId', 'id'], label: (row) => row.roomNo || row.roomName,
  desc: (row) => [row.floor ? `${row.floor} 层` : '', row.vacantBeds != null ? `空床 ${row.vacantBeds}` : ''].filter(Boolean).join(' · ')
})

const dormBed = entityAdapter(async (keyword, query) => {
  if (!query.roomId) return []
  const rows = rowsOf(await studentAffairsApi.getBeds(query.roomId))
  return rows.filter((row) => (!query.vacantOnly || row.status === 'VACANT') && matches(row, keyword, ['bedNo', 'status']))
}, {
  value: ['bedId', 'id'], label: (row) => row.bedNo ? `${row.bedNo} 号床` : '',
  desc: (row) => statusLabel(row.status)
})

export const studentAffairsPickerAdapters = {
  // 学院/专业/班级/年级走公共组织适配器（数据源 /directory/org-tree，按本人数据范围裁剪）；
  // 不在本模块另写一份，避免各中心口径分裂
  ...createOrgPickerAdapters(),
  // 学工此前没有 teacher 适配器，AppTeacherPicker 放上去是空下拉；
  // 辅导员责任分配等页面因此只能让用户手填用户 ID
  teacher: createTeacherPickerAdapter(),
  student,
  riskOwner,
  aidBatch,
  fundingProject,
  fundingBatch,
  studentArchiveBatch,
  counselorAssessmentPeriod,
  dormBuilding,
  dormRoom,
  dormBed
}
