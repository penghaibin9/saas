/**
 * 毕业设计中心 mock 数据（05 反向建模 V1.0 口径）。
 * 主状态机：未启动 → 选题中 → 任务书确认 → 指导中 → 中期检查 → 成果检查 → 答辩中 → 成绩待发布 → 已完成 → 已归档。
 * 页面禁止直接 import 本文件，必须经 modules/graduation/api 获取。
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

/** 当前登录角色（mock：学院管理员视角，与岗位实习模块的教师视角形成权限对照） */
export const currentRole = {
  userId: 'u-college-001',
  userName: '张文澜',
  roleCode: 'COLLEGE_ADMIN',
  roleName: '学院管理员'
}

export const dataScope = {
  scopeCode: 'COLLEGE',
  scopeName: '本学院（软件学院 · 326 人）'
}

export const permissionActions = {
  createBatch: { visible: true, allowed: true, reason: '' },
  importStudents: { visible: true, allowed: true, reason: '' },
  exportStats: { visible: true, allowed: true, reason: '' },
  viewAuditLog: { visible: true, allowed: true, reason: '' },
  createProject: { visible: true, allowed: true, reason: '' },
  batchAssignAdvisor: { visible: true, allowed: true, reason: '' },
  batchRemind: { visible: true, allowed: true, reason: '' },
  batchArchive: { visible: true, allowed: true, reason: '' },
  editProject: { visible: true, allowed: true, reason: '' },
  voidProject: { visible: true, allowed: true, reason: '作废为逻辑删除，需填写原因并留痕' },
  createTopic: { visible: true, allowed: true, reason: '' },
  importTopics: { visible: true, allowed: true, reason: '' },
  exportTopics: { visible: true, allowed: true, reason: '' },
  disableTopic: { visible: true, allowed: true, reason: '' },
  reviewProposal: { visible: true, allowed: false, reason: '开题批阅需「指导教师」角色，管理员仅可查看' },
  reviewFinal: { visible: true, allowed: false, reason: '成果批阅需「指导教师」角色，管理员仅可查看' },
  exportProposals: { visible: true, allowed: true, reason: '' },
  manageDefense: { visible: true, allowed: true, reason: '' },
  publishDefense: { visible: true, allowed: true, reason: '' },
  exportDefense: { visible: true, allowed: true, reason: '' },
  enterDefenseScore: { visible: true, allowed: true, reason: '' },
  confirmDefenseScores: { visible: true, allowed: true, reason: '' },
  createSecondDefense: { visible: true, allowed: true, reason: '' },
  manageGrade: { visible: true, allowed: true, reason: '' },
  reviewGradeAppeal: { visible: true, allowed: true, reason: '' },
  publishGrade: { visible: true, allowed: true, reason: '' },
  guideMidterm: { visible: true, allowed: true, reason: '' },
  guideTaskbook: { visible: true, allowed: true, reason: '' }
}

export const statusOptions = {
  stage: [
    { value: 'TOPIC_SELECTING', label: '选题中' },
    { value: 'TASKBOOK_CONFIRM', label: '任务书确认' },
    { value: 'GUIDING', label: '指导中' },
    { value: 'MIDTERM', label: '中期检查' },
    { value: 'FINAL_CHECK', label: '成果检查' },
    { value: 'DEFENSE', label: '答辩中' },
    { value: 'ARCHIVED', label: '已归档' }
  ],
  riskLevel: [
    { value: 'LOW', label: '低风险' },
    { value: 'MEDIUM', label: '中风险' },
    { value: 'HIGH', label: '高风险' }
  ],
  materialStatus: [
    { value: 'PENDING_REVIEW', label: '待审阅' },
    { value: 'APPROVED', label: '已通过' },
    { value: 'REJECTED', label: '已驳回' },
    { value: 'NOT_SUBMITTED', label: '未提交' }
  ],
  advisors: [
    { value: 't-001', label: '王芳' },
    { value: 't-004', label: '钱立群' },
    { value: 't-005', label: '孙晓梅' }
  ],
  classes: [
    { value: 'c-2301', label: '软件2301' },
    { value: 'c-2302', label: '软件2302' }
  ]
}

export const dashboardSummary = {
  batchName: '2026 届毕业设计批次',
  batchRange: '2025-11-01 ~ 2026-06-30',
  batchStatus: '进行中',
  stats: [
    { label: '毕设学生', value: '326', trend: '', trendQuality: 'neutral' },
    { label: '选题确认率', value: '96.3%', trend: '未确认 12 人', trendQuality: 'neutral' },
    { label: '开题通过率', value: '88.7%', trend: '待审阅 23 篇', trendQuality: 'neutral' },
    { label: '查重达标率', value: '91.4%', trend: '▲ 较上批 +3.2%', trendQuality: 'good' },
    { label: '滞后学生', value: '18', trend: '高风险 5', trendQuality: 'bad' }
  ],
  flow: [
    { label: '选题中', value: 12 },
    { label: '任务书确认', value: 9 },
    { label: '指导中', value: 74 },
    { label: '中期检查', value: 41 },
    { label: '成果检查', value: 158, active: true },
    { label: '答辩中', value: 26 },
    { label: '已归档', value: 6 }
  ],
  todos: [
    { id: 'gd-todo-1', label: '开题材料待审阅', count: 23, tone: 'danger', hint: '3 篇超 48h 未批（GD-R05）', route: '/admin/graduation/proposals' },
    { id: 'gd-todo-2', label: '成果定稿待审 / 待查重', count: 31, tone: 'warning', hint: '含查重不达标 4 篇', route: '/admin/graduation/finals' },
    { id: 'gd-todo-3', label: '答辩分组待发布', count: 2, tone: 'warning', hint: '第 5、6 组未安排评委', route: '/admin/graduation/defense' },
    { id: 'gd-todo-4', label: '滞后学生待跟进', count: 18, tone: 'danger', hint: '5 人两个节点未过（GD-R08）', route: '/admin/graduation/students' }
  ],
  riskAlerts: [
    { id: 'gd-ra-1', code: 'GD-R04', level: 'HIGH', title: '开题逾期未交 5 人', detail: '软件2302 为主 · 已催办 2 轮', time: '今天 08:00' },
    { id: 'gd-ra-2', code: 'GD-R09', level: 'HIGH', title: '查重率超标 4 篇', detail: '定稿查重 >30% · 已退回修改', time: '昨天 16:20' },
    { id: 'gd-ra-3', code: 'GD-R11', level: 'MEDIUM', title: '答辩评委与导师冲突 1 组', detail: '第 4 组评委含指导教师本人，已拦截待调整', time: '昨天 10:05' }
  ]
}

/** 毕设学生列表 */
export const graduationStudents = [
  {
    id: 'gd-001', studentId: 'stu-002', name: '陈思雨', studentNo: 'S2026-000002',
    className: '软件2301', classId: 'c-2301',
    topicTitle: '基于 Vue3 的校园二手交易平台设计与实现',
    advisorId: 't-001', advisorName: '王芳',
    stage: 'FINAL_CHECK', stageLabel: '成果检查',
    materialSummary: '定稿 v3 待审', plagiarismRate: '12.6%', plagiarismTone: 'success',
    riskLevel: 'NONE', phone: '13612340552'
  },
  {
    id: 'gd-002', studentId: 'stu-013', name: '刘一鸣', studentNo: 'S2026-000013',
    className: '软件2301', classId: 'c-2301',
    topicTitle: '中小企业进销存管理系统的设计与实现',
    advisorId: 't-001', advisorName: '王芳',
    stage: 'FINAL_CHECK', stageLabel: '成果检查',
    materialSummary: '查重不达标（34.2%）', plagiarismRate: '34.2%', plagiarismTone: 'danger',
    riskLevel: 'HIGH', phone: '13712340981'
  },
  {
    id: 'gd-003', studentId: 'stu-014', name: '王梓涵', studentNo: 'S2026-000014',
    className: '软件2302', classId: 'c-2302',
    topicTitle: '基于微信小程序的社区团购系统',
    advisorId: 't-004', advisorName: '钱立群',
    stage: 'MIDTERM', stageLabel: '中期检查（限期整改）',
    materialSummary: '中期整改中 · 期限 07-10', plagiarismRate: '—', plagiarismTone: 'default',
    riskLevel: 'MEDIUM', phone: '15812343307'
  },
  {
    id: 'gd-004', studentId: 'stu-015', name: '李嘉豪', studentNo: 'S2026-000015',
    className: '软件2302', classId: 'c-2302',
    topicTitle: '（未确认选题）',
    advisorId: '', advisorName: '未分配',
    stage: 'TOPIC_SELECTING', stageLabel: '选题中',
    materialSummary: '选题逾期 6 天（GD-R02）', plagiarismRate: '—', plagiarismTone: 'default',
    riskLevel: 'HIGH', phone: '13912340774'
  },
  {
    id: 'gd-005', studentId: 'stu-016', name: '张启铭', studentNo: 'S2026-000016',
    className: '软件2301', classId: 'c-2301',
    topicTitle: '高校实验室预约管理系统的设计与实现',
    advisorId: 't-005', advisorName: '孙晓梅',
    stage: 'DEFENSE', stageLabel: '答辩中',
    materialSummary: '第 2 组 · 07-08 上午', plagiarismRate: '9.8%', plagiarismTone: 'success',
    riskLevel: 'NONE', phone: '13512340228'
  },
  {
    id: 'gd-006', studentId: 'stu-017', name: '黄雅静', studentNo: 'S2026-000017',
    className: '软件2302', classId: 'c-2302',
    topicTitle: '基于数据可视化的销售分析平台',
    advisorId: 't-004', advisorName: '钱立群',
    stage: 'GUIDING', stageLabel: '指导中',
    materialSummary: '开题 v2 待审阅', plagiarismRate: '—', plagiarismTone: 'default',
    riskLevel: 'NONE', phone: '18712341190'
  },
  {
    id: 'gd-007', studentId: 'stu-018', name: '徐子涵', studentNo: 'S2026-000018',
    className: '软件2301', classId: 'c-2301',
    topicTitle: '在线考试与题库管理系统',
    advisorId: 't-005', advisorName: '孙晓梅',
    stage: 'ARCHIVED', stageLabel: '已归档',
    materialSummary: '归档编号 GD-AR-0630-02', plagiarismRate: '11.3%', plagiarismTone: 'success',
    riskLevel: 'NONE', phone: '15012340663'
  },
  {
    id: 'gd-008', studentId: 'stu-019', name: '宋雨桐', studentNo: 'S2026-000019',
    className: '软件2302', classId: 'c-2302',
    topicTitle: '餐饮门店智能点单系统的设计与实现',
    advisorId: 't-001', advisorName: '王芳',
    stage: 'TASKBOOK_CONFIRM', stageLabel: '任务书确认',
    materialSummary: '任务书 v2 待学生确认', plagiarismRate: '—', plagiarismTone: 'default',
    riskLevel: 'NONE', phone: '13312340815'
  }
]

export const studentDetailMap = {
  'gd-001': {
    id: 'gd-001', name: '陈思雨', studentNo: 'S2026-000002', className: '软件2301',
    phone: '13612340552', stage: 'FINAL_CHECK', stageLabel: '成果检查', riskLevel: 'NONE',
    topicTitle: '基于 Vue3 的校园二手交易平台设计与实现',
    topicSource: '教师申报课题 · 王芳', advisorName: '王芳（副教授 · 软件教研室）',
    taskbook: '任务书 v1 · 已确认（2025-12-05）',
    stateFlow: [
      { title: '选题确认（学生选题 → 导师确认）', time: '2025-11-28', tone: 'success' },
      { title: '任务书下达并确认', time: '2025-12-05', tone: 'success' },
      { title: '开题报告 v2 通过', time: '2026-01-10', tone: 'success' },
      { title: '中期检查：通过', time: '2026-04-15', tone: 'success' },
      { title: '成果检查（当前）· 定稿 v3 待审', time: '进行中', tone: 'processing' },
      { title: '答辩 · 成绩 · 归档', time: '未到达', tone: 'default' }
    ],
    proposals: [
      { id: 'pr-101', type: '开题报告', version: 'v2', submitAt: '2026-01-08', status: 'APPROVED', reviewer: '王芳' },
      { id: 'pr-102', type: '开题报告', version: 'v1', submitAt: '2025-12-28', status: 'REJECTED', reviewer: '王芳' }
    ],
    midterm: { conclusion: '通过', time: '2026-04-15', note: '进度符合任务书要求，注意补充测试章节' },
    finals: [
      { id: 'fn-101', type: '定稿', version: 'v3', submitAt: '2026-06-28', status: 'PENDING_REVIEW', plagiarism: '12.6% · 达标' },
      { id: 'fn-102', type: '初稿', version: 'v1', submitAt: '2026-05-30', status: 'APPROVED', plagiarism: '18.4% · 达标' }
    ],
    plagiarisms: [
      { id: 'pl-101', version: '定稿 v3', rate: '12.6%', status: '完成', time: '2026-06-29', report: '查重报告-v3.pdf' },
      { id: 'pl-102', version: '初稿 v1', rate: '18.4%', status: '完成', time: '2026-06-01', report: '查重报告-v1.pdf' }
    ],
    defense: { group: '第 3 组', time: '2026-07-09 09:00', location: '实训楼 B402', secretary: '孙晓梅', published: true },
    auditTrail: [
      { who: '陈思雨（学生端）', time: '06-28 21:40', action: '提交定稿 v3', affected: '来自学生端 P15 毕设提交' },
      { who: '系统', time: '06-29 08:00', action: '查重完成', affected: '定稿 v3 查重率 12.6% · 报告已关联（P16 可查看）' },
      { who: '张文澜 · 学院管理员', time: '06-25 10:12', action: '发布答辩安排', affected: '第 3 组 12 人 · 学生端 P17 已同步' }
    ]
  }
}

/** 选题管理 */
export const topicList = [
  {
    id: 'tp-001', title: '基于 Vue3 的校园二手交易平台设计与实现', source: '教师申报',
    advisorName: '王芳', majorName: '软件技术', capacity: 2, selected: 2,
    status: 'CONFIRMED', statusLabel: '已确认', students: ['陈思雨', '刘一鸣']
  },
  {
    id: 'tp-002', title: '基于微信小程序的社区团购系统', source: '教师申报',
    advisorName: '钱立群', majorName: '软件技术', capacity: 2, selected: 1,
    status: 'CONFIRMED', statusLabel: '已确认', students: ['王梓涵']
  },
  {
    id: 'tp-003', title: '企业网络安全等保测评辅助工具', source: '企业课题',
    advisorName: '孙晓梅', majorName: '信息安全', capacity: 1, selected: 0,
    status: 'PENDING_CONFIRM', statusLabel: '待确认', students: []
  },
  {
    id: 'tp-004', title: '校园能耗监测与可视化平台', source: '教师申报',
    advisorName: '钱立群', majorName: '软件技术', capacity: 2, selected: 0,
    status: 'DISABLED', statusLabel: '已停用', students: [],
    disabledNote: '停用于 06-02 · 原因：与另一课题重复 · 操作人 张文澜'
  },
  {
    id: 'tp-005', title: '餐饮门店智能点单系统的设计与实现', source: '学生自拟',
    advisorName: '王芳', majorName: '软件技术', capacity: 1, selected: 1,
    status: 'CONFIRMED', statusLabel: '已确认', students: ['宋雨桐']
  }
]

/** 开题材料列表（学生 P15 提交 → 教师 T24 → PC 批阅） */
export const proposalList = [
  {
    id: 'pp-001', projectId: 'gd-006', studentName: '黄雅静', className: '软件2302',
    topicTitle: '基于数据可视化的销售分析平台', advisorName: '钱立群',
    version: 'v2', isResubmit: true, submitAt: '07-01 20:18', attachments: 2,
    status: 'PENDING_REVIEW', statusLabel: '待审阅'
  },
  {
    id: 'pp-002', projectId: 'gd-008', studentName: '宋雨桐', className: '软件2302',
    topicTitle: '餐饮门店智能点单系统的设计与实现', advisorName: '王芳',
    version: 'v1', isResubmit: false, submitAt: '06-30 22:41', attachments: 1,
    status: 'PENDING_REVIEW', statusLabel: '待审阅'
  },
  {
    id: 'pp-003', projectId: 'gd-001', studentName: '陈思雨', className: '软件2301',
    topicTitle: '基于 Vue3 的校园二手交易平台设计与实现', advisorName: '王芳',
    version: 'v2', isResubmit: true, submitAt: '01-08 19:02', attachments: 2,
    status: 'APPROVED', statusLabel: '已通过'
  },
  {
    id: 'pp-004', projectId: 'gd-004', studentName: '李嘉豪', className: '软件2302',
    topicTitle: '（未确认选题）', advisorName: '未分配',
    version: '—', isResubmit: false, submitAt: '', attachments: 0,
    status: 'NOT_SUBMITTED', statusLabel: '逾期未交（GD-R04）'
  }
]

export const proposalReviewDetailMap = {
  'pp-001': {
    id: 'pp-001', projectId: 'gd-006', studentName: '黄雅静', className: '软件2302',
    topicTitle: '基于数据可视化的销售分析平台', advisorName: '钱立群',
    version: 'v2', isResubmit: true, submitAt: '07-01 20:18',
    content: {
      background: '零售企业销售数据分散在多个系统，缺乏统一可视化分析入口，人工汇总耗时且易错。',
      plan: '采用 Vue3 + ECharts 构建前端看板，Node 侧做数据聚合；分四阶段：需求分析（2 周）、原型（3 周）、开发（8 周）、测试与撰写（3 周）。',
      outcome: '可运行系统 + 毕业论文 + 部署文档；核心指标看板支持钻取与导出。'
    },
    attachments: ['开题报告-v2.docx', '文献综述.pdf'],
    versions: [
      { title: 'v2 · 重新提交（当前审阅版本）', desc: '按批注补充了技术路线与进度甘特图', time: '07-01 20:18', tone: 'processing' },
      { title: 'v1 · 被驳回', desc: '驳回原因：研究内容与专业培养目标结合不足，进度安排缺少里程碑，请补充技术路线。', time: '06-25 09:40 · 钱立群', tone: 'danger' },
      { title: 'v1 · 首次提交', desc: '', time: '06-23 21:35', tone: 'default' }
    ],
    status: 'PENDING_REVIEW',
    trail: [
      { who: '钱立群', time: '06-25 09:40', action: '驳回 v1', affected: '原因已同步学生端（退回提醒不可关闭）' },
      { who: '黄雅静（学生端）', time: '07-01 20:18', action: '重交 v2', affected: '来自学生端 P15 毕设提交' }
    ]
  }
}

/** 成果提交列表（定稿 / 初稿 + 查重） */
export const finalSubmissionList = [
  {
    id: 'fs-001', projectId: 'gd-001', studentName: '陈思雨', className: '软件2301',
    topicTitle: '基于 Vue3 的校园二手交易平台设计与实现', advisorName: '王芳',
    type: '定稿', version: 'v3', submitAt: '06-28 21:40',
    plagiarismRate: '12.6%', plagiarismStatus: '达标', plagiarismTone: 'success',
    status: 'PENDING_REVIEW', statusLabel: '待审阅'
  },
  {
    id: 'fs-002', projectId: 'gd-002', studentName: '刘一鸣', className: '软件2301',
    topicTitle: '中小企业进销存管理系统的设计与实现', advisorName: '王芳',
    type: '定稿', version: 'v2', submitAt: '06-27 23:02',
    plagiarismRate: '34.2%', plagiarismStatus: '超标（阈值 30%）', plagiarismTone: 'danger',
    status: 'REJECTED', statusLabel: '已退回修改'
  },
  {
    id: 'fs-003', projectId: 'gd-005', studentName: '张启铭', className: '软件2301',
    topicTitle: '高校实验室预约管理系统的设计与实现', advisorName: '孙晓梅',
    type: '定稿', version: 'v2', submitAt: '06-20 18:15',
    plagiarismRate: '9.8%', plagiarismStatus: '达标', plagiarismTone: 'success',
    status: 'APPROVED', statusLabel: '已通过（进入答辩）'
  },
  {
    id: 'fs-004', projectId: 'gd-006', studentName: '黄雅静', className: '软件2302',
    topicTitle: '基于数据可视化的销售分析平台', advisorName: '钱立群',
    type: '初稿', version: 'v1', submitAt: '',
    plagiarismRate: '—', plagiarismStatus: '未检测', plagiarismTone: 'default',
    status: 'NOT_SUBMITTED', statusLabel: '未提交'
  }
]

/** 答辩安排（分组 / 时间 / 地点 / 评委 / 发布状态） */
export const defenseScheduleList = [
  {
    id: 'df-001', groupName: '第 1 组', date: '2026-07-08 09:00', location: '实训楼 B401',
    chair: '周正邦（教授）', members: ['孙晓梅', '外聘 · 华信智能 陈总监'], secretary: '林小婉',
    studentCount: 12, conflict: '', published: true, publishedLabel: '已发布（学生端 P17 可见）'
  },
  {
    id: 'df-002', groupName: '第 2 组', date: '2026-07-08 13:30', location: '实训楼 B402',
    chair: '吴敬亭（教授）', members: ['王芳', '钱立群'], secretary: '林小婉',
    studentCount: 12, conflict: '', published: true, publishedLabel: '已发布（学生端 P17 可见）'
  },
  {
    id: 'df-003', groupName: '第 3 组', date: '2026-07-09 09:00', location: '实训楼 B402',
    chair: '周正邦（教授）', members: ['孙晓梅', '外聘 · 星辰网络 郑架构师'], secretary: '林小婉',
    studentCount: 12, conflict: '', published: true, publishedLabel: '已发布（学生端 P17 可见）'
  },
  {
    id: 'df-004', groupName: '第 4 组', date: '2026-07-09 13:30', location: '实训楼 B403',
    chair: '吴敬亭（教授）', members: ['王芳', '钱立群'], secretary: '待指定',
    studentCount: 11, conflict: '评委含指导教师本人（王芳 ↔ 3 名学生），已拦截',
    published: false, publishedLabel: '待调整后发布'
  },
  {
    id: 'df-005', groupName: '第 5 组', date: '待排期', location: '待定',
    chair: '待指定', members: [], secretary: '待指定',
    studentCount: 13, conflict: '', published: false, publishedLabel: '待安排'
  }
]
