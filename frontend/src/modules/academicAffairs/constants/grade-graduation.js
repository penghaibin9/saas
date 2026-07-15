/** 成绩 / 预警 / 毕业预审 · 前端展示常量（与后端 grade/warning/graduation service 一致）。 */

export const PASS_STATUS = { PASSED: '及格', FAIL: '不及格' }

export const WARNING_LEVEL = { LOW: '一般', MEDIUM: '中度', HIGH: '严重' }
export function warningColor(level) {
  switch (level) {
    case 'HIGH': return 'danger'
    case 'MEDIUM': return 'warning'
    default: return 'default'
  }
}

/** 预警来源（13B-教务中心状态机与权限矩阵.md §13）；EXAM_FAIL 为历史内部编码，展示统一为「挂科预警」。 */
export const WARNING_SOURCE = {
  EXAM_FAIL: '挂科预警',
  CREDIT_SHORT: '学分预警',
  LOW_GPA: '绩点预警',
  RETAKE_EXCESS: '补考重修预警',
  GRAD_ABNORMAL: '毕业风险预警'
}
export const WARNING_STATUS = { PENDING_HANDLE: '待处理', PROCESSING: '跟进中', ESCALATED: '已升级', CLOSED: '已关闭' }
export function warningStatusColor(status) {
  switch (status) {
    case 'PENDING_HANDLE': return 'danger'
    case 'PROCESSING': return 'warning'
    case 'ESCALATED': return 'warning'
    case 'CLOSED': return 'default'
    default: return 'default'
  }
}

/** 毕业资格审核十项供数编码 → 中文（顺序对齐后端 _run_items）。 */
export const GRAD_ITEM_LABEL = {
  STATUS: '学籍状态',
  CREDIT: '学分达成',
  COURSE_REQUIRED: '必修课程',
  COURSE_ELECTIVE: '选修课程',
  PRACTICE: '实践环节',
  INTERNSHIP: '岗位实习',
  GRADUATION_DESIGN: '毕业设计',
  DISCIPLINE: '违纪处分',
  EMPLOYMENT: '就业去向',
  ARCHIVE: '迎新归档'
}

/** 「课程达成审核」叶子覆盖的两项（必修全通过 + 选修学分达标）。 */
export const COURSE_ITEMS = ['COURSE_REQUIRED', 'COURSE_ELECTIVE']

/** 状态联动三项 → 责任模块跳转路由前缀（resultId 详情内 refId 拼接，供「毕设/实习/处分状态联动」页跳转）。 */
export const GRAD_LINK_ITEM = {
  GRADUATION_DESIGN: { label: '毕业设计', routeName: null, hint: '在毕业设计中心查看该生选题/答辩结论' },
  INTERNSHIP: { label: '岗位实习', routeName: null, hint: '在岗位实习中心查看该生实习记录' },
  DISCIPLINE: { label: '违纪处分', routeName: null, hint: '在学工中心查看该生处分明细（按权限脱敏）' }
}

/** 三态：PASS/FAIL/UNKNOWN。UNKNOWN 灰色，明确区别于 FAIL。 */
export const GRAD_ITEM_RESULT = { PASS: '通过', FAIL: '不通过', UNKNOWN: '缺数据' }
export function gradItemColor(result) {
  switch (result) {
    case 'PASS': return 'success'
    case 'FAIL': return 'danger'
    default: return 'default'
  }
}

export const OVERALL_LABEL = { SYSTEM_PASSED: '系统通过', SYSTEM_ABNORMAL: '系统异常' }
export function overallColor(overall) {
  return overall === 'SYSTEM_PASSED' ? 'success' : 'warning'
}

export const CONCLUSION_LABEL = { GRADUATED: '毕业', COMPLETED: '结业', DELAYED: '延毕' }

export const GRAD_STATUS_LABEL = {
  WAIT_PRECHECK: '待预审',
  SYSTEM_PASSED: '系统通过',
  SYSTEM_ABNORMAL: '系统异常',
  COLLEGE_REVIEW: '学院初审中',
  ACADEMIC_REVIEW: '教务终审中',
  REJECTED: '学院已退回',
  GRADUATED: '已定：毕业',
  COMPLETED: '已定：结业',
  DELAYED: '已定：延毕',
  ARCHIVED: '已归档'
}

/** 「不通过原因」叶子覆盖的三类不通过状态 → 分组标题（顺序即页面分组顺序）。
 * REJECTED 提示刻意不写"重新提交"：当前 college_review/precheck 均不接受 REJECTED 状态的结果重新进入
 * 复核队列（无重置/重跑入口），如需再审只能并入学校下一次新批次，是真实的现状而非文案疏漏。 */
export const GRAD_FAIL_GROUPS = [
  { status: 'SYSTEM_ABNORMAL', title: '系统判定异常（待学院初审）', hint: '十项供数命中不通过项，尚未进入人工复核' },
  { status: 'REJECTED', title: '学院初审退回', hint: '学院教务员核实后退回并填写原因；本批次内不支持再次提交，如需重审需并入学校下一批次' },
  { status: 'DELAYED', title: '教务终审：延毕', hint: '教务处终审已判定本届不具备毕业条件，滚入下一批次' }
]
