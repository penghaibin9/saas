/** 课程库 / 培养方案 · 前端展示常量（与后端 course/program service 枚举一致）。 */

export const COURSE_CATEGORY = {
  PUBLIC_BASIC: '公共基础',
  DISCIPLINE_BASIC: '学科基础',
  MAJOR_CORE: '专业核心',
  MAJOR_ELECTIVE: '专业选修',
  PRACTICE: '实践环节'
}

export const COURSE_NATURE = {
  REQUIRED: '必修',
  ELECTIVE: '选修',
  LIMITED_ELECTIVE: '限选',
  PUBLIC_ELECTIVE: '公选'
}

export const EXAM_MODE = { EXAM: '考试', CHECK: '考查' }

/** 课程/方案共用的两级审核状态。 */
export const REVIEW_STATUS = {
  DRAFT: '草稿',
  COLLEGE_REVIEW: '学院审核中',
  ACADEMIC_REVIEW: '教务审核中',
  ENABLED: '已启用',
  PUBLISHED: '已发布',
  RETURNED: '已退回',
  DISABLED: '已停用'
}

export function reviewStatusColor(status) {
  switch (status) {
    case 'ENABLED':
    case 'PUBLISHED': return 'success'
    case 'RETURNED':
    case 'DISABLED': return 'warning'
    case 'COLLEGE_REVIEW':
    case 'ACADEMIC_REVIEW': return 'primary'
    default: return 'default'
  }
}

/** 是否处于可审核态（学院/教务审核环节）。 */
export function inReview(status) {
  return status === 'COLLEGE_REVIEW' || status === 'ACADEMIC_REVIEW'
}

/** 是否处于可提交态（编制/退回）。 */
export function canSubmit(status) {
  return status === 'DRAFT' || status === 'RETURNED'
}
