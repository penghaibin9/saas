import { TYPE_LABEL, STATUS_LABEL } from '../../constants/status-change.js'
import { COURSE_CATEGORY, COURSE_NATURE } from '../../constants/course-program.js'
import { WARNING_LEVEL, WARNING_SOURCE, WARNING_STATUS } from '../../constants/grade-graduation.js'
import { ACADEMIC_STATUS_LABELS } from '../../constants/academic-display.constants.js'

const labels = { ...ACADEMIC_STATUS_LABELS, ...STATUS_LABEL, ...TYPE_LABEL,
  ...COURSE_CATEGORY, ...COURSE_NATURE, ...WARNING_LEVEL, ...WARNING_SOURCE, ...WARNING_STATUS,
  makeup: '补考', retake: '重修', conflict: '冲突', UNKNOWN: '未分类',
  OPEN: '选课中', CLOSED: '已截止', LOCKED: '名单已锁定' }

export function statsGroupLabel(group) {
  if (typeof group?.label === 'string' && /[\u4e00-\u9fff]/.test(group.label)) return group.label
  const value = String(group?.key ?? '')
  return labels[value] || (/[\u4e00-\u9fff]/.test(value) || /^\d+(\.\d+)?$/.test(value) ? value : '未分类')
}

// 专题与异常明细的口径分别展示，不能把异常子集冒充总览指标的全部明细。
export const STATS_INDICATOR_TOPICS = Object.freeze({
  course: 'course', teachingTask: 'teachingTask', schedule: 'schedule',
  gradePublish: 'grade', failRate: 'grade', makeupRetake: 'grade',
  graduation: 'graduation', courseSelection: 'courseSelection', exam: 'exam', resource: 'resource'
})
