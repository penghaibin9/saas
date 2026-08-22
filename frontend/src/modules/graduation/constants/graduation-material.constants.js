import { safeEnumLabel } from '../../../utils/presentationSafety.js'

/**
 * 毕业设计材料中心展示字典。
 *
 * 后端与查询参数继续使用稳定英文枚举；界面只展示中文，未知新枚举也不得把技术码
 * 直接暴露给学校用户。
 */
export const GD_MATERIAL_STAGES = Object.freeze([
  { value: 'TOPIC', label: '选题材料' },
  { value: 'TASKBOOK', label: '任务书' },
  { value: 'PROPOSAL', label: '开题报告' },
  { value: 'GUIDANCE', label: '指导记录' },
  { value: 'MIDTERM', label: '中期检查' },
  { value: 'FINAL_DRAFT', label: '成果初稿' },
  { value: 'FINAL_APPROVED', label: '成果定稿' },
  { value: 'PLAGIARISM', label: '查重报告' },
  { value: 'REVIEW', label: '评阅材料' },
  { value: 'DEFENSE', label: '答辩材料' },
  { value: 'GRADE', label: '成绩材料' },
  { value: 'ARCHIVE', label: '归档材料' }
])

export const GD_MATERIAL_STAGE_LABELS = Object.freeze(
  Object.fromEntries(GD_MATERIAL_STAGES.map((item) => [item.value, item.label]))
)

export const GD_SCAN_STATUS_LABELS = Object.freeze({
  NOT_SUBMITTED: '未提交',
  MISSING: '未提交',
  CLEAN: '安全',
  PASSED: '安全',
  READY: '安全可用',
  PENDING: '待扫描',
  UPLOADED: '已上传，待扫描',
  SCANNING: '扫描中',
  ERROR: '扫描失败',
  FAILED: '扫描失败',
  INFECTED: '检测到安全风险',
  ABNORMAL: '安全异常',
  NOT_REQUIRED: '无需扫描'
})

export const GD_REVIEW_STATUS_LABELS = Object.freeze({
  NOT_SUBMITTED: '未提交',
  MISSING: '未提交',
  DRAFT: '草稿',
  PENDING: '待审核',
  PENDING_REVIEW: '待审核',
  REVIEWING: '审核中',
  RETURNED: '已退回',
  REJECTED: '已驳回',
  APPROVED: '已通过',
  SUBMITTED: '已提交',
  NOT_REQUIRED: '无需审核'
})

export const GD_ARCHIVE_STATUS_LABELS = Object.freeze({
  NOT_ARCHIVED: '未归档',
  ELIGIBLE: '可归档',
  FROZEN: '已冻结',
  ARCHIVED: '已归档',
  SUPERSEDED: '已被新版本替代'
})

export const GD_FILE_VERSION_STATUS_LABELS = Object.freeze({
  UPLOADED: '已上传',
  SCANNING: '扫描中',
  READY: '安全可用',
  SUBMITTED: '已提交',
  APPROVED: '已通过',
  REJECTED: '已驳回',
  RETURNED: '已退回',
  INVALIDATED: '已失效',
  ARCHIVED: '已归档'
})

export const GD_PLAGIARISM_STATUS_LABELS = Object.freeze({
  CHECKING: '检测中',
  DONE: '已完成',
  FAILED: '检测失败',
  PASSED: '已通过',
  OVER_THRESHOLD: '重复率超标',
  NOT_CHECKED: '未检测'
})

export const GD_MENTOR_STATUS_LABELS = Object.freeze({
  ACTIVE: '正常',
  QUALIFIED: '已认证',
  CERTIFIED: '已认证',
  PENDING: '待认证',
  UNQUALIFIED: '未认证',
  DISABLED: '已停用',
  ARCHIVED: '已归档'
})

function label(value, dictionary, unknownLabel) {
  const raw = String(value ?? '').trim()
  if (/[一-鿿]/.test(raw)) return raw
  return safeEnumLabel({ value, dictionary, unknownLabel })
}

export const graduationMaterialStageLabel = (value) => label(value, GD_MATERIAL_STAGE_LABELS, '其他材料阶段')
export const graduationScanStatusLabel = (value) => label(value, GD_SCAN_STATUS_LABELS, '扫描状态待确认')
export const graduationReviewStatusLabel = (value) => label(value, GD_REVIEW_STATUS_LABELS, '审核状态待确认')
export const graduationArchiveStatusLabel = (value) => label(value, GD_ARCHIVE_STATUS_LABELS, '归档状态待确认')
export const graduationFileVersionStatusLabel = (value) => label(value, GD_FILE_VERSION_STATUS_LABELS, '文件状态待确认')
export const graduationPlagiarismStatusLabel = (value) => label(value, GD_PLAGIARISM_STATUS_LABELS, '查重状态待确认')
export const graduationMentorStatusLabel = (value) => label(value, GD_MENTOR_STATUS_LABELS, '导师状态待确认')
