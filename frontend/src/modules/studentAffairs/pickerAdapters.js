/**
 * 学工中心业务选择器统一数据适配层。
 * 页面只声明业务实体；搜索、回显和数据范围均收敛在这里及后端接口。
 */
import { studentAffairsApi } from '@/modules/studentAffairs/api/studentAffairs.api'
import { assessmentApi } from '@/modules/studentAffairs/api/class.api'

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
    return rows.map((row) => ({
      value: String(firstDefined(row, config.value)),
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
  label: (row) => row.batchName || `认定批次 #${firstDefined(row, ['batchId', 'id'])}`,
  desc: (row) => [row.schoolYear, row.status].filter(Boolean).join(' · ')
})

const fundingProject = entityAdapter(async (keyword) => {
  const rows = rowsOf(await studentAffairsApi.getFundingProjects({ page: 1, pageSize: 100 }))
  return rows.filter((row) => matches(row, keyword, ['projectName', 'projectType', 'status']))
}, {
  value: ['projectId', 'id'], label: (row) => row.projectName || `资助项目 #${firstDefined(row, ['projectId', 'id'])}`,
  desc: (row) => [row.projectType, row.status].filter(Boolean).join(' · ')
})

const fundingBatch = entityAdapter(async (keyword, query) => {
  const rows = rowsOf(await studentAffairsApi.getFundingBatches({ projectId: query.projectId || '', page: 1, pageSize: 100 }))
  return rows.filter((row) => matches(row, keyword, ['schoolYear', 'projectName', 'projectType', 'status']))
}, {
  value: ['batchId', 'id'], label: (row) => `${row.schoolYear || '未设学年'} · ${row.projectName || row.projectType || '资助批次'}`,
  desc: (row) => row.status || ''
})

const studentArchiveBatch = entityAdapter(async (keyword) => {
  const rows = rowsOf(await studentAffairsApi.getArchiveBatches({ page: 1, pageSize: 100 }))
  return rows.filter((row) => matches(row, keyword, ['batchName', 'yearCode', 'status']))
}, {
  value: ['batchId', 'id'], label: (row) => row.batchName || `归档批次 #${firstDefined(row, ['batchId', 'id'])}`,
  desc: (row) => [row.yearCode, row.status].filter(Boolean).join(' · ')
})

const counselorAssessmentPeriod = entityAdapter(async (keyword) => {
  const rows = rowsOf(await assessmentApi.periods({ page: 1, pageSize: 100 }))
  return rows.filter((row) => matches(row, keyword, ['periodName', 'statusLabel', 'status']))
}, {
  value: ['id', 'periodId'], label: (row) => row.periodName || `考评周期 #${firstDefined(row, ['id', 'periodId'])}`,
  desc: (row) => row.statusLabel || row.status || ''
})

const dormBuilding = entityAdapter(async (keyword, query) => {
  const rows = rowsOf(await studentAffairsApi.getBuildings({ gender: query.gender || '', page: 1, pageSize: 100 }))
  return rows.filter((row) => matches(row, keyword, ['buildingName', 'buildingCode']))
}, {
  value: ['buildingId', 'id'], label: (row) => row.buildingName || `楼栋 #${firstDefined(row, ['buildingId', 'id'])}`,
  desc: (row) => row.vacantBeds != null ? `空床 ${row.vacantBeds}` : ''
})

const dormRoom = entityAdapter(async (keyword, query) => {
  if (!query.buildingId) return []
  const rows = rowsOf(await studentAffairsApi.getRooms(query.buildingId, { page: 1, pageSize: 200 }))
  return rows.filter((row) => matches(row, keyword, ['roomNo', 'roomName', 'floor']))
}, {
  value: ['roomId', 'id'], label: (row) => row.roomNo || row.roomName || `房间 #${firstDefined(row, ['roomId', 'id'])}`,
  desc: (row) => [row.floor ? `${row.floor} 层` : '', row.vacantBeds != null ? `空床 ${row.vacantBeds}` : ''].filter(Boolean).join(' · ')
})

const dormBed = entityAdapter(async (keyword, query) => {
  if (!query.roomId) return []
  const rows = rowsOf(await studentAffairsApi.getBeds(query.roomId))
  return rows.filter((row) => (!query.vacantOnly || row.status === 'VACANT') && matches(row, keyword, ['bedNo', 'status']))
}, {
  value: ['bedId', 'id'], label: (row) => `${row.bedNo || firstDefined(row, ['bedId', 'id'])} 号床`,
  desc: (row) => row.status === 'VACANT' ? '空床' : (row.status || '')
})

export const studentAffairsPickerAdapters = {
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
