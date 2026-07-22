/**
 * 教务中心业务选择器统一数据适配层。
 *
 * 页面只声明“选择什么”，不再各自实现搜索、返回结构转换和编辑态回显。
 * 后端仍负责租户、权限与数据范围；这里不扩大任何可见范围。
 */
import {
  academicAffairsApi,
  academicAffairsOrgApi,
  academicAffairsLabApi,
  academicAffairsEquipmentApi,
  academicAffairsExamApi,
  academicAffairsSelectionApi,
  academicAffairsMakeupApi,
  academicAffairsArchiveApi
} from '@/modules/academicAffairs/api/academic-affairs.api'

function assertOk(res) {
  if (!res || res.code !== 0) throw new Error(res?.message || '选择器数据加载失败')
  return res.data
}

function listOf(res) {
  const data = assertOk(res)
  if (Array.isArray(data)) return data
  return data?.list || data?.items || []
}

function firstDefined(row, keys, fallback = '') {
  for (const key of keys) {
    if (row?.[key] !== undefined && row?.[key] !== null && row?.[key] !== '') return row[key]
  }
  return fallback
}

function option(row, config) {
  const value = typeof config.value === 'function' ? config.value(row) : firstDefined(row, config.value)
  const label = config.label(row)
  return { value, label, desc: config.desc ? config.desc(row) : '', raw: row }
}

function searchable(loader, config) {
  const search = async (keyword = '', query = {}) => {
    const rows = listOf(await loader(keyword, query))
    return rows.map((row) => option(row, config)).filter((item) => item.value !== '')
  }
  const resolve = async (value, query = {}) => {
    const values = Array.isArray(value) ? value : [value]
    const found = []
    for (const current of values) {
      let rows = await search('', { ...query, resolveValue: current })
      let matched = rows.find((item) => String(item.value) === String(current))
      if (!matched) {
        rows = await search(String(current), { ...query, resolveValue: current })
        matched = rows.find((item) => String(item.value) === String(current))
      }
      found.push(matched)
    }
    const clean = found.filter(Boolean)
    return Array.isArray(value) ? clean : clean[0]
  }
  return { search, resolve }
}

const student = searchable(
  (keyword, query) => academicAffairsApi.getRoster({ ...query, resolveValue: undefined, keyword, page: 1, pageSize: 30 }),
  {
    value: ['studentId', 'id'],
    label: (s) => `${firstDefined(s, ['realName', 'studentName', 'name'], '学生')} · ${firstDefined(s, ['studentNo', 'studentCode'], '无学号')}`,
    desc: (s) => [s.collegeName, s.majorName, s.className].filter(Boolean).join(' · ')
  }
)

const teacher = searchable(
  (keyword) => academicAffairsApi.searchCourseTeachers(keyword),
  {
    value: ['value', 'teacherId', 'userId', 'teacherKey', 'id'],
    label: (t) => firstDefined(t, ['label', 'teacherName', 'realName', 'name'], '教师'),
    desc: (t) => firstDefined(t, ['desc', 'teacherNo', 'teacherKey', 'employeeNo', 'collegeName'])
  }
)

const college = searchable(
  (keyword, query) => academicAffairsOrgApi.listColleges({ ...query, resolveValue: undefined, keyword, page: 1, pageSize: 100 }),
  { value: ['id', 'collegeId'], label: (x) => firstDefined(x, ['collegeName', 'name']), desc: (x) => x.collegeCode || '' }
)

const major = searchable(
  (keyword, query) => academicAffairsOrgApi.listMajors({ ...query, resolveValue: undefined, keyword, page: 1, pageSize: 200 }),
  {
    value: ['id', 'majorId'],
    label: (x) => firstDefined(x, ['majorName', 'name']),
    desc: (x) => [x.collegeName, x.majorCode].filter(Boolean).join(' · ')
  }
)

const klass = searchable(
  (keyword, query) => academicAffairsOrgApi.listClasses({ ...query, resolveValue: undefined, keyword, page: 1, pageSize: 200 }),
  {
    value: ['id', 'classId'],
    label: (x) => firstDefined(x, ['className', 'name']),
    desc: (x) => [x.grade, x.majorName, x.collegeName].filter(Boolean).join(' · ')
  }
)

const course = searchable(
  (keyword, query) => academicAffairsApi.getCourses({ status: 'ENABLED', ...query, resolveValue: undefined, keyword, page: 1, pageSize: 50 }),
  {
    value: ['courseId', 'id'],
    label: (x) => firstDefined(x, ['courseName', 'name']),
    desc: (x) => [x.courseCode, x.credit != null ? `${x.credit} 学分` : ''].filter(Boolean).join(' · ')
  }
)

const termEntity = searchable(
  (keyword, query) => academicAffairsApi.getTerms({ ...query, resolveValue: undefined, keyword, page: 1, pageSize: 100 }),
  {
    value: ['termId', 'id'],
    label: (x) => x.termName || `${x.yearCode || ''} 第${x.termNo || ''}学期`,
    desc: (x) => [x.isCurrent ? '当前学期' : '', x.status].filter(Boolean).join(' · ')
  }
)

const termCode = searchable(
  (keyword, query) => academicAffairsApi.getTerms({ ...query, resolveValue: undefined, keyword, page: 1, pageSize: 100 }),
  {
    value: (x) => x.termCode || (x.yearCode && x.termNo ? `${x.yearCode}-${x.termNo}` : ''),
    label: (x) => x.termName || `${x.yearCode || ''} 第${x.termNo || ''}学期`,
    desc: (x) => [x.isCurrent ? '当前学期' : '', x.status].filter(Boolean).join(' · ')
  }
)

/** 供既要选择学期、又要读取学期状态/周数的页面复用同一数据入口。 */
export async function loadAcademicTermCatalog(query = {}) {
  const options = await termEntity.search('', query)
  return options.map((item) => item.raw)
}

/** 仅需要当前学期标识的页面不再自行调用接口和解析响应。 */
export async function loadCurrentAcademicTerm() {
  return assertOk(await academicAffairsApi.getCurrentTerm())
}

const teachingTask = searchable(
  (keyword, query) => academicAffairsApi.listAllTasks({ ...query, resolveValue: undefined, keyword, page: 1, pageSize: 50 }),
  {
    value: ['taskId', 'teachingTaskId', 'id'],
    label: (x) => firstDefined(x, ['courseName', 'taskName'], '教学任务'),
    desc: (x) => [x.className, x.teacherName, x.termName, x.taskCode].filter(Boolean).join(' · ')
  }
)

const teachingClass = searchable(
  (keyword, query) => academicAffairsOrgApi.listTeachingClasses({ ...query, resolveValue: undefined, keyword, page: 1, pageSize: 100 }),
  {
    value: ['teachingClassCode', 'teachingClassId', 'id'],
    label: (x) => firstDefined(x, ['teachingClassName', 'className', 'courseName']),
    desc: (x) => [x.courseName, x.teacherName].filter(Boolean).join(' · ')
  }
)

const classroom = searchable(
  (keyword) => academicAffairsApi.getClassroomOptions(keyword),
  {
    value: ['classroomId', 'id', 'value'],
    label: (x) => firstDefined(x, ['label', 'roomName'], `${x.buildingName || ''}${x.roomCode || ''}`),
    desc: (x) => [x.campusName, x.capacity ? `${x.capacity} 人` : ''].filter(Boolean).join(' · ')
  }
)

const lab = searchable(
  (keyword) => academicAffairsLabApi.options(keyword),
  {
    value: ['labId', 'id', 'value'],
    label: (x) => firstDefined(x, ['label', 'labName', 'name']),
    desc: (x) => x.capacity ? `${x.capacity} 工位` : ''
  }
)

const equipment = searchable(
  (keyword, query) => academicAffairsEquipmentApi.list({ ...query, resolveValue: undefined, keyword, page: 1, pageSize: 100 }),
  {
    value: ['equipmentId', 'id'],
    label: (x) => firstDefined(x, ['equipmentName', 'name'], '设备'),
    desc: (x) => [x.equipmentCode, x.specModel, x.status].filter(Boolean).join(' · ')
  }
)

const timeSlot = searchable(
  async (keyword, query) => {
    const res = await academicAffairsApi.getTimeSlots(query.includeDisabled !== false)
    if (res.code !== 0) return res
    const rows = Array.isArray(res.data) ? res.data : (res.data?.items || [])
    const k = String(keyword || '').toLowerCase()
    return {
      code: 0,
      data: rows.filter((x) => !k || `${x.slotNo || ''}${x.slotName || ''}`.toLowerCase().includes(k))
    }
  },
  {
    value: ['slotId', 'id'],
    label: (x) => `第 ${x.slotNo || '—'} 节${x.slotName ? ` · ${x.slotName}` : ''}`,
    desc: (x) => [x.startTime && x.endTime ? `${x.startTime}-${x.endTime}` : '', x.status].filter(Boolean).join(' · ')
  }
)

const scheduleBatch = searchable(
  (keyword, query) => academicAffairsApi.getScheduleBatches({ ...query, resolveValue: undefined, keyword, page: 1, pageSize: 100 }),
  {
    value: ['batchId', 'id'], label: (x) => firstDefined(x, ['batchName', 'name']),
    desc: (x) => [x.termName, x.status].filter(Boolean).join(' · ')
  }
)

const gradeTask = searchable(
  (keyword, query) => academicAffairsApi.getGradeTasks({ ...query, resolveValue: undefined, keyword, page: 1, pageSize: 100 }),
  {
    value: ['taskId', 'gradeTaskId', 'id'], label: (x) => firstDefined(x, ['courseName', 'taskName'], '成绩任务'),
    desc: (x) => [x.className, x.termCode, x.status].filter(Boolean).join(' · ')
  }
)

const gradeRecord = searchable(
  async (keyword, query) => {
    if (!query.taskId) return { code: 0, data: [] }
    const res = await academicAffairsApi.getGradeRecords(query.taskId)
    if (res.code !== 0) return res
    const rows = Array.isArray(res.data) ? res.data : (res.data?.items || [])
    const k = String(keyword || '').toLowerCase()
    return { code: 0, data: rows.filter((x) => !k || `${x.realName || x.studentName || ''}${x.studentNo || ''}`.toLowerCase().includes(k)) }
  },
  {
    value: ['recordId', 'gradeRecordId', 'id'], label: (x) => `${firstDefined(x, ['realName', 'studentName'], '学生')} · ${x.studentNo || '无学号'}`,
    desc: (x) => x.totalScore != null ? `当前成绩 ${x.totalScore}` : ''
  }
)

const graduationBatch = searchable(
  (keyword, query) => academicAffairsApi.listGradBatches({ ...query, resolveValue: undefined, keyword, page: 1, pageSize: 100 }),
  { value: ['batchId', 'id'], label: (x) => firstDefined(x, ['batchName', 'name']), desc: (x) => x.status || '' }
)

const registrationBatch = searchable(
  (keyword, query) => academicAffairsApi.getRegistrationBatches({ ...query, resolveValue: undefined, keyword, page: 1, pageSize: 100 }),
  { value: ['batchId', 'id'], label: (x) => firstDefined(x, ['batchName', 'name']), desc: (x) => x.status || '' }
)

const examBatch = searchable(
  (keyword, query) => academicAffairsExamApi.listBatches({ ...query, resolveValue: undefined, keyword, page: 1, pageSize: 100 }),
  { value: ['batchId', 'id'], label: (x) => firstDefined(x, ['batchName', 'name']), desc: (x) => x.status || '' }
)

const program = searchable(
  (keyword, query) => academicAffairsApi.getPrograms({ ...query, resolveValue: undefined, keyword, page: 1, pageSize: 100 }),
  {
    value: ['programId', 'id'], label: (x) => firstDefined(x, ['programName', 'name'], '培养方案'),
    desc: (x) => [x.majorName, x.gradeYear, x.versionNo ? `V${x.versionNo}` : '', x.status].filter(Boolean).join(' · ')
  }
)

const selectionBatch = searchable(
  (keyword, query) => academicAffairsSelectionApi.listBatches({ ...query, resolveValue: undefined, keyword, page: 1, pageSize: 100 }),
  { value: ['batchId', 'id'], label: (x) => firstDefined(x, ['batchName', 'name']), desc: (x) => [x.termName, x.status].filter(Boolean).join(' · ') }
)

const makeupBatch = searchable(
  (keyword, query) => academicAffairsMakeupApi.listBatches({ ...query, resolveValue: undefined, keyword, page: 1, pageSize: 100 }),
  { value: ['batchId', 'id'], label: (x) => firstDefined(x, ['batchName', 'name']), desc: (x) => [x.termCode, x.status].filter(Boolean).join(' · ') }
)

const archiveBatch = searchable(
  (keyword, query) => academicAffairsArchiveApi.listBatches({ ...query, resolveValue: undefined, keyword, page: 1, pageSize: 100 }),
  { value: ['batchId', 'id'], label: (x) => firstDefined(x, ['batchName', 'name'], '归档批次'), desc: (x) => [x.termName, x.status].filter(Boolean).join(' · ') }
)

function normalizeOrgNode(node, level = 0) {
  const value = firstDefined(node, ['value', 'id', level === 0 ? 'collegeId' : level === 1 ? 'majorId' : 'classId'])
  const label = firstDefined(node, ['label', 'name', level === 0 ? 'collegeName' : level === 1 ? 'majorName' : 'className'])
  return { value, label, children: (node.children || []).map((child) => normalizeOrgNode(child, level + 1)) }
}

const orgCascade = {
  async load() {
    const data = assertOk(await academicAffairsOrgApi.orgTree())
    const rows = Array.isArray(data) ? data : (data?.items || data?.tree || [])
    return rows.map((row) => normalizeOrgNode(row))
  }
}

export const academicAffairsPickerAdapters = {
  student,
  teacher,
  mentor: teacher,
  college,
  major,
  class: klass,
  course,
  termEntity,
  termCode,
  teachingTask,
  teachingClass,
  classroom,
  lab,
  equipment,
  timeSlot,
  scheduleBatch,
  gradeTask,
  gradeRecord,
  graduationBatch,
  registrationBatch,
  examBatch,
  program,
  selectionBatch,
  makeupBatch,
  archiveBatch,
  orgCascade
}
