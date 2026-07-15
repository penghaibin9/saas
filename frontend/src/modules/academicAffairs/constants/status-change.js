/**
 * 学籍异动 · 前端展示常量（与后端 academic_affairs_change_service.py 的 CHANGE_FLOW / 状态枚举一致）。
 * workflow 编码以后端 ACAD_* 为准，本文件只做中文展示映射，不参与业务判定。
 */
export const TYPE_LABEL = {
  SUSPEND: '休学',
  WITHDRAW: '退学',
  RESUME: '复学',
  RETAIN: '留级',
  TRANSFER_MAJOR: '转专业'
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
  TRANSFER_MAJOR: ['COUNSELOR_REVIEW', 'OUT_COLLEGE_REVIEW', 'IN_COLLEGE_REVIEW', 'AA_OFFICE_FINAL']
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

/** 分类申请入口路径段（Tier1 R1：休学/复学/退学/转专业四个独立三级菜单叶子，
 *  路由 /admin/academic-affairs/status-changes/<segment>）。仅覆盖本轮开工的四类；
 *  留级(RETAIN)不设分类入口，沿用「发起异动」通用页。 */
export const TYPE_PATH_SEGMENT = {
  SUSPEND: 'suspend',
  RESUME: 'resume',
  WITHDRAW: 'withdraw',
  TRANSFER_MAJOR: 'transfer-major'
}

/** 分类申请页标题/副标题（Tier1 R1 四个「申请入口」页文案）。 */
export const TYPE_PAGE_META = {
  SUSPEND: { title: '休学申请', subtitle: '在籍学生申请休学；到期日按规则中心最长年限自动计算，超期未复学应作退学处理' },
  RESUME: { title: '复学申请', subtitle: '休学中的学生申请复学；休学已超最长年限不可复学，应改办退学' },
  WITHDRAW: { title: '退学申请', subtitle: '退学为学籍终态，终审生效后不可再对该生发起其它学籍异动' },
  TRANSFER_MAJOR: { title: '转专业申请', subtitle: '需填写目标学院/专业/班级；终审生效后同步迁移学籍主档院系班' }
}
