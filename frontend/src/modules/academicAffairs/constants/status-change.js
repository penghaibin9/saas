/**
 * 学籍异动 · 前端展示常量（与后端 academic_affairs_change_service.py 的 CHANGE_FLOW / 状态枚举一致）。
 * workflow 编码以后端 ACAD_* 为准，本文件只做中文展示映射，不参与业务判定。
 */
export const TYPE_LABEL = {
  SUSPEND: '休学',
  WITHDRAW: '退学',
  RESUME: '复学',
  RETAIN: '留级',
  TRANSFER_MAJOR: '转专业',
  TRANSFER_CLASS: '转班'
}

export const STATUS_LABEL = {
  DRAFT: '草稿',
  SUBMITTED: '已提交',
  IN_REVIEW: '审批中',
  RETURNED: '已退回',
  REJECTED: '已驳回',
  EFFECTIVE: '已生效'
}

/** 审批节点编码 → 中文（CHANGE_FLOW 各类型的节点序列）。 */
export const NODE_LABEL = {
  COUNSELOR_REVIEW: '辅导员审核',
  COLLEGE_REVIEW: '学院审核',
  AA_OFFICE_FINAL: '教务处终审',
  COLLEGE_ASSIGN_CLASS: '学院分班',
  OUT_COLLEGE_REVIEW: '转出学院审核',
  IN_COLLEGE_REVIEW: '转入学院审核'
}

/** 各异动类型的审批节点序列（前端展示时间线用；权威仍在后端）。 */
export const CHANGE_FLOW_NODES = {
  SUSPEND: ['COUNSELOR_REVIEW', 'COLLEGE_REVIEW', 'AA_OFFICE_FINAL'],
  WITHDRAW: ['COUNSELOR_REVIEW', 'COLLEGE_REVIEW', 'AA_OFFICE_FINAL'],
  RESUME: ['COUNSELOR_REVIEW', 'COLLEGE_ASSIGN_CLASS', 'AA_OFFICE_FINAL'],
  RETAIN: ['COLLEGE_REVIEW', 'AA_OFFICE_FINAL'],
  TRANSFER_MAJOR: ['COUNSELOR_REVIEW', 'OUT_COLLEGE_REVIEW', 'IN_COLLEGE_REVIEW', 'AA_OFFICE_FINAL'],
  TRANSFER_CLASS: ['COUNSELOR_REVIEW', 'COLLEGE_REVIEW', 'AA_OFFICE_FINAL']
}

/** 状态 → AppStatusTag 语义色 */
export function statusColor(status) {
  switch (status) {
    case 'EFFECTIVE': return 'success'
    case 'REJECTED': return 'danger'
    case 'RETURNED': return 'warning'
    case 'IN_REVIEW':
    case 'SUBMITTED': return 'primary'
    default: return 'default'
  }
}

/** 是否可审批（在途）。 */
export function isActive(status) {
  return status === 'SUBMITTED' || status === 'IN_REVIEW' || status === 'DRAFT'
}

/** 分类申请入口路径段（Tier1 R1：休学/复学/退学/转专业；学籍异动三级模块续工补建：转班/留级，
 *  路由 /admin/academic-affairs/status-changes/<segment>）。 */
export const TYPE_PATH_SEGMENT = {
  SUSPEND: 'suspend',
  RESUME: 'resume',
  WITHDRAW: 'withdraw',
  TRANSFER_MAJOR: 'transfer-major',
  TRANSFER_CLASS: 'transfer-class',
  RETAIN: 'retain'
}

/** 分类申请页标题/副标题（Tier1 R1 四个 + 续工补建两个「申请入口」页文案）。 */
export const TYPE_PAGE_META = {
  SUSPEND: { title: '休学申请', subtitle: '在籍学生申请休学；到期日按规则中心最长年限自动计算，超期未复学应作退学处理' },
  RESUME: { title: '复学申请', subtitle: '休学中的学生申请复学；休学已超最长年限不可复学，应改办退学' },
  WITHDRAW: { title: '退学申请', subtitle: '退学为学籍终态，终审生效后不可再对该生发起其它学籍异动' },
  TRANSFER_MAJOR: { title: '转专业申请', subtitle: '需填写目标学院/专业/班级；终审生效后同步迁移学籍主档院系班' },
  TRANSFER_CLASS: { title: '转班申请', subtitle: '同专业换班（学院/专业不变，仅换班级）；跨专业请使用「转专业申请」' },
  // 甲方决策待确认：navPlan 原始占位文案为「保留学籍申请」，但项目冻结的学籍状态机（13B-教务中心状态机与
  // 权限矩阵.md SM-02，14 态）没有独立的「保留学籍」状态，唯一匹配的既有状态是 RETAINED（留级）。本页按
  // RETAIN/留级 实现并如实标注，如学校实际所指是参军/创业/病休等区别于「留级」的独立保留学籍政策
  // （SM-02 未覆盖的第 15 类状态），需另行确认业务规则（适用条件/最长年限/是否计在籍）后再单独设计。
  RETAIN: { title: '留级申请（保留学籍）', subtitle: '学业成绩条件命中的留级认定；如需参军/创业/病休等「保留学籍」政策请见页内说明' }
}
