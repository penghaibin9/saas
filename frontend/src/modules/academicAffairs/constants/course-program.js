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

/** 毕业要求分类（知识/能力/素质/职业证书）。 */
export const GRADUATION_REQUIREMENT_CATEGORY = {
  KNOWLEDGE: '知识要求',
  ABILITY: '能力要求',
  QUALITY: '素质要求',
  CERTIFICATE: '职业证书'
}

/** 是否处于可新建版本态（已发布/启用/冻结/停用，编制/退回态直接编辑无需新建版本）。 */
export function canNewVersion(status) {
  return ['PUBLISHED', 'ENABLED', 'FROZEN', 'DISABLED'].includes(status)
}

/** 是否处于可发布绑定态（已发布/已启用）。 */
export function canPublishBind(status) {
  return status === 'PUBLISHED' || status === 'ENABLED'
}

/** 课程模块文本是否属于集中实践/实训/实习环节（教学计划「实践教学计划」叶子的筛选口径，
 * 与 COURSE_CATEGORY.PRACTICE 标签「实践环节」保持一致；module 为编制期自由文本，按关键词命中）。 */
export function isPracticeModule(module) {
  return !!module && /实践|实训|实习/.test(module)
}
