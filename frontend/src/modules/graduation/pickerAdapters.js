/**
 * 毕业设计中心业务选择器统一适配层。
 *
 * 页面只描述要选择的业务对象和筛选条件；查询、回显及响应结构转换集中在这里。
 * 后端仍负责数据范围、资格与回避规则，前端不扩大可见数据范围。
 */
import { gdStudentApi } from '@/modules/graduation/api/graduation-student.api'
import { graduationMentorApi } from '@/modules/graduation/api/graduation-mentor.api'
import { graduationBatchApi } from '@/modules/graduation/api/graduation-batch.api'
import { gdTopicApi } from '@/modules/graduation/api/graduation-topic.api'
import { createOrgPickerAdapters } from '@/components/common/picker/orgAdapters'

function assertOk(response) {
  if (!response || response.code !== 0) throw new Error(response?.message || '选择器数据加载失败')
  return response.data
}

function rowsOf(response) {
  const data = assertOk(response)
  return Array.isArray(data) ? data : (data?.list || data?.items || [])
}

function contains(row, keyword, keys) {
  const text = keys.map((key) => row?.[key] || '').join(' ').toLowerCase()
  return !keyword || text.includes(String(keyword).toLowerCase())
}

function adapter(loader, map) {
  const search = async (keyword = '', query = {}) => rowsOf(await loader(keyword, query)).map((row) => map(row, query)).filter((item) => item.value !== '')
  const resolve = async (value, query = {}) => {
    const values = Array.isArray(value) ? value : [value]
    const options = await search('', query)
    const resolved = values.map((current) => options.find((item) => String(item.value) === String(current))).filter(Boolean)
    return Array.isArray(value) ? resolved : resolved[0]
  }
  return { search, resolve }
}

const candidateStudent = adapter(
  (keyword) => gdStudentApi.getStudentOptions(keyword),
  (row) => ({ value: row.id, label: `${row.name || '学生'} · ${row.studentNo || '无学号'}`, raw: row })
)

const graduationStudent = adapter(
  (keyword, query) => gdStudentApi.getStudents({ ...query, keyword, page: 1, pageSize: 30 }),
  (row, query) => ({
    value: row.id,
    label: `${row.name || row.studentName || '学生'} · ${row.studentNo || '无学号'}`,
    desc: [row.className, row.topicTitle].filter(Boolean).join(' · '),
    disabled: !!query.excludeStudentId && String(row.id) === String(query.excludeStudentId), raw: row
  })
)

function mentorOption(row, query = {}) {
  const isExcludedByName = !!query.excludeTeacherName && row.teacherName === query.excludeTeacherName
  const isExcludedById = !!query.excludeMentorId && String(row.id) === String(query.excludeMentorId)
  return {
    value: query.valueMode === 'id' ? row.id : row.teacherName,
    label: row.teacherName || '导师',
    desc: [row.teacherNo, row.capacityText || row.collegeName].filter(Boolean).join(' · ') || '',
    disabled: isExcludedByName || isExcludedById,
    raw: row
  }
}

const graduationMentor = adapter(
  (keyword, query) => graduationMentorApi.getMentors({
    ...query, keyword, page: 1, pageSize: 30,
    valueMode: undefined, excludeTeacherName: undefined, excludeMentorId: undefined,
  }),
  (row, query) => mentorOption(row, query)
)

const availableMentor = adapter(
  (keyword, query) => graduationMentorApi.getMentors({ ...query, keyword, qualificationStatus: 'QUALIFIED', hasCapacity: 'true', page: 1, pageSize: 30 }),
  (row) => mentorOption(row, { valueMode: 'id' })
)

const graduationBatch = adapter(
  (keyword, query) => graduationBatchApi.getBatches({ ...query, keyword, page: 1, pageSize: 100 }),
  (row) => ({ value: row.id, label: row.batchName || '毕业设计批次', desc: [row.batchNo, row.status].filter(Boolean).join(' · '), raw: row })
)

const graduationTopic = adapter(
  async (keyword, query) => {
    const response = await gdTopicApi.getTopics({
      reviewStatus: 'APPROVED', status: 'CONFIRMED', isFull: false, archiveView: 'active',
      ...query, keyword, page: 1, pageSize: 50
    })
    return { code: response.code, message: response.message, data: rowsOf(response).filter((row) => contains(row, keyword, ['title', 'advisorName', 'topicNo'])) }
  },
  (row) => ({
    value: row.id, label: row.title || '毕业设计题目',
    desc: [row.advisorName, row.remaining != null ? `余 ${row.remaining}` : ''].filter(Boolean).join(' · '),
    disabled: row.remaining != null && row.remaining <= 0, raw: row
  })
)

const defenseGroup = adapter(
  async (keyword, query) => {
    const response = await gdStudentApi.getDefenseGroups()
    const groups = rowsOf(response).filter((row) => contains(row, keyword, ['groupName', 'defenseDate', 'location']))
    return { code: 0, data: groups.filter((row) => !query.publishedOnly || row.published) }
  },
  (row) => ({
    value: row.id, label: row.groupName || '答辩组',
    desc: [row.defenseDate, row.location, row.studentCount != null ? `${row.studentCount} 人` : ''].filter(Boolean).join(' · '), raw: row
  })
)

export const graduationPickerAdapters = {
  // 学院/专业/班级/年级走公共组织适配器（数据源 /directory/org-tree，按本人数据范围裁剪）；
  // 不在本模块另写一份，避免各中心口径分裂
  ...createOrgPickerAdapters(),
  candidateStudent,
  graduationStudent,
  graduationMentor,
  availableMentor,
  graduationBatch,
  graduationTopic,
  defenseGroup
}
