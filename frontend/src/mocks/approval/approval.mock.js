/**
 * 审批中心 mock 数据（待办/审批闭环，区别于 /admin/workflow 权限与流程中心）。
 * 与 mocks/internship 保持同一世界观（演示职业技术学院 / 赵一凡 / 刘强 / 李敏 / 华信智能 / 星辰网络）。
 * 页面禁止直接 import 本文件，必须经 modules/approval/api 获取。
 * 时间口径：剧本内“今日”= 07-03（todoSummary.todayTag），运行期写操作时间统一记“刚刚”。
 */

export const tenantBrandConfig = {
  tenantId: 'tenant-demo-a',
  schoolName: '演示职业技术学院',
  platformDisplayName: '高校学生全生命周期管理平台',
  schoolLogo: '',
  schoolBadge: '',
  brandColor: '#2563eb',
  watermarkText: '演示职业技术学院 · 内部数据'
}

/**
 * 权限动作基线（学院管理员全量）。
 * allowed=false 且 visible=true：按钮置灰并提示 reason；visible=false：入口不渲染。
 */
export const permissionActions = {
  approveTask: { visible: true, allowed: true, reason: '' },
  returnTask: { visible: true, allowed: true, reason: '' },
  transferTask: { visible: true, allowed: true, reason: '' },
  batchApprove: { visible: true, allowed: true, reason: '' },
  batchReturn: { visible: true, allowed: true, reason: '' },
  batchTransfer: { visible: true, allowed: true, reason: '' },
  exportRecords: { visible: true, allowed: true, reason: '导出默认脱敏并加水印，写入审计日志' },
  viewTemplates: { visible: true, allowed: true, reason: '' },
  createTemplate: { visible: true, allowed: true, reason: '' },
  editTemplate: { visible: true, allowed: true, reason: '' },
  voidTemplate: { visible: true, allowed: true, reason: '' },
  exportTemplates: { visible: true, allowed: true, reason: '' },
  viewAuditLog: { visible: true, allowed: true, reason: '' }
}

/**
 * 五个演示角色档案：currentRole / dataScope / 待办业务范围 / 权限动作。
 * 差异设计：仅学院管理员可管理审批模板；辅导员不能批量转交；
 * 指导教师不能批量退回；教务/就业老师不能批量通过（须逐份复核）。
 */
export const roleProfiles = {
  COLLEGE_ADMIN: {
    currentRole: { userId: 'u-wjg', userName: '王建国', roleCode: 'COLLEGE_ADMIN', roleName: '学院管理员' },
    dataScope: { scopeCode: 'COLLEGE_ALL', scopeName: '信息工程学院 · 全部审批事项' },
    todoBizTypes: [
      'STATUS_CHANGE',
      'INFO_CORRECT',
      'INTERN_APPLY',
      'INTERN_REPORT',
      'THESIS_TOPIC',
      'EMPLOY_AGREEMENT',
      'LEAVE'
    ],
    permissionActions: { ...permissionActions }
  },
  COUNSELOR: {
    currentRole: { userId: 'u-lm', userName: '李敏', roleCode: 'COUNSELOR', roleName: '辅导员' },
    dataScope: { scopeCode: 'MY_CLASSES', scopeName: '所带班级（软件2301 / 软件2302）' },
    todoBizTypes: ['LEAVE', 'STATUS_CHANGE', 'INFO_CORRECT'],
    permissionActions: {
      ...permissionActions,
      batchTransfer: { visible: true, allowed: false, reason: '批量转交需「学院管理员」角色' },
      viewTemplates: { visible: true, allowed: false, reason: '审批模板管理需「学院管理员」角色' },
      createTemplate: { visible: false, allowed: false, reason: '模板管理入口仅学院管理员可见' },
      editTemplate: { visible: false, allowed: false, reason: '模板管理入口仅学院管理员可见' },
      voidTemplate: { visible: false, allowed: false, reason: '模板管理入口仅学院管理员可见' },
      exportTemplates: { visible: false, allowed: false, reason: '模板导出仅学院管理员可见' }
    }
  },
  ADVISOR: {
    currentRole: { userId: 'u-lq', userName: '刘强', roleCode: 'ADVISOR', roleName: '指导教师' },
    dataScope: { scopeCode: 'MY_STUDENTS', scopeName: '本人指导的实习/毕设学生（8 人）' },
    todoBizTypes: ['INTERN_APPLY', 'INTERN_REPORT', 'THESIS_TOPIC'],
    permissionActions: {
      ...permissionActions,
      batchReturn: { visible: true, allowed: false, reason: '批量退回需逐单说明整改要求，请进入详情逐条退回' },
      batchTransfer: { visible: true, allowed: false, reason: '批量转交需「学院管理员」角色' },
      viewTemplates: { visible: true, allowed: false, reason: '审批模板管理需「学院管理员」角色' },
      createTemplate: { visible: false, allowed: false, reason: '模板管理入口仅学院管理员可见' },
      editTemplate: { visible: false, allowed: false, reason: '模板管理入口仅学院管理员可见' },
      voidTemplate: { visible: false, allowed: false, reason: '模板管理入口仅学院管理员可见' },
      exportTemplates: { visible: false, allowed: false, reason: '模板导出仅学院管理员可见' }
    }
  },
  ACADEMIC: {
    currentRole: { userId: 'u-cj', userName: '陈静', roleCode: 'ACADEMIC', roleName: '教务老师' },
    dataScope: { scopeCode: 'SCHOOL_TEACHING', scopeName: '全校 · 教学口径审批' },
    todoBizTypes: ['STATUS_CHANGE', 'INFO_CORRECT', 'LEAVE'],
    permissionActions: {
      ...permissionActions,
      batchApprove: { visible: true, allowed: false, reason: '学籍与信息类审批须逐份复核，不支持批量通过' },
      batchTransfer: { visible: true, allowed: false, reason: '批量转交需「学院管理员」角色' },
      createTemplate: { visible: true, allowed: false, reason: '模板管理需「学院管理员」角色' },
      editTemplate: { visible: true, allowed: false, reason: '模板管理需「学院管理员」角色' },
      voidTemplate: { visible: true, allowed: false, reason: '模板管理需「学院管理员」角色' }
    }
  },
  EMPLOYMENT: {
    currentRole: { userId: 'u-sl', userName: '孙丽', roleCode: 'EMPLOYMENT', roleName: '就业老师' },
    dataScope: { scopeCode: 'SCHOOL_EMPLOY', scopeName: '全校 · 就业口径审批' },
    todoBizTypes: ['EMPLOY_AGREEMENT', 'INTERN_APPLY'],
    permissionActions: {
      ...permissionActions,
      batchApprove: { visible: true, allowed: false, reason: '就业协议需逐份核对签章信息，不支持批量通过' },
      batchTransfer: { visible: true, allowed: false, reason: '批量转交需「学院管理员」角色' },
      viewTemplates: { visible: true, allowed: false, reason: '审批模板管理需「学院管理员」角色' },
      createTemplate: { visible: false, allowed: false, reason: '模板管理入口仅学院管理员可见' },
      editTemplate: { visible: false, allowed: false, reason: '模板管理入口仅学院管理员可见' },
      voidTemplate: { visible: false, allowed: false, reason: '模板管理入口仅学院管理员可见' },
      exportTemplates: { visible: false, allowed: false, reason: '模板导出仅学院管理员可见' }
    }
  }
}

export const statusOptions = {
  taskStatus: [
    { value: 'PENDING_REVIEW', label: '待审批' },
    { value: 'APPROVED', label: '已通过' },
    { value: 'RETURNED', label: '已退回' }
  ],
  urgency: [
    { value: 'NORMAL', label: '正常' },
    { value: 'URGENT', label: '临期' },
    { value: 'OVERDUE', label: '已超时' }
  ],
  rectifyStatus: [
    { value: 'PENDING_RESUBMIT', label: '待整改重报' },
    { value: 'RESUBMITTED', label: '已重新提交' },
    { value: 'CLOSED', label: '已关闭' }
  ],
  templateStatus: [
    { value: 'ENABLED', label: '启用中' },
    { value: 'VOIDED', label: '已作废' }
  ],
  ccReadStatus: [
    { value: 'UNREAD', label: '未读' },
    { value: 'READ', label: '已读' }
  ]
}

export const filterOptions = {
  bizTypes: [
    { value: 'STATUS_CHANGE', label: '学籍异动' },
    { value: 'INFO_CORRECT', label: '信息更正' },
    { value: 'INTERN_APPLY', label: '实习申请' },
    { value: 'INTERN_REPORT', label: '实习周报' },
    { value: 'THESIS_TOPIC', label: '毕设选题' },
    { value: 'EMPLOY_AGREEMENT', label: '就业协议' },
    { value: 'LEAVE', label: '请假申请' }
  ],
  urgencies: [
    { value: 'NORMAL', label: '正常' },
    { value: 'URGENT', label: '临期' },
    { value: 'OVERDUE', label: '已超时' }
  ],
  doneResults: [
    { value: 'APPROVED', label: '已通过' },
    { value: 'RETURNED', label: '已退回' }
  ],
  rectifyStatuses: [
    { value: 'PENDING_RESUBMIT', label: '待整改重报' },
    { value: 'RESUBMITTED', label: '已重新提交' },
    { value: 'CLOSED', label: '已关闭' }
  ],
  templateStatuses: [
    { value: 'ENABLED', label: '启用中' },
    { value: 'VOIDED', label: '已作废' }
  ],
  templateNodeRoles: [
    { value: 'COUNSELOR', label: '辅导员' },
    { value: 'ADVISOR', label: '指导教师' },
    { value: 'ACADEMIC', label: '教务老师' },
    { value: 'EMPLOYMENT', label: '就业老师' },
    { value: 'COLLEGE_ADMIN', label: '学院管理员' }
  ]
}

/** 批量动作字典（页面按钮文案与确认语从此取，权限由 permissionActions 控制） */
export const batchActions = [
  { key: 'batchApprove', label: '批量通过', confirmText: '确认通过' },
  { key: 'batchReturn', label: '批量退回', confirmText: '确认退回' },
  { key: 'batchTransfer', label: '批量转交', confirmText: '确认转交' }
]

/** 待办统计快照（api 按当前角色实时重算，todayTag 为剧本“今日”口径） */
export const todoSummary = {
  todayTag: '07-03',
  total: 14,
  todayNew: 3,
  nearDeadline: 5,
  overdue: 3,
  byBizType: [
    { bizType: 'STATUS_CHANGE', label: '学籍异动', count: 2, earliest: '06-28 09:12' },
    { bizType: 'INFO_CORRECT', label: '信息更正', count: 2, earliest: '07-01 10:18' },
    { bizType: 'INTERN_APPLY', label: '实习申请', count: 2, earliest: '07-01 16:40' },
    { bizType: 'INTERN_REPORT', label: '实习周报', count: 2, earliest: '07-01 08:02' },
    { bizType: 'THESIS_TOPIC', label: '毕设选题', count: 2, earliest: '07-02 09:55' },
    { bizType: 'EMPLOY_AGREEMENT', label: '就业协议', count: 2, earliest: '07-01 15:22' },
    { bizType: 'LEAVE', label: '请假申请', count: 2, earliest: '06-30 08:20' }
  ]
}

/**
 * 审批任务池：ap-0xx 为在办待办（12+ 条，覆盖 7 类业务），ap-1xx 为已办结历史件
 * （供已办/抄送/退回列表回看详情，不进入待办队列）。
 */
export const approvalList = [
  {
    taskId: 'ap-001', bizType: 'STATUS_CHANGE', bizTypeLabel: '学籍异动',
    title: '休学申请（因病休学一学期）',
    applicant: { name: '赵一凡', studentNo: 'S2026-000001', className: '软件2301' },
    submitTime: '06-28 09:12', deadline: '07-02 18:00', urgency: 'OVERDUE', urgencyLabel: '已超时',
    status: 'PENDING_REVIEW', statusLabel: '待审批', currentNode: '学院审批', transferred: false
  },
  {
    taskId: 'ap-002', bizType: 'STATUS_CHANGE', bizTypeLabel: '学籍异动',
    title: '转专业申请（软件技术 → 大数据技术）',
    applicant: { name: '孙一诺', studentNo: 'S2026-000008', className: '软件2302' },
    submitTime: '07-01 14:26', deadline: '07-05 18:00', urgency: 'URGENT', urgencyLabel: '临期',
    status: 'PENDING_REVIEW', statusLabel: '待审批', currentNode: '教务复核', transferred: false
  },
  {
    taskId: 'ap-003', bizType: 'INFO_CORRECT', bizTypeLabel: '信息更正',
    title: '联系电话更正申请',
    applicant: { name: '何雨珊', studentNo: 'S2026-000012', className: '软件2301' },
    submitTime: '07-03 09:40', deadline: '07-07 18:00', urgency: 'NORMAL', urgencyLabel: '正常',
    status: 'PENDING_REVIEW', statusLabel: '待审批', currentNode: '辅导员核验', transferred: false
  },
  {
    taskId: 'ap-004', bizType: 'INFO_CORRECT', bizTypeLabel: '信息更正',
    title: '身份证件信息更正申请',
    applicant: { name: '陈志远', studentNo: 'S2026-000007', className: '软件2302' },
    submitTime: '07-01 10:18', deadline: '07-04 18:00', urgency: 'URGENT', urgencyLabel: '临期',
    status: 'PENDING_REVIEW', statusLabel: '待审批', currentNode: '教务复核', transferred: false
  },
  {
    taskId: 'ap-005', bizType: 'INTERN_APPLY', bizTypeLabel: '实习申请',
    title: '实习申请（华信智能 · 前端开发实习生）',
    applicant: { name: '吴俊杰', studentNo: 'S2026-000010', className: '软件2301' },
    submitTime: '07-02 11:05', deadline: '07-06 18:00', urgency: 'NORMAL', urgencyLabel: '正常',
    status: 'PENDING_REVIEW', statusLabel: '待审批', currentNode: '指导教师审核', transferred: false
  },
  {
    taskId: 'ap-006', bizType: 'INTERN_APPLY', bizTypeLabel: '实习申请',
    title: '实习单位变更申请（转入星辰网络）',
    applicant: { name: '郑浩然', studentNo: 'S2026-000011', className: '软件2302' },
    submitTime: '07-01 16:40', deadline: '07-04 12:00', urgency: 'URGENT', urgencyLabel: '临期',
    status: 'PENDING_REVIEW', statusLabel: '待审批', currentNode: '指导教师审核', transferred: false
  },
  {
    taskId: 'ap-007', bizType: 'INTERN_REPORT', bizTypeLabel: '实习周报',
    title: '实习周报批阅（第 3 周 · v2 重交）',
    applicant: { name: '赵一凡', studentNo: 'S2026-000001', className: '软件2301' },
    submitTime: '07-01 08:02', deadline: '07-02 18:00', urgency: 'OVERDUE', urgencyLabel: '已超时',
    status: 'PENDING_REVIEW', statusLabel: '待审批', currentNode: '指导教师批阅', transferred: false
  },
  {
    taskId: 'ap-008', bizType: 'INTERN_REPORT', bizTypeLabel: '实习周报',
    title: '实习周报批阅（第 4 周）',
    applicant: { name: '林晓彤', studentNo: 'S2026-000006', className: '软件2301' },
    submitTime: '07-03 08:15', deadline: '07-07 18:00', urgency: 'NORMAL', urgencyLabel: '正常',
    status: 'PENDING_REVIEW', statusLabel: '待审批', currentNode: '指导教师批阅', transferred: false
  },
  {
    taskId: 'ap-009', bizType: 'THESIS_TOPIC', bizTypeLabel: '毕设选题',
    title: '毕设选题申报《基于小程序的实习打卡系统设计》',
    applicant: { name: '周雨萌', studentNo: 'S2026-000009', className: '软件2301' },
    submitTime: '07-02 19:30', deadline: '07-08 18:00', urgency: 'NORMAL', urgencyLabel: '正常',
    status: 'PENDING_REVIEW', statusLabel: '待审批', currentNode: '指导教师审核', transferred: false
  },
  {
    taskId: 'ap-010', bizType: 'THESIS_TOPIC', bizTypeLabel: '毕设选题',
    title: '毕设选题变更申请（原题目难度超出实习岗位范围）',
    applicant: { name: '吴俊杰', studentNo: 'S2026-000010', className: '软件2301' },
    submitTime: '07-02 09:55', deadline: '07-05 12:00', urgency: 'URGENT', urgencyLabel: '临期',
    status: 'PENDING_REVIEW', statusLabel: '待审批', currentNode: '教研室复核', transferred: false
  },
  {
    taskId: 'ap-011', bizType: 'EMPLOY_AGREEMENT', bizTypeLabel: '就业协议',
    title: '就业协议审签（华信智能科技有限公司）',
    applicant: { name: '周雨萌', studentNo: 'S2026-000009', className: '软件2301' },
    submitTime: '07-01 15:22', deadline: '07-04 18:00', urgency: 'URGENT', urgencyLabel: '临期',
    status: 'PENDING_REVIEW', statusLabel: '待审批', currentNode: '就业老师初审', transferred: false
  },
  {
    taskId: 'ap-012', bizType: 'EMPLOY_AGREEMENT', bizTypeLabel: '就业协议',
    title: '就业协议审签（星辰网络技术有限公司）',
    applicant: { name: '林晓彤', studentNo: 'S2026-000006', className: '软件2301' },
    submitTime: '07-02 17:48', deadline: '07-06 18:00', urgency: 'NORMAL', urgencyLabel: '正常',
    status: 'PENDING_REVIEW', statusLabel: '待审批', currentNode: '就业老师初审', transferred: false
  },
  {
    taskId: 'ap-013', bizType: 'LEAVE', bizTypeLabel: '请假申请',
    title: '请假申请（病假 3 天）',
    applicant: { name: '陈志远', studentNo: 'S2026-000007', className: '软件2302' },
    submitTime: '06-30 08:20', deadline: '07-01 18:00', urgency: 'OVERDUE', urgencyLabel: '已超时',
    status: 'PENDING_REVIEW', statusLabel: '待审批', currentNode: '辅导员审批', transferred: false
  },
  {
    taskId: 'ap-014', bizType: 'LEAVE', bizTypeLabel: '请假申请',
    title: '请假申请（事假 1 天 · 家中事务）',
    applicant: { name: '何雨珊', studentNo: 'S2026-000012', className: '软件2301' },
    submitTime: '07-03 10:05', deadline: '07-05 18:00', urgency: 'NORMAL', urgencyLabel: '正常',
    status: 'PENDING_REVIEW', statusLabel: '待审批', currentNode: '辅导员审批', transferred: false
  },
  {
    taskId: 'ap-101', bizType: 'STATUS_CHANGE', bizTypeLabel: '学籍异动',
    title: '复学申请（休学期满申请复学）',
    applicant: { name: '周雨萌', studentNo: 'S2026-000009', className: '软件2301' },
    submitTime: '06-25 09:00', deadline: '06-30 18:00', urgency: 'NORMAL', urgencyLabel: '正常',
    status: 'APPROVED', statusLabel: '已通过', currentNode: '已办结', finishTime: '06-30 11:20', transferred: false
  },
  {
    taskId: 'ap-102', bizType: 'EMPLOY_AGREEMENT', bizTypeLabel: '就业协议',
    title: '就业协议审签（华信智能科技有限公司）',
    applicant: { name: '何雨珊', studentNo: 'S2026-000012', className: '软件2301' },
    submitTime: '06-22 10:30', deadline: '06-27 18:00', urgency: 'NORMAL', urgencyLabel: '正常',
    status: 'APPROVED', statusLabel: '已通过', currentNode: '已办结', finishTime: '06-26 16:02', transferred: false
  },
  {
    taskId: 'ap-103', bizType: 'STATUS_CHANGE', bizTypeLabel: '学籍异动',
    title: '休学申请（家庭原因）',
    applicant: { name: '孙一诺', studentNo: 'S2026-000008', className: '软件2302' },
    submitTime: '06-20 15:40', deadline: '06-25 18:00', urgency: 'NORMAL', urgencyLabel: '正常',
    status: 'RETURNED', statusLabel: '已退回', currentNode: '已退回申请人', finishTime: '06-24 10:44', transferred: false
  },
  {
    taskId: 'ap-104', bizType: 'LEAVE', bizTypeLabel: '请假申请',
    title: '请假申请（事假 2 天）',
    applicant: { name: '林晓彤', studentNo: 'S2026-000006', className: '软件2301' },
    submitTime: '06-27 08:40', deadline: '06-28 18:00', urgency: 'NORMAL', urgencyLabel: '正常',
    status: 'APPROVED', statusLabel: '已通过', currentNode: '已办结', finishTime: '06-28 09:12', transferred: false
  },
  {
    taskId: 'ap-105', bizType: 'INFO_CORRECT', bizTypeLabel: '信息更正',
    title: '宿舍信息更正申请',
    applicant: { name: '赵一凡', studentNo: 'S2026-000001', className: '软件2301' },
    submitTime: '06-24 11:20', deadline: '06-27 18:00', urgency: 'NORMAL', urgencyLabel: '正常',
    status: 'APPROVED', statusLabel: '已通过', currentNode: '已办结', finishTime: '06-25 15:33', transferred: false
  },
  {
    taskId: 'ap-106', bizType: 'INTERN_REPORT', bizTypeLabel: '实习周报',
    title: '实习周报批阅（第 2 周）',
    applicant: { name: '何雨珊', studentNo: 'S2026-000012', className: '软件2301' },
    submitTime: '06-28 20:31', deadline: '06-30 18:00', urgency: 'NORMAL', urgencyLabel: '正常',
    status: 'RETURNED', statusLabel: '已退回', currentNode: '已退回申请人', finishTime: '06-29 10:22', transferred: false
  },
  {
    taskId: 'ap-107', bizType: 'INTERN_REPORT', bizTypeLabel: '实习周报',
    title: '实习周报批阅（第 4 周）',
    applicant: { name: '周雨萌', studentNo: 'S2026-000009', className: '软件2301' },
    submitTime: '07-01 19:40', deadline: '07-03 18:00', urgency: 'NORMAL', urgencyLabel: '正常',
    status: 'APPROVED', statusLabel: '已通过', currentNode: '已办结', finishTime: '07-01 20:40', transferred: false
  },
  {
    taskId: 'ap-108', bizType: 'INFO_CORRECT', bizTypeLabel: '信息更正',
    title: '户籍住址更正申请',
    applicant: { name: '吴俊杰', studentNo: 'S2026-000010', className: '软件2301' },
    submitTime: '06-21 09:15', deadline: '06-24 18:00', urgency: 'NORMAL', urgencyLabel: '正常',
    status: 'RETURNED', statusLabel: '已退回', currentNode: '已退回申请人', finishTime: '06-22 11:05', transferred: false
  },
  {
    taskId: 'ap-110', bizType: 'EMPLOY_AGREEMENT', bizTypeLabel: '就业协议',
    title: '就业协议审签（星辰网络技术有限公司）',
    applicant: { name: '郑浩然', studentNo: 'S2026-000011', className: '软件2302' },
    submitTime: '06-25 14:00', deadline: '06-29 18:00', urgency: 'NORMAL', urgencyLabel: '正常',
    status: 'RETURNED', statusLabel: '已退回', currentNode: '已退回申请人', finishTime: '06-27 09:50', transferred: false
  },
  {
    taskId: 'ap-112', bizType: 'LEAVE', bizTypeLabel: '请假申请',
    title: '请假申请（病假 5 天 · 超 3 天上报学院）',
    applicant: { name: '陈志远', studentNo: 'S2026-000007', className: '软件2302' },
    submitTime: '06-28 08:30', deadline: '06-30 18:00', urgency: 'NORMAL', urgencyLabel: '正常',
    status: 'APPROVED', statusLabel: '已通过', currentNode: '已办结', finishTime: '06-30 09:05', transferred: false
  }
]

/** 审批详情（业务字段 mp-kv 展示；敏感字段已在数据层脱敏，masked 标记用于页面加锁提示） */
export const approvalDetailMap = {
  'ap-001': {
    taskId: 'ap-001',
    fields: [
      { label: '异动类型', value: '休学（因病）' },
      { label: '身份证号', value: '3205**********0034', masked: true },
      { label: '联系电话', value: '135****6867', masked: true },
      { label: '休学起止', value: '2026-09-01 ~ 2027-02-28' },
      { label: '监护人意见', value: '已同意并签字确认' },
      { label: '学籍影响', value: '休学期间保留学籍，复学后随下一年级学习' }
    ],
    applyNote: '因病需住院治疗并休养，医院建议全休六个月，特申请休学一学期，相关证明已随附件上传。',
    attachments: ['三甲医院诊断证明.pdf', '家长知情同意书.jpg', '休学申请表（签字版）.pdf'],
    suggestions: [
      { who: '李敏 · 辅导员', time: '06-29 10:30', content: '已电话家访确认病情属实，家长陪同就医，建议同意休学并纳入返校跟踪名单。' },
      { who: '陈静 · 教务老师', time: '06-30 15:00', content: '学籍系统已预检，休学不影响本批次学籍注册，复学时需重修 2 门未结课程。' }
    ]
  },
  'ap-002': {
    taskId: 'ap-002',
    fields: [
      { label: '异动类型', value: '转专业' },
      { label: '转出专业', value: '软件技术（软件2302）' },
      { label: '转入专业', value: '大数据技术（数据2302）' },
      { label: '联系电话', value: '186****0031', masked: true },
      { label: '绩点排名', value: '专业前 15%（符合转入条件）' }
    ],
    applyNote: '对数据分析方向兴趣浓厚，已自学完成两门在线课程并取得证书，申请转入大数据技术专业。',
    attachments: ['转专业申请表.pdf', '在线课程证书 ×2.zip'],
    suggestions: [
      { who: '李敏 · 辅导员', time: '07-02 09:10', content: '在校表现良好，学习主动性强，无违纪记录，建议按转专业流程正常推进。' }
    ]
  },
  'ap-003': {
    taskId: 'ap-003',
    fields: [
      { label: '更正字段', value: '联系电话' },
      { label: '原号码', value: '155****0049', masked: true },
      { label: '新号码', value: '158****7723', masked: true },
      { label: '变更原因', value: '原号码停用换号' }
    ],
    applyNote: '手机号已更换，为不影响实习打卡与消息接收，申请更正主档联系电话。',
    attachments: [],
    suggestions: []
  },
  'ap-004': {
    taskId: 'ap-004',
    fields: [
      { label: '更正字段', value: '身份证件号' },
      { label: '原证件号', value: '3205**********0712', masked: true },
      { label: '新证件号', value: '3205**********0731', masked: true },
      { label: '联系电话', value: '137****5460', masked: true },
      { label: '变更原因', value: '入学登记时录入笔误，与户籍信息不一致' }
    ],
    applyNote: '入学信息采集时证件号末四位录入有误，影响实习责任险投保，申请依据户籍信息更正。',
    attachments: ['身份证正反面（加密）.pdf', '户籍页扫描件.pdf'],
    suggestions: [
      { who: '李敏 · 辅导员', time: '07-02 08:50', content: '已当面核对证件原件，确为录入笔误，建议尽快更正以免影响投保。' }
    ]
  },
  'ap-005': {
    taskId: 'ap-005',
    fields: [
      { label: '实习单位', value: '华信智能科技有限公司' },
      { label: '实习岗位', value: '前端开发实习生' },
      { label: '实习期限', value: '2026-07-13 ~ 2026-12-25' },
      { label: '企业导师', value: '周工 · 137****9902', masked: true },
      { label: '三方协议', value: '已签署待备案' },
      { label: '实习保险', value: '实习责任险 · 待生效' }
    ],
    applyNote: '已通过企业面试并取得录用意向，岗位与专业方向匹配，申请进入岗位实习。',
    attachments: ['实习三方协议.pdf', '企业录用意向书.pdf'],
    suggestions: []
  },
  'ap-006': {
    taskId: 'ap-006',
    fields: [
      { label: '原实习单位', value: '华信智能科技有限公司' },
      { label: '拟转入单位', value: '星辰网络技术有限公司' },
      { label: '拟转入岗位', value: '网络工程实习生' },
      { label: '变更原因', value: '原岗位项目结束，企业无后续实习安排' },
      { label: '联系电话', value: '133****0276', masked: true }
    ],
    applyNote: '原实习项目已提前收尾，经学校推荐已与星辰网络达成接收意向，申请变更实习单位。',
    attachments: ['单位变更申请表.pdf', '新单位接收函.pdf'],
    suggestions: [
      { who: '孙丽 · 就业老师', time: '07-02 10:20', content: '星辰网络为校企合作白名单企业，岗位与专业匹配，就业口径无异议。' }
    ]
  },
  'ap-007': {
    taskId: 'ap-007',
    fields: [
      { label: '周报周次', value: '第 3 周（v2 重交）' },
      { label: '本周工作', value: '客户现场配合完成 3 个前端页面联调与上线，学习灰度发布与回滚流程' },
      { label: '收获与问题', value: '掌握接口 Mock 与联调排错方法；打包配置尚不熟练，已约企业导师专项讲解' },
      { label: '下周计划', value: '返回公司参与组件库单元测试补齐，完成第 4 周周报' },
      { label: '字数 / 附件', value: '1430 字 · 3 个附件' }
    ],
    applyNote: 'v1 因内容过少被退回，本次已补充联调记录与问题反思，请老师复阅。',
    attachments: ['联调记录表.xlsx', '现场照片 ×2.zip', '上线清单.pdf'],
    suggestions: [
      { who: '李敏 · 辅导员', time: '07-02 09:00', content: '该生近期打卡连续异常已转风险跟进，批阅时请一并关注在岗状态说明。' }
    ]
  },
  'ap-008': {
    taskId: 'ap-008',
    fields: [
      { label: '周报周次', value: '第 4 周（v1）' },
      { label: '本周工作', value: '完成登录与订单模块回归测试 86 条用例，提交缺陷 7 个（阻塞级 2 个）' },
      { label: '收获与问题', value: '学会用例分层设计；自动化脚本维护仍需练习' },
      { label: '下周计划', value: '开始接口自动化脚本编写，目标覆盖核心链路 30%' },
      { label: '字数 / 附件', value: '1120 字 · 2 个附件' }
    ],
    applyNote: '',
    attachments: ['测试用例.xlsx', '缺陷清单.xlsx'],
    suggestions: []
  },
  'ap-009': {
    taskId: 'ap-009',
    fields: [
      { label: '选题名称', value: '基于小程序的实习打卡系统设计' },
      { label: '选题类型', value: '工程实践类（结合实习岗位）' },
      { label: '关联实习岗位', value: '产品助理实习生 · 华信智能' },
      { label: '预期成果', value: '可运行系统 + 设计文档 + 答辩材料' }
    ],
    applyNote: '选题来源于实习岗位真实需求，数据与场景可获得企业支持，恳请审核。',
    attachments: ['开题报告（初稿）.docx'],
    suggestions: []
  },
  'ap-010': {
    taskId: 'ap-010',
    fields: [
      { label: '原选题', value: '基于深度学习的图像识别平台' },
      { label: '新选题', value: '企业官网前端组件库设计与实现' },
      { label: '变更原因', value: '原题目算力与数据要求超出实习岗位可提供范围' },
      { label: '指导教师意见', value: '待审核' }
    ],
    applyNote: '经与指导教师沟通，原选题落地难度过大，新选题与当前实习工作内容一致，产出更可控。',
    attachments: ['选题变更申请表.pdf'],
    suggestions: [
      { who: '吴晓梅 · 教研室主任', time: '07-03 09:20', content: '新选题工作量饱满度尚可，建议补充组件库测试覆盖指标后通过。' }
    ]
  },
  'ap-011': {
    taskId: 'ap-011',
    fields: [
      { label: '签约单位', value: '华信智能科技有限公司' },
      { label: '签约岗位', value: '产品助理（转正）' },
      { label: '身份证号', value: '3205**********0451', masked: true },
      { label: '联系电话', value: '150****7788', masked: true },
      { label: '协议薪资', value: '试用期 4500 元/月，转正 5500 元/月' },
      { label: '违约条款', value: '违约金不超过一个月工资（合规）' }
    ],
    applyNote: '实习考核优秀获转正 Offer，三方协议已由企业盖章，请审签。',
    attachments: ['就业三方协议（企业盖章）.pdf', '企业营业执照副本.pdf'],
    suggestions: []
  },
  'ap-012': {
    taskId: 'ap-012',
    fields: [
      { label: '签约单位', value: '星辰网络技术有限公司' },
      { label: '签约岗位', value: '测试工程师（校招）' },
      { label: '联系电话', value: '159****8873', masked: true },
      { label: '协议薪资', value: '转正 5200 元/月 + 项目奖金' },
      { label: '报到时间', value: '2026-07-20' }
    ],
    applyNote: '已通过星辰网络校招流程，协议文本为学校模板版本，请审签备案。',
    attachments: ['就业三方协议.pdf'],
    suggestions: []
  },
  'ap-013': {
    taskId: 'ap-013',
    fields: [
      { label: '请假类型', value: '病假' },
      { label: '请假时长', value: '07-01 ~ 07-03（3 天）' },
      { label: '联系电话', value: '137****5460', masked: true },
      { label: '实习影响', value: '请假期间打卡走请假旁路，不计异常' }
    ],
    applyNote: '急性肠胃炎就医输液，医院建议休息三天，附门诊病历与缴费单。',
    attachments: ['门诊病历.jpg', '医疗缴费单.jpg'],
    suggestions: []
  },
  'ap-014': {
    taskId: 'ap-014',
    fields: [
      { label: '请假类型', value: '事假' },
      { label: '请假时长', value: '07-06（1 天）' },
      { label: '事由', value: '家中事务需本人到场办理' }
    ],
    applyNote: '家中户籍事务需本人回户籍地办理，往返一天，特申请事假。',
    attachments: [],
    suggestions: []
  },
  'ap-101': {
    taskId: 'ap-101',
    fields: [
      { label: '异动类型', value: '复学' },
      { label: '原休学期间', value: '2025-09-01 ~ 2026-02-28' },
      { label: '复学安排', value: '编入软件2301 随班学习' }
    ],
    applyNote: '休学期满，身体已康复（附复查证明），申请按期复学。',
    attachments: ['复查证明.pdf'],
    suggestions: []
  },
  'ap-102': {
    taskId: 'ap-102',
    fields: [
      { label: '签约单位', value: '华信智能科技有限公司' },
      { label: '签约岗位', value: '测试工程师（转正）' },
      { label: '协议薪资', value: '转正 5000 元/月' }
    ],
    applyNote: '实习期满考核合格，企业发放转正 Offer，申请协议审签。',
    attachments: ['就业三方协议.pdf'],
    suggestions: []
  },
  'ap-103': {
    taskId: 'ap-103',
    fields: [
      { label: '异动类型', value: '休学（家庭原因）' },
      { label: '拟休学期间', value: '2026-09-01 ~ 2027-02-28' },
      { label: '材料情况', value: '缺少监护人签字书面申请' }
    ],
    applyNote: '因家庭原因需暂停学业半年，先行线上提交申请。',
    attachments: [],
    suggestions: []
  },
  'ap-104': {
    taskId: 'ap-104',
    fields: [
      { label: '请假类型', value: '事假' },
      { label: '请假时长', value: '06-29 ~ 06-30（2 天）' }
    ],
    applyNote: '家中长辈生日，申请事假两天，已与企业导师报备。',
    attachments: [],
    suggestions: []
  },
  'ap-105': {
    taskId: 'ap-105',
    fields: [
      { label: '更正字段', value: '宿舍信息' },
      { label: '原信息', value: '3 号楼 512' },
      { label: '新信息', value: '5 号楼 208' }
    ],
    applyNote: '因宿舍调整申请更正主档住宿信息。',
    attachments: ['调宿通知截图.png'],
    suggestions: []
  },
  'ap-106': {
    taskId: 'ap-106',
    fields: [
      { label: '周报周次', value: '第 2 周（v1）' },
      { label: '字数 / 附件', value: '620 字 · 无附件' },
      { label: '批阅结论', value: '已退回（内容不完整）' }
    ],
    applyNote: '',
    attachments: [],
    suggestions: []
  },
  'ap-107': {
    taskId: 'ap-107',
    fields: [
      { label: '周报周次', value: '第 4 周（v1）' },
      { label: '字数 / 附件', value: '980 字 · 1 个附件' },
      { label: '批阅结论', value: '已通过' }
    ],
    applyNote: '',
    attachments: ['需求评审纪要.pdf'],
    suggestions: []
  },
  'ap-108': {
    taskId: 'ap-108',
    fields: [
      { label: '更正字段', value: '户籍住址' },
      { label: '材料情况', value: '未上传户口簿变更页' }
    ],
    applyNote: '家庭搬迁申请更正户籍住址信息。',
    attachments: [],
    suggestions: []
  },
  'ap-110': {
    taskId: 'ap-110',
    fields: [
      { label: '签约单位', value: '星辰网络技术有限公司' },
      { label: '签约岗位', value: '运维工程师（校招）' },
      { label: '审签结论', value: '已退回（公章名称与营业执照不一致）' }
    ],
    applyNote: '校招签约星辰网络，提交三方协议审签。',
    attachments: ['就业三方协议.pdf'],
    suggestions: []
  },
  'ap-112': {
    taskId: 'ap-112',
    fields: [
      { label: '请假类型', value: '病假（超 3 天上报学院）' },
      { label: '请假时长', value: '06-29 ~ 07-03（5 天）' },
      { label: '联系电话', value: '137****5460', masked: true }
    ],
    applyNote: '支气管炎需连续输液五天，附住院证明，按流程上报学院审批。',
    attachments: ['住院证明.pdf'],
    suggestions: []
  }
}

/** 审批时间线（节点留痕：who/action/time/comment/tone） */
export const approvalTimelineMap = {
  'ap-001': [
    { who: '赵一凡（学生端）', action: '提交休学申请', time: '06-28 09:12', comment: '', tone: 'default' },
    { who: '李敏 · 辅导员', action: '初审通过', time: '06-29 10:35', comment: '情况属实，材料齐全，已完成家访确认', tone: 'success' },
    { who: '陈静 · 教务老师', action: '教务复核通过', time: '06-30 15:02', comment: '学籍信息核对无误，复学需重修 2 门课程', tone: 'success' },
    { who: '系统', action: '超时预警', time: '07-03 08:00', comment: '任务超过办理时限，已标记为已超时并提醒经办人', tone: 'danger' }
  ],
  'ap-002': [
    { who: '孙一诺（学生端）', action: '提交转专业申请', time: '07-01 14:26', comment: '', tone: 'default' },
    { who: '李敏 · 辅导员', action: '初审通过', time: '07-02 09:12', comment: '在校表现良好，符合转专业申请条件', tone: 'success' }
  ],
  'ap-003': [
    { who: '何雨珊（学生端）', action: '提交信息更正申请', time: '07-03 09:40', comment: '', tone: 'default' }
  ],
  'ap-004': [
    { who: '陈志远（学生端）', action: '提交信息更正申请', time: '07-01 10:18', comment: '', tone: 'default' },
    { who: '李敏 · 辅导员', action: '核验通过', time: '07-02 08:52', comment: '已当面核对证件原件，确为录入笔误', tone: 'success' }
  ],
  'ap-005': [
    { who: '吴俊杰（学生端）', action: '提交实习申请', time: '07-02 11:05', comment: '', tone: 'default' }
  ],
  'ap-006': [
    { who: '郑浩然（学生端）', action: '提交单位变更申请', time: '07-01 16:40', comment: '', tone: 'default' },
    { who: '孙丽 · 就业老师', action: '加签意见', time: '07-02 10:20', comment: '新单位为校企合作白名单企业，就业口径无异议', tone: 'warning' }
  ],
  'ap-007': [
    { who: '赵一凡（学生端）', action: '首次提交 v1', time: '06-28 22:10', comment: '', tone: 'default' },
    { who: '刘强 · 指导教师', action: '退回 v1', time: '06-29 10:22', comment: '仅 300 字，缺少本周工作实质内容与问题反思', tone: 'danger' },
    { who: '赵一凡（学生端）', action: '重新提交 v2', time: '07-01 08:02', comment: '已补充联调记录与问题反思', tone: 'default' },
    { who: '系统', action: '超时预警', time: '07-03 08:00', comment: '批阅任务超过 48 小时时限', tone: 'danger' }
  ],
  'ap-008': [
    { who: '林晓彤（学生端）', action: '提交第 4 周周报', time: '07-03 08:15', comment: '', tone: 'default' }
  ],
  'ap-009': [
    { who: '周雨萌（学生端）', action: '提交选题申报', time: '07-02 19:30', comment: '', tone: 'default' }
  ],
  'ap-010': [
    { who: '吴俊杰（学生端）', action: '提交选题变更申请', time: '07-02 09:55', comment: '', tone: 'default' },
    { who: '刘强 · 指导教师', action: '审核通过', time: '07-02 15:30', comment: '新选题与实习内容一致，同意变更', tone: 'success' },
    { who: '吴晓梅 · 教研室主任', action: '加签意见', time: '07-03 09:20', comment: '建议补充组件库测试覆盖指标后通过', tone: 'warning' }
  ],
  'ap-011': [
    { who: '周雨萌（学生端）', action: '提交协议审签申请', time: '07-01 15:22', comment: '', tone: 'default' }
  ],
  'ap-012': [
    { who: '林晓彤（学生端）', action: '提交协议审签申请', time: '07-02 17:48', comment: '', tone: 'default' }
  ],
  'ap-013': [
    { who: '陈志远（学生端）', action: '提交请假申请', time: '06-30 08:20', comment: '', tone: 'default' },
    { who: '系统', action: '超时预警', time: '07-02 08:00', comment: '请假审批超过 12 小时时限，请尽快办理', tone: 'danger' }
  ],
  'ap-014': [
    { who: '何雨珊（学生端）', action: '提交请假申请', time: '07-03 10:05', comment: '', tone: 'default' }
  ],
  'ap-101': [
    { who: '周雨萌（学生端）', action: '提交复学申请', time: '06-25 09:00', comment: '', tone: 'default' },
    { who: '陈静 · 教务老师', action: '教务复核通过', time: '06-28 14:20', comment: '复查证明有效，学籍可正常恢复', tone: 'success' },
    { who: '王建国 · 学院管理员', action: '学院审批通过', time: '06-30 11:20', comment: '同意复学，请辅导员跟进选课', tone: 'success' }
  ],
  'ap-102': [
    { who: '何雨珊（学生端）', action: '提交协议审签申请', time: '06-22 10:30', comment: '', tone: 'default' },
    { who: '孙丽 · 就业老师', action: '初审通过', time: '06-24 10:15', comment: '企业资质与协议条款核对无误', tone: 'success' },
    { who: '王建国 · 学院管理员', action: '学院审签通过', time: '06-26 16:02', comment: '协议条款合规，完成审签', tone: 'success' }
  ],
  'ap-103': [
    { who: '孙一诺（学生端）', action: '提交休学申请', time: '06-20 15:40', comment: '', tone: 'default' },
    { who: '王建国 · 学院管理员', action: '退回申请', time: '06-24 10:44', comment: '缺少监护人签字的书面休学申请与证明材料', tone: 'danger' }
  ],
  'ap-104': [
    { who: '林晓彤（学生端）', action: '提交请假申请', time: '06-27 08:40', comment: '', tone: 'default' },
    { who: '李敏 · 辅导员', action: '审批通过', time: '06-28 09:12', comment: '已与企业导师确认工作交接安排', tone: 'success' }
  ],
  'ap-105': [
    { who: '赵一凡（学生端）', action: '提交信息更正申请', time: '06-24 11:20', comment: '', tone: 'default' },
    { who: '李敏 · 辅导员', action: '核验通过', time: '06-25 15:33', comment: '与宿管系统调宿记录一致', tone: 'success' }
  ],
  'ap-106': [
    { who: '何雨珊（学生端）', action: '提交第 2 周周报', time: '06-28 20:31', comment: '', tone: 'default' },
    { who: '刘强 · 指导教师', action: '退回周报', time: '06-29 10:22', comment: '仅 620 字且无附件，缺少工作实质内容，请补充后重交', tone: 'danger' }
  ],
  'ap-107': [
    { who: '周雨萌（学生端）', action: '提交第 4 周周报', time: '07-01 19:40', comment: '', tone: 'default' },
    { who: '刘强 · 指导教师', action: '批阅通过', time: '07-01 20:40', comment: '记录完整，下周补充量化数据', tone: 'success' }
  ],
  'ap-108': [
    { who: '吴俊杰（学生端）', action: '提交信息更正申请', time: '06-21 09:15', comment: '', tone: 'default' },
    { who: '陈静 · 教务老师', action: '退回申请', time: '06-22 11:05', comment: '未上传户口簿变更页扫描件，无法核验新住址', tone: 'danger' }
  ],
  'ap-110': [
    { who: '郑浩然（学生端）', action: '提交协议审签申请', time: '06-25 14:00', comment: '', tone: 'default' },
    { who: '孙丽 · 就业老师', action: '退回申请', time: '06-27 09:50', comment: '协议甲方公章名称与营业执照登记名称不一致', tone: 'danger' }
  ],
  'ap-112': [
    { who: '陈志远（学生端）', action: '提交请假申请', time: '06-28 08:30', comment: '', tone: 'default' },
    { who: '李敏 · 辅导员', action: '初审通过', time: '06-28 10:10', comment: '住院证明属实，按超 3 天流程上报学院', tone: 'success' },
    { who: '王建国 · 学院管理员', action: '学院审批通过', time: '06-30 09:05', comment: '同意病假，返岗时需提交复工确认', tone: 'success' }
  ]
}

/** 退回记录（roleCode 标记退回操作发生在哪个角色名下；辅导员名下暂无 → 演示友好空态） */
export const returnedItems = [
  {
    id: 'rt-001', taskId: 'ap-106', bizTypeLabel: '实习周报', title: '实习周报批阅（第 2 周）',
    applicantName: '何雨珊', className: '软件2301',
    reason: '周报仅 620 字且无附件，缺少本周工作实质内容与问题反思，请补充联调过程细节后重新提交',
    returnedBy: '刘强', returnTime: '06-29 10:22',
    rectifyStatus: 'RESUBMITTED', rectifyStatusLabel: '已重新提交', roleCode: 'ADVISOR'
  },
  {
    id: 'rt-002', taskId: 'ap-103', bizTypeLabel: '学籍异动', title: '休学申请（家庭原因）',
    applicantName: '孙一诺', className: '软件2302',
    reason: '缺少监护人签字的书面休学申请与医院证明原件扫描件，请补齐材料后重新提交',
    returnedBy: '王建国', returnTime: '06-24 10:44',
    rectifyStatus: 'PENDING_RESUBMIT', rectifyStatusLabel: '待整改重报', roleCode: 'COLLEGE_ADMIN'
  },
  {
    id: 'rt-003', taskId: 'ap-110', bizTypeLabel: '就业协议', title: '就业协议审签（星辰网络技术有限公司）',
    applicantName: '郑浩然', className: '软件2302',
    reason: '协议甲方公章名称与营业执照登记名称不一致，请企业重新盖章后上传',
    returnedBy: '孙丽', returnTime: '06-27 09:50',
    rectifyStatus: 'PENDING_RESUBMIT', rectifyStatusLabel: '待整改重报', roleCode: 'EMPLOYMENT'
  },
  {
    id: 'rt-004', taskId: 'ap-108', bizTypeLabel: '信息更正', title: '户籍住址更正申请',
    applicantName: '吴俊杰', className: '软件2301',
    reason: '未上传户口簿变更页扫描件，无法核验新住址信息，本次申请关闭，可重新发起',
    returnedBy: '陈静', returnTime: '06-22 11:05',
    rectifyStatus: 'CLOSED', rectifyStatusLabel: '已关闭', roleCode: 'ACADEMIC'
  }
]

/** 已办记录（roleCode 标记经办角色；同一任务可在不同节点产生多条已办） */
export const doneItems = [
  {
    id: 'dn-001', taskId: 'ap-101', bizTypeLabel: '学籍异动', title: '复学申请（休学期满申请复学）',
    applicantName: '周雨萌', className: '软件2301', node: '学院审批',
    result: 'APPROVED', resultLabel: '已通过', finishTime: '06-30 11:20',
    comment: '同意复学，请辅导员跟进选课', roleCode: 'COLLEGE_ADMIN'
  },
  {
    id: 'dn-002', taskId: 'ap-102', bizTypeLabel: '就业协议', title: '就业协议审签（华信智能科技有限公司）',
    applicantName: '何雨珊', className: '软件2301', node: '学院审签',
    result: 'APPROVED', resultLabel: '已通过', finishTime: '06-26 16:02',
    comment: '协议条款合规，完成审签', roleCode: 'COLLEGE_ADMIN'
  },
  {
    id: 'dn-003', taskId: 'ap-103', bizTypeLabel: '学籍异动', title: '休学申请（家庭原因）',
    applicantName: '孙一诺', className: '软件2302', node: '学院审批',
    result: 'RETURNED', resultLabel: '已退回', finishTime: '06-24 10:44',
    comment: '缺少监护人签字的书面申请', roleCode: 'COLLEGE_ADMIN'
  },
  {
    id: 'dn-004', taskId: 'ap-104', bizTypeLabel: '请假申请', title: '请假申请（事假 2 天）',
    applicantName: '林晓彤', className: '软件2301', node: '辅导员审批',
    result: 'APPROVED', resultLabel: '已通过', finishTime: '06-28 09:12',
    comment: '已与企业导师确认交接安排', roleCode: 'COUNSELOR'
  },
  {
    id: 'dn-005', taskId: 'ap-105', bizTypeLabel: '信息更正', title: '宿舍信息更正申请',
    applicantName: '赵一凡', className: '软件2301', node: '辅导员核验',
    result: 'APPROVED', resultLabel: '已通过', finishTime: '06-25 15:33',
    comment: '与宿管系统调宿记录一致', roleCode: 'COUNSELOR'
  },
  {
    id: 'dn-006', taskId: 'ap-106', bizTypeLabel: '实习周报', title: '实习周报批阅（第 2 周）',
    applicantName: '何雨珊', className: '软件2301', node: '指导教师批阅',
    result: 'RETURNED', resultLabel: '已退回', finishTime: '06-29 10:22',
    comment: '内容不完整，已注明整改要求', roleCode: 'ADVISOR'
  },
  {
    id: 'dn-007', taskId: 'ap-107', bizTypeLabel: '实习周报', title: '实习周报批阅（第 4 周）',
    applicantName: '周雨萌', className: '软件2301', node: '指导教师批阅',
    result: 'APPROVED', resultLabel: '已通过', finishTime: '07-01 20:40',
    comment: '记录完整，下周补充量化数据', roleCode: 'ADVISOR'
  },
  {
    id: 'dn-008', taskId: 'ap-108', bizTypeLabel: '信息更正', title: '户籍住址更正申请',
    applicantName: '吴俊杰', className: '软件2301', node: '教务复核',
    result: 'RETURNED', resultLabel: '已退回', finishTime: '06-22 11:05',
    comment: '缺少户口簿变更页扫描件', roleCode: 'ACADEMIC'
  },
  {
    id: 'dn-009', taskId: 'ap-101', bizTypeLabel: '学籍异动', title: '复学申请（休学期满申请复学）',
    applicantName: '周雨萌', className: '软件2301', node: '教务复核',
    result: 'APPROVED', resultLabel: '已通过', finishTime: '06-28 14:20',
    comment: '复查证明有效，学籍可正常恢复', roleCode: 'ACADEMIC'
  },
  {
    id: 'dn-010', taskId: 'ap-110', bizTypeLabel: '就业协议', title: '就业协议审签（星辰网络技术有限公司）',
    applicantName: '郑浩然', className: '软件2302', node: '就业老师初审',
    result: 'RETURNED', resultLabel: '已退回', finishTime: '06-27 09:50',
    comment: '公章名称与营业执照不一致', roleCode: 'EMPLOYMENT'
  },
  {
    id: 'dn-011', taskId: 'ap-102', bizTypeLabel: '就业协议', title: '就业协议审签（华信智能科技有限公司）',
    applicantName: '何雨珊', className: '软件2301', node: '就业老师初审',
    result: 'APPROVED', resultLabel: '已通过', finishTime: '06-24 10:15',
    comment: '企业资质与协议条款核对无误', roleCode: 'EMPLOYMENT'
  }
]

/** 抄送记录（roleCode 标记抄送对象角色） */
export const ccItems = [
  {
    id: 'cc-001', taskId: 'ap-112', bizTypeLabel: '请假申请', title: '请假申请（病假 5 天 · 超 3 天上报学院）',
    applicantName: '陈志远', className: '软件2302',
    ccReason: '病假超 3 天，按流程抄送学院备案', ccTime: '06-30 09:10',
    readStatus: 'UNREAD', readStatusLabel: '未读', roleCode: 'COLLEGE_ADMIN'
  },
  {
    id: 'cc-002', taskId: 'ap-110', bizTypeLabel: '就业协议', title: '就业协议审签（星辰网络技术有限公司）',
    applicantName: '郑浩然', className: '软件2302',
    ccReason: '协议退回结果抄送学院知悉', ccTime: '06-27 10:00',
    readStatus: 'READ', readStatusLabel: '已读', roleCode: 'COLLEGE_ADMIN'
  },
  {
    id: 'cc-003', taskId: 'ap-106', bizTypeLabel: '实习周报', title: '实习周报批阅（第 2 周）',
    applicantName: '何雨珊', className: '软件2301',
    ccReason: '周报退回结果抄送辅导员，请协同督促整改', ccTime: '06-29 10:25',
    readStatus: 'READ', readStatusLabel: '已读', roleCode: 'COUNSELOR'
  },
  {
    id: 'cc-004', taskId: 'ap-101', bizTypeLabel: '学籍异动', title: '复学申请（休学期满申请复学）',
    applicantName: '周雨萌', className: '软件2301',
    ccReason: '复学审批结果抄送指导教师，请安排后续毕设指导', ccTime: '06-30 11:25',
    readStatus: 'UNREAD', readStatusLabel: '未读', roleCode: 'ADVISOR'
  },
  {
    id: 'cc-005', taskId: 'ap-101', bizTypeLabel: '学籍异动', title: '复学申请（休学期满申请复学）',
    applicantName: '周雨萌', className: '软件2301',
    ccReason: '复学审批结果抄送教务备案', ccTime: '06-30 11:25',
    readStatus: 'READ', readStatusLabel: '已读', roleCode: 'ACADEMIC'
  },
  {
    id: 'cc-006', taskId: 'ap-102', bizTypeLabel: '就业协议', title: '就业协议审签（华信智能科技有限公司）',
    applicantName: '何雨珊', className: '软件2301',
    ccReason: '协议审签完成，抄送就业口径归档', ccTime: '06-26 16:05',
    readStatus: 'UNREAD', readStatusLabel: '未读', roleCode: 'EMPLOYMENT'
  }
]

/** 可转交人列表（api 按当前角色排除本人后下发） */
export const transferTargets = [
  { userId: 'u-wjg', userName: '王建国', roleName: '学院管理员', orgName: '信息工程学院', pendingCount: 14 },
  { userId: 'u-lm', userName: '李敏', roleName: '辅导员', orgName: '信息工程学院 · 学工线', pendingCount: 5 },
  { userId: 'u-lq', userName: '刘强', roleName: '指导教师', orgName: '信息工程学院 · 软件教研室', pendingCount: 4 },
  { userId: 'u-cj', userName: '陈静', roleName: '教务老师', orgName: '教务处', pendingCount: 6 },
  { userId: 'u-sl', userName: '孙丽', roleName: '就业老师', orgName: '就业指导中心', pendingCount: 3 },
  { userId: 'u-wxm', userName: '吴晓梅', roleName: '教研室主任', orgName: '信息工程学院 · 软件教研室', pendingCount: 2 },
  { userId: 'u-hzq', userName: '何志强', roleName: '副院长', orgName: '信息工程学院', pendingCount: 1 }
]

/** 审批模板（节点定义 nodes:[{name,role,roleLabel,sla(小时)}]，逻辑作废保留 voidReason） */
export const approvalTemplates = [
  {
    id: 'tpl-001', name: '学籍异动审批流', bizType: 'STATUS_CHANGE', bizTypeLabel: '学籍异动',
    nodes: [
      { name: '辅导员初审', role: 'COUNSELOR', roleLabel: '辅导员', sla: 48 },
      { name: '教务复核', role: 'ACADEMIC', roleLabel: '教务老师', sla: 24 },
      { name: '学院审批', role: 'COLLEGE_ADMIN', roleLabel: '学院管理员', sla: 24 }
    ],
    status: 'ENABLED', statusLabel: '启用中', version: 'V3',
    updatedBy: '王建国', updatedAt: '06-20 10:00', voidReason: ''
  },
  {
    id: 'tpl-002', name: '信息更正审批流', bizType: 'INFO_CORRECT', bizTypeLabel: '信息更正',
    nodes: [
      { name: '辅导员核验', role: 'COUNSELOR', roleLabel: '辅导员', sla: 24 },
      { name: '教务复核', role: 'ACADEMIC', roleLabel: '教务老师', sla: 24 }
    ],
    status: 'ENABLED', statusLabel: '启用中', version: 'V2',
    updatedBy: '王建国', updatedAt: '06-18 14:30', voidReason: ''
  },
  {
    id: 'tpl-003', name: '实习申请审批流', bizType: 'INTERN_APPLY', bizTypeLabel: '实习申请',
    nodes: [
      { name: '指导教师审核', role: 'ADVISOR', roleLabel: '指导教师', sla: 24 },
      { name: '学院备案', role: 'COLLEGE_ADMIN', roleLabel: '学院管理员', sla: 48 }
    ],
    status: 'ENABLED', statusLabel: '启用中', version: 'V2',
    updatedBy: '王建国', updatedAt: '06-15 09:20', voidReason: ''
  },
  {
    id: 'tpl-004', name: '实习周报批阅流', bizType: 'INTERN_REPORT', bizTypeLabel: '实习周报',
    nodes: [{ name: '指导教师批阅', role: 'ADVISOR', roleLabel: '指导教师', sla: 48 }],
    status: 'ENABLED', statusLabel: '启用中', version: 'V1',
    updatedBy: '王建国', updatedAt: '05-30 16:00', voidReason: ''
  },
  {
    id: 'tpl-005', name: '毕设选题审批流', bizType: 'THESIS_TOPIC', bizTypeLabel: '毕设选题',
    nodes: [
      { name: '指导教师审核', role: 'ADVISOR', roleLabel: '指导教师', sla: 48 },
      { name: '教研室复核', role: 'COLLEGE_ADMIN', roleLabel: '学院管理员', sla: 48 }
    ],
    status: 'ENABLED', statusLabel: '启用中', version: 'V2',
    updatedBy: '王建国', updatedAt: '06-10 11:00', voidReason: ''
  },
  {
    id: 'tpl-006', name: '就业协议审签流', bizType: 'EMPLOY_AGREEMENT', bizTypeLabel: '就业协议',
    nodes: [
      { name: '就业老师初审', role: 'EMPLOYMENT', roleLabel: '就业老师', sla: 24 },
      { name: '学院审签', role: 'COLLEGE_ADMIN', roleLabel: '学院管理员', sla: 48 }
    ],
    status: 'ENABLED', statusLabel: '启用中', version: 'V4',
    updatedBy: '王建国', updatedAt: '07-02 16:20', voidReason: ''
  },
  {
    id: 'tpl-007', name: '请假审批流', bizType: 'LEAVE', bizTypeLabel: '请假申请',
    nodes: [
      { name: '辅导员审批', role: 'COUNSELOR', roleLabel: '辅导员', sla: 12 },
      { name: '学院审批（超 3 天）', role: 'COLLEGE_ADMIN', roleLabel: '学院管理员', sla: 24 }
    ],
    status: 'ENABLED', statusLabel: '启用中', version: 'V2',
    updatedBy: '王建国', updatedAt: '06-05 10:40', voidReason: ''
  },
  {
    id: 'tpl-008', name: '信息更正审批流（旧版）', bizType: 'INFO_CORRECT', bizTypeLabel: '信息更正',
    nodes: [{ name: '教务直核', role: 'ACADEMIC', roleLabel: '教务老师', sla: 48 }],
    status: 'VOIDED', statusLabel: '已作废', version: 'V1',
    updatedBy: '王建国', updatedAt: '05-10 09:00', voidReason: '流程节点调整，由 V2 版本替代，历史单据保留可追溯'
  }
]

/** 审计留痕（新增留痕由 api unshift 到队首） */
export const auditLogs = [
  {
    id: 'al-005', who: '王建国', roleName: '学院管理员', time: '07-02 16:20',
    action: '更新审批模板', target: '就业协议审签流',
    detail: '版本 V3 → V4，学院审签时限由 72 小时调整为 48 小时'
  },
  {
    id: 'al-004', who: '系统', roleName: '自动任务', time: '07-03 08:00',
    action: '超时预警', target: 'ap-001 / ap-007 / ap-013',
    detail: '3 条待办超过办理时限，已标记「已超时」并通知经办人'
  },
  {
    id: 'al-003', who: '刘强', roleName: '指导教师', time: '06-29 10:22',
    action: '退回审批', target: 'ap-106 实习周报（第 2 周）',
    detail: '退回原因已同步学生端，抄送辅导员协同督促'
  },
  {
    id: 'al-002', who: '孙丽', roleName: '就业老师', time: '06-27 09:50',
    action: '退回审批', target: 'ap-110 就业协议审签',
    detail: '要求企业重新盖章后上传，退回结果抄送学院'
  },
  {
    id: 'al-001', who: '陈静', roleName: '教务老师', time: '06-22 11:08',
    action: '导出记录', target: '学籍异动台账',
    detail: '字段已脱敏、文件含水印，审计编号 AUD-0061'
  }
]
