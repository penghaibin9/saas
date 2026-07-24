/** 岗位实习业务选择器统一适配层。页面只声明实体与 query，不再自带搜索和响应映射。 */
import { internStudentApi } from '@/modules/internship/api/internship-student.api'
import { matchApi } from '@/modules/internship/api/match.api'
import { positionApi } from '@/modules/internship/api/position.api'
import { internshipApi } from '@/modules/internship/api/internship.api'

function rowsOf(response) {
  if (!response || response.code !== 0) throw new Error(response?.message || '选择器数据加载失败')
  const data = response.data
  return Array.isArray(data) ? data : (data?.list || data?.items || [])
}

function adapter(loader, map) {
  const search = async (keyword = '', query = {}) => rowsOf(await loader(keyword, query))
    .map((row) => map(row, query)).filter((item) => item.value !== '')
  const resolve = async (value, query = {}) => {
    const values = Array.isArray(value) ? value : [value]
    const options = await search('', query)
    const resolved = values.map((current) => options.find((item) => String(item.value) === String(current))).filter(Boolean)
    return Array.isArray(value) ? resolved : resolved[0]
  }
  return { search, resolve }
}

const candidateInternshipStudent = adapter(
  (keyword) => internStudentApi.getStudentOptions(keyword, 30),
  (row) => ({ value: row.id, label: row.name || '学生', desc: row.studentNo ? `学号 ${row.studentNo}` : '', raw: row })
)

const internshipStudent = adapter(
  (keyword, query) => internshipApi.getStudents({ ...query, keyword, page: 1, pageSize: 30, batchId: query.batchId }),
  (row) => ({ value: row.id, label: row.name || row.studentName || '实习学生', desc: [row.studentNo, row.className, row.enterpriseName].filter(Boolean).join(' · '), raw: row })
)

const unassignedInternshipStudent = adapter(
  (keyword, query) => matchApi.getStudentOptions(keyword, query.pageSize || 30, query.batchId),
  (row) => ({ value: row.id, label: row.name || row.studentName || '实习学生', desc: [row.studentNo, row.className, row.batchName].filter(Boolean).join(' · '), raw: row })
)

const internshipPosition = adapter(
  (keyword) => matchApi.getPositionOptions(keyword, 30),
  (row) => ({ value: row.id, label: row.title || '实习岗位', desc: [row.companyName, row.remaining != null ? `余 ${row.remaining}/${row.capacity || ''}` : ''].filter(Boolean).join(' · '), disabled: row.remaining === 0, raw: row })
)

const internshipEnterprise = adapter(
  (keyword) => positionApi.getEnterpriseOptions(keyword, 30),
  (row) => ({ value: row.id, label: row.name || '合作企业', desc: row.industry || '', raw: row })
)

const internshipAdvisor = adapter(
  (keyword) => internStudentApi.getAdvisors(keyword),
  (row) => ({ value: row.id, label: row.name || '校内指导教师', desc: row.loginName || row.employeeNo || '', raw: row })
)

const internshipBatch = adapter(
  (keyword, query) => internshipApi.getBatches({ ...query, keyword, page: 1, pageSize: 100 }),
  (row) => ({ value: row.id, label: row.batchName || '实习批次', desc: [row.batchNo, row.status].filter(Boolean).join(' · '), raw: row })
)

export async function loadInitialInternshipBatch() {
  const options = await internshipBatch.search('')
  return options[0]?.raw || null
}

const enterpriseMentor = adapter(
  async (keyword, query) => {
    if (!query.companyId) return { code: 0, data: [] }
    const response = await positionApi.getEnterpriseMentors(query.companyId)
    const rows = rowsOf(response).filter((row) => !keyword || `${row.name || ''}${row.contactName || ''}${row.phone || ''}`.toLowerCase().includes(String(keyword).toLowerCase()))
    return { code: 0, data: rows }
  },
  (row) => ({ value: row.id, label: row.name || row.contactName || '企业导师', desc: row.phone || row.position || '', raw: row })
)

export const internshipPickerAdapters = {
  candidateInternshipStudent,
  internshipStudent,
  unassignedInternshipStudent,
  internshipPosition,
  internshipEnterprise,
  internshipAdvisor,
  internshipBatch,
  enterpriseMentor
}
