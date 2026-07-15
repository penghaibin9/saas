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
  FROZEN: '已冻结',
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
    case 'FROZEN': return 'info'
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

/** 实践环节类型（Tier1 R3：以周计的集中性实践教学环节）。 */
export const PRACTICE_SEGMENT_TYPE = {
  COGNITION_INTERNSHIP: '认识实习',
  COURSE_DESIGN: '课程设计',
  PRODUCTION_INTERNSHIP: '生产实习',
  POST_INTERNSHIP: '顶岗实习',
  GRADUATION_PROJECT: '毕业设计(论文)',
  MILITARY_TRAINING: '军训',
  SOCIAL_PRACTICE: '社会实践',
  OTHER: '其他'
}

/** 实践环节组织方式。 */
export const PRACTICE_ORG_MODE = { CENTRALIZED: '集中', DISTRIBUTED: '分散' }

/** 方案变更（状态生命周期）可选操作文案。 */
export const PROGRAM_CHANGE_ACTION = { FREEZE: '冻结', RESUME: '恢复', DISABLE: '停用' }

/** 方案变更：当前状态可执行的生命周期操作。 */
export function availableChangeActions(status) {
  if (status === 'PUBLISHED' || status === 'ENABLED') return ['FREEZE', 'DISABLE']
  if (status === 'FROZEN') return ['RESUME', 'DISABLE']
  return []
}

/** 方案归档：归档原因文案。 */
export const ARCHIVE_REASON_LABEL = { DISABLED: '已停用', SUPERSEDED: '已被新版本取代' }
