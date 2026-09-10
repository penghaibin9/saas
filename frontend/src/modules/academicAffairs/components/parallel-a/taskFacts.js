// Read every page before presenting task totals or confirming a command result.
// An incomplete/changing list must never become a successful empty result.
export function taskConfirmationEvidence(row = {}) {
  return JSON.stringify(['taskId', 'batchId', 'courseId', 'courseCode', 'courseName', 'classId', 'teachingClassId', 'teachingClassCode', 'teachingClassName', 'teacherId', 'teacherKey', 'teacherName', 'weeklyHours', 'totalHours', 'startWeek', 'endWeek', 'expectedStudents', 'isMerged', 'mergedIntoId'].map(key => String(row[key] ?? '')))
}

export async function readTaskPages(readPage, isCurrent = () => true) {
  const rows = []
  const ids = new Set()
  let total
  for (let page = 1; isCurrent(); page++) {
    const result = await readPage({ page, pageSize: 200 })
    if (!isCurrent()) return null
    if (result.code !== 0) return result
    const list = result.data?.list
    const count = Number(result.data?.total)
    if (!Array.isArray(list) || !Number.isInteger(count) || count < 0 || (total !== undefined && count !== total)) {
      return { code: 409001, message: '任务列表事实已变化或未完整返回，请刷新核对。' }
    }
    total = count
    for (const row of list) {
      const id = String(row.taskId || '')
      if (!id || ids.has(id)) return { code: 409001, message: '任务列表身份发生变化，请刷新核对。' }
      ids.add(id)
      rows.push(row)
    }
    if (rows.length === total) return { code: 0, data: { list: rows, total } }
    if (!list.length || rows.length > total) return { code: 409001, message: '任务列表未完整返回，请刷新核对。' }
  }
  return null
}
