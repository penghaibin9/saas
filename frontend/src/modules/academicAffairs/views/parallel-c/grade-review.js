export function gradeStatusLabel(status) {
  return ({ NOT_STARTED: '未开始', INPUTTING: '录入中', SUBMITTED: '待学院审核', COLLEGE_REVIEW: '学院审核中',
    ACADEMIC_REVIEW: '待教务终审', PUBLISHED: '已正式发布', RETURNED: '已退回', ARCHIVED: '已归档' })[status] || '状态待确认'
}

export function gradeQueueState(query = {}) {
  const states = ['', 'NOT_STARTED', 'INPUTTING', 'RETURNED', 'SUBMITTED', 'COLLEGE_REVIEW', 'ACADEMIC_REVIEW', 'PUBLISHED', 'ARCHIVED']
  const scalar = key => typeof query[key] === 'string' ? query[key].trim() : ''
  const status = scalar('status'), term = scalar('term'), keyword = scalar('keyword')
  const page = Number(scalar('page'))
  const invalid = ['status', 'term', 'keyword', 'page'].some(key => query[key] != null && typeof query[key] !== 'string')
  return { status, term, keyword, page: Number.isInteger(page) && page > 0 && page <= 1000000 ? page : 1,
    error: invalid || !states.includes(status) || term.length > 50 || keyword.length > 100 ? '查询条件无效，请清除筛选后重新查询。' : '' }
}

// The server owns allowedActions. Navigation does not grant permission or change state.
export function gradeTaskDestination(row = {}) {
  const actions = row.allowedActions || []
  if (row.status === 'ACADEMIC_REVIEW' && actions.includes('PUBLISH')) return { page: 'grade-publish', tab: 'ACADEMIC_REVIEW', label: '终审并发布' }
  if (row.status === 'SUBMITTED' && actions.includes('COLLEGE_REVIEW')) return { page: 'grade-college-review', label: '审核成绩' }
  if (['PUBLISHED', 'ARCHIVED'].includes(row.status)) return { page: 'grade-entry', label: '查看正式成绩' }
  if (actions.includes('INPUT')) return { page: 'grade-entry', label: row.status === 'RETURNED' ? '修改并重交' : '录入成绩' }
  return { page: 'grade-entry', label: '查看任务进度' }
}

export function gradeError(result, fallback = '读取失败，请重试') {
  if (result?.bizCode === 'TERM_ARCHIVED') return '该学期已归档封存，本次未调整成绩；请按学校受控纠错流程办理。'
  const code = [result?.httpStatus, result?.code, result?.bizCode].join(' ')
  if (/403|NO_DATA_SCOPE|NO_PERMISSION|FORBIDDEN/.test(code)) return '当前身份无权办理此任务，请返回责任队列。'
  if (/404|NOT_FOUND/.test(code)) return '任务不存在或已不在当前数据范围，请返回责任队列。'
  if (/400|409|422|CONFLICT|STALE|TERM_ARCHIVED/.test(code)) {
    const message = typeof result?.message === 'string'
      // eslint-disable-next-line no-control-regex -- 剔除服务端消息中的控制字符后再展示。
      ? result.message.replace(/[\u0000-\u001f\u007f]/g, ' ').trim().slice(0, 200)
      : ''
    return message || '任务已变化，请重新读取并核对后办理。'
  }
  return fallback
}
