/**
 * 04 学业过程中心 — mock 数据源（内存态，可被 api 写操作变更）。
 * 口径来自《04-学业过程中心深化设计 V1.0》：本中心不替代教务系统，
 * 课程/成绩/学分数据以“同步/导入摘要”的形式进入本系统，做学业画像、预警与帮扶跟进。
 * 约定：
 *  - 学校名/平台名/Logo/水印/角色/数据范围全部由 tenantBrandConfig 与 roles 提供，页面禁止硬编码。
 *  - 删除一律逻辑作废（recordStatus = VOIDED），保留原因并写审计。
 *  - permissionActions / fieldColumns / filterOptions / batchActions / importTemplates / exportOptions
 *    均由本文件下发，页面不得自行写死。
 *  - 页面禁止直接 import 本文件，必须经 modules/academic/api 获取。
 */

export const nowText = () => {
  const d = new Date()
  const p = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`
}

/* ---------------- 租户品牌（模拟后端下发） ---------------- */
export const tenantBrandConfig = {
  tenantId: 'tenant-demo-001',
  schoolName: '演示职业技术学院',
  platformDisplayName: '高校学生全生命周期管理平台',
  schoolLogo: '/assets/tenant/demo-logo.svg',
  schoolBadge: '/assets/tenant/demo-badge.svg',
  tenantBrandColor: '#2563EB',
  watermarkText: '演示职业技术学院 · 学业过程中心'
}

/* ---------------- 角色与数据范围（04 §4 使用角色） ---------------- */
export const roles = [
  {
    roleId: 'COLLEGE_ADMIN',
    roleName: '学院管理员',
    userName: '张文澜',
    dataScope: { code: 'COLLEGE', name: '信息工程学院' }
  },
  {
    roleId: 'COUNSELOR',
    roleName: '辅导员',
    userName: '李敏',
    dataScope: { code: 'CLASS', name: '软件2301班 / 软件2302班' }
  },
  {
    roleId: 'COURSE_TEACHER',
    roleName: '任课教师',
    userName: '王芳',
    dataScope: { code: 'COURSE', name: '我任教的课程（Web前端开发 / Java程序设计）' }
  },
  {
    roleId: 'ACADEMIC_AFFAIRS',
    roleName: '教务老师',
    userName: '周建国',
    dataScope: { code: 'SCHOOL', name: '全校（教务口径）' }
  },
  {
    roleId: 'REGISTRAR',
    roleName: '学籍老师',
    userName: '郑淑华',
    dataScope: { code: 'SCHOOL', name: '全校（学籍口径 · 统计只读）' }
  }
]

export const state = { currentRoleId: 'COLLEGE_ADMIN' }

/* ---------------- 权限动作（按角色下发） ---------------- */
const FULL = {
  'academic.record.create': true,
  'academic.record.view': true,
  'academic.record.edit': true,
  'academic.record.void': true,
  'academic.record.import': true,
  'academic.record.export': true,
  'academic.record.batchRemind': true,
  'academic.grade.create': true,
  'academic.grade.edit': true,
  'academic.grade.void': true,
  'academic.grade.import': true,
  'academic.grade.export': true,
  'academic.credit.export': true,
  'academic.makeup.create': true,
  'academic.makeup.edit': true,
  'academic.makeup.batchRemind': true,
  'academic.makeup.export': true,
  'academic.warning.create': true,
  'academic.warning.editLevel': true,
  'academic.warning.void': true,
  'academic.warning.assign': true,
  'academic.warning.followup': true,
  'academic.warning.close': true,
  'academic.warning.escalate': true,
  'academic.warning.batchRemind': true,
  'academic.warning.batchAssign': true,
  'academic.warning.export': true,
  'academic.audit.view': true,
  'academic.columns.setting': true
}

/**
 * allowed=false 且 visible=true → 按钮置灰并提示原因；visible=false（hidden）→ 不渲染（涉密收敛）。
 */
export const permissionActionsByRole = {
  COLLEGE_ADMIN: { actions: FULL, hidden: [], disabledReason: '' },
  COUNSELOR: {
    actions: {
      ...FULL,
      'academic.record.create': false,
      'academic.record.void': false,
      'academic.record.import': false,
      'academic.grade.create': false,
      'academic.grade.edit': false,
      'academic.grade.void': false,
      'academic.grade.import': false,
      'academic.makeup.create': false,
      'academic.makeup.edit': false,
      'academic.warning.void': false,
      'academic.warning.batchAssign': false
    },
    hidden: [],
    disabledReason: '辅导员角色负责学业预警跟进与提醒，成绩与学业台账由教务/学院维护'
  },
  COURSE_TEACHER: {
    actions: {
      ...FULL,
      'academic.record.create': false,
      'academic.record.edit': false,
      'academic.record.void': false,
      'academic.record.import': false,
      'academic.makeup.create': false,
      'academic.makeup.edit': false,
      'academic.warning.editLevel': false,
      'academic.warning.void': false,
      'academic.warning.assign': false,
      'academic.warning.close': false,
      'academic.warning.escalate': false,
      'academic.warning.batchAssign': false
    },
    hidden: ['academic.record.export', 'academic.warning.export', 'academic.credit.export'],
    disabledReason: '任课教师仅可维护本人任教课程的成绩，并对学业预警发起上报'
  },
  ACADEMIC_AFFAIRS: {
    actions: {
      ...FULL,
      'academic.warning.followup': false,
      'academic.warning.close': false
    },
    hidden: [],
    disabledReason: '教务老师负责成绩/学分口径维护与分派，预警跟进与关闭由辅导员/学院完成'
  },
  REGISTRAR: {
    actions: Object.fromEntries(
      Object.keys(FULL).map((k) => [
        k,
        k.endsWith('.view') ||
          k === 'academic.audit.view' ||
          k === 'academic.columns.setting' ||
          k === 'academic.record.export' ||
          k === 'academic.credit.export'
      ])
    ),
    hidden: ['academic.warning.batchRemind', 'academic.warning.batchAssign'],
    disabledReason: '学籍老师为学籍口径统计角色，仅可查看与导出（脱敏），不可执行业务写操作'
  }
}

/* ---------------- 字典 ---------------- */
export const statusOptions = {
  terms: [
    { value: '2025-2026-2', label: '2025-2026 学年第二学期' },
    { value: '2025-2026-1', label: '2025-2026 学年第一学期' },
    { value: '2024-2025-2', label: '2024-2025 学年第二学期' }
  ],
  courseNature: [
    { value: 'REQUIRED', label: '必修' },
    { value: 'ELECTIVE', label: '选修' },
    { value: 'PRACTICE', label: '实践' }
  ],
  passStatus: [
    { value: 'PASSED', label: '通过' },
    { value: 'FAILED', label: '未通过' },
    { value: 'PENDING', label: '待发布' }
  ],
  examType: [
    { value: 'FINAL', label: '期末考试' },
    { value: 'MAKEUP', label: '补考' },
    { value: 'RETAKE', label: '重修考核' }
  ],
  academicStatus: [
    { value: 'NORMAL', label: '正常' },
    { value: 'WARNING', label: '预警中' },
    { value: 'HELPING', label: '帮扶中' }
  ],
  makeupStatus: [
    { value: 'PENDING_EXAM', label: '待补考' },
    { value: 'PASSED', label: '补考通过' },
    { value: 'FAILED', label: '补考未过' },
    { value: 'ABSENT', label: '缺考' }
  ],
  retakeStatus: [
    { value: 'ENROLLING', label: '报名中' },
    { value: 'STUDYING', label: '修读中' },
    { value: 'PASSED', label: '重修通过' },
    { value: 'FAILED', label: '重修未过' }
  ],
  warningType: [
    { value: 'MULTI_FAIL', label: '多门挂科' },
    { value: 'CREDIT_GAP', label: '学分不足' },
    { value: 'GRADE_DROP', label: '成绩持续下滑' },
    { value: 'ATTENDANCE', label: '出勤异常' },
    { value: 'GRAD_RISK', label: '毕业资格风险' }
  ],
  warningLevel: [
    { value: 'LOW', label: '低风险' },
    { value: 'MEDIUM', label: '中风险' },
    { value: 'HIGH', label: '高风险' }
  ],
  warningStatus: [
    { value: 'PENDING_HANDLE', label: '待处理' },
    { value: 'PROCESSING', label: '跟进中' },
    { value: 'CLOSED', label: '已关闭' },
    { value: 'ESCALATED', label: '已升级' }
  ],
  creditStatus: [
    { value: 'ON_TRACK', label: '达标' },
    { value: 'BEHIND', label: '滞后' },
    { value: 'SEVERE', label: '严重滞后' }
  ],
  recordStatus: [
    { value: 'ACTIVE', label: '有效' },
    { value: 'VOIDED', label: '已作废' }
  ]
}

export const filterOptions = {
  colleges: [
    { value: 'C01', label: '信息工程学院' },
    { value: 'C02', label: '智能制造学院' }
  ],
  classes: [
    { value: 'CL01', label: '软件2301班' },
    { value: 'CL02', label: '软件2302班' },
    { value: 'CL03', label: '大数据2301班' },
    { value: 'CL04', label: '机电2301班' }
  ],
  courses: [
    { value: 'crs-001', label: 'Web前端开发' },
    { value: 'crs-002', label: 'Java程序设计' },
    { value: 'crs-003', label: '数据库原理' },
    { value: 'crs-004', label: '高等数学' },
    { value: 'crs-005', label: '大学英语' },
    { value: 'crs-006', label: '计算机网络' }
  ],
  owners: [
    { value: 'u-limin', label: '李敏（辅导员）' },
    { value: 'u-zhangwenlan', label: '张文澜（学院管理员）' },
    { value: 'u-zhoujianguo', label: '周建国（教务老师）' }
  ]
}

/* ---------------- 列设置 ---------------- */
export const fieldColumns = {
  studentList: [
    { key: 'name', title: '学生', locked: true, default: true },
    { key: 'className', title: '班级', default: true },
    { key: 'gpa', title: 'GPA', default: true },
    { key: 'avgScore', title: '平均成绩', default: false },
    { key: 'failedCount', title: '挂科门数', default: true },
    { key: 'credit', title: '学分进度', default: true },
    { key: 'makeupRetake', title: '补考/重修', default: true },
    { key: 'warning', title: '学业预警', default: true },
    { key: 'status', title: '学业状态', default: true },
    { key: 'phone', title: '手机号', sensitive: true, default: false },
    { key: 'counselor', title: '辅导员', default: false },
    { key: 'updateTime', title: '更新时间', default: false },
    { key: 'actions', title: '操作', locked: true, default: true }
  ],
  gradeList: [
    { key: 'name', title: '学生', locked: true, default: true },
    { key: 'className', title: '班级', default: true },
    { key: 'courseName', title: '课程', default: true },
    { key: 'term', title: '学期', default: true },
    { key: 'nature', title: '课程性质', default: false },
    { key: 'creditValue', title: '学分', default: true },
    { key: 'score', title: '成绩', default: true },
    { key: 'passStatus', title: '是否通过', default: true },
    { key: 'examType', title: '考试类型', default: true },
    { key: 'sourceBatch', title: '来源批次', default: false },
    { key: 'updateTime', title: '更新时间', default: false },
    { key: 'actions', title: '操作', locked: true, default: true }
  ],
  creditList: [
    { key: 'name', title: '学生', locked: true, default: true },
    { key: 'className', title: '班级', default: true },
    { key: 'obtained', title: '已获学分', default: true },
    { key: 'required', title: '应修学分', default: true },
    { key: 'progress', title: '完成进度', default: true },
    { key: 'categories', title: '分类完成情况', default: true },
    { key: 'gap', title: '缺口', default: true },
    { key: 'status', title: '状态', default: true },
    { key: 'actions', title: '操作', locked: true, default: true }
  ],
  makeupList: [
    { key: 'name', title: '学生', locked: true, default: true },
    { key: 'className', title: '班级', default: true },
    { key: 'courseName', title: '课程', default: true },
    { key: 'term', title: '学期', default: true },
    { key: 'originScore', title: '原成绩', default: true },
    { key: 'examDate', title: '考核安排', default: true },
    { key: 'status', title: '状态', default: true },
    { key: 'remindCount', title: '已提醒', default: false },
    { key: 'actions', title: '操作', locked: true, default: true }
  ],
  warningList: [
    { key: 'code', title: '预警编号', locked: true, default: true },
    { key: 'name', title: '学生', default: true },
    { key: 'className', title: '班级', default: true },
    { key: 'type', title: '预警类型', default: true },
    { key: 'level', title: '风险等级', default: true },
    { key: 'reason', title: '触发原因', default: true },
    { key: 'owner', title: '跟进人', default: true },
    { key: 'status', title: '处理状态', default: true },
    { key: 'triggerTime', title: '触发时间', default: true },
    { key: 'deadline', title: '处理期限', default: false },
    { key: 'actions', title: '操作', locked: true, default: true }
  ]
}

/* ---------------- 批量操作 ---------------- */
export const batchActions = {
  studentList: [
    { key: 'batchRemind', label: '批量提醒学生', permission: 'academic.record.batchRemind' },
    { key: 'batchExport', label: '导出选中', permission: 'academic.record.export' }
  ],
  gradeList: [{ key: 'batchExport', label: '导出选中成绩', permission: 'academic.grade.export' }],
  makeupList: [
    { key: 'batchRemind', label: '批量提醒补考/重修', permission: 'academic.makeup.batchRemind' },
    { key: 'batchExport', label: '导出选中名单', permission: 'academic.makeup.export' }
  ],
  warningList: [
    { key: 'batchRemind', label: '批量提醒', permission: 'academic.warning.batchRemind' },
    { key: 'batchAssign', label: '批量分配跟进人', permission: 'academic.warning.batchAssign' },
    { key: 'batchExport', label: '导出预警名单', permission: 'academic.warning.export' }
  ]
}

/* ---------------- 导入模板 ---------------- */
export const importTemplates = {
  studentList: {
    key: 'studentList',
    name: '学业学生台账导入模板',
    fileName: '学业学生导入模板.xlsx',
    fields: [
      { key: 'studentNo', label: '学号', required: true, example: '2023010101' },
      { key: 'name', label: '姓名', required: true, example: '张三' },
      { key: 'className', label: '班级', required: true, example: '软件2301班' },
      { key: 'requiredCredits', label: '应修学分', required: true, example: '120' },
      { key: 'obtainedCredits', label: '已获学分', required: false, example: '64.5' }
    ]
  },
  gradeList: {
    key: 'gradeList',
    name: '课程成绩导入模板（教务导出口径）',
    fileName: '课程成绩导入模板.xlsx',
    fields: [
      { key: 'studentNo', label: '学号', required: true, example: '2023010101' },
      { key: 'courseName', label: '课程名称', required: true, example: 'Web前端开发' },
      { key: 'term', label: '学期', required: true, example: '2025-2026-2' },
      { key: 'score', label: '成绩', required: true, example: '86' },
      { key: 'examType', label: '考试类型', required: false, example: '期末考试' }
    ]
  }
}

/* ---------------- 导出配置 ---------------- */
export const exportOptions = {
  scopes: [
    { value: 'FILTERED', label: '当前筛选结果' },
    { value: 'SELECTED', label: '仅选中记录' },
    { value: 'SCOPE_ALL', label: '数据范围内全部' }
  ],
  fieldGroups: {
    studentList: [
      { key: 'base', label: '基础信息', fields: ['姓名', '学号', '班级', '学业状态'] },
      { key: 'academic', label: '学业信息', fields: ['GPA', '平均成绩', '挂科门数', '学分进度', '预警等级'] },
      { key: 'sensitive', label: '敏感信息（默认脱敏）', sensitive: true, fields: ['手机号', '身份证号（仅脱敏）'] }
    ],
    gradeList: [
      { key: 'base', label: '成绩记录', fields: ['学生', '课程', '学期', '成绩', '是否通过', '考试类型', '来源批次'] }
    ],
    creditList: [
      { key: 'base', label: '学分台账', fields: ['学生', '班级', '已获学分', '应修学分', '分类完成情况', '缺口'] }
    ],
    makeupList: [
      { key: 'base', label: '补考/重修名单', fields: ['学生', '班级', '课程', '原成绩', '考核安排', '状态'] },
      { key: 'sensitive', label: '敏感信息（默认脱敏）', sensitive: true, fields: ['手机号'] }
    ],
    warningList: [
      { key: 'base', label: '预警名单', fields: ['预警编号', '学生', '班级', '类型', '等级', '触发原因', '跟进人', '状态'] },
      { key: 'sensitive', label: '敏感信息（默认脱敏）', sensitive: true, fields: ['手机号'] }
    ]
  },
  maskDefault: true,
  idCardPlainForbidden: true,
  watermarkNote: '导出文件将自动嵌入水印（学校名 · 操作人 · 时间 · 用途），并写入审计日志。',
  auditNotice: '本次导出行为将被完整记录并可追溯，请确认导出用途合规。'
}

/* ---------------- 学业学生台账 ---------------- */
const STU = (id, name, no, classId, className, extras = {}) => ({
  id,
  studentId: id,
  name,
  studentNo: no,
  gender: extras.gender || '男',
  collegeId: extras.collegeId || 'C01',
  collegeName: extras.collegeName || '信息工程学院',
  majorName: extras.majorName || '软件技术',
  classId,
  className,
  grade: '2023级',
  phone: extras.phone || '13800001234',
  idCard: extras.idCard || '330102200501011234',
  counselor: extras.counselor || '李敏',
  gpa: extras.gpa ?? 3.1,
  avgScore: extras.avgScore ?? 81,
  failedCount: extras.failedCount ?? 0,
  obtainedCredits: extras.obtainedCredits ?? 66,
  requiredCredits: extras.requiredCredits ?? 120,
  makeupCount: extras.makeupCount ?? 0,
  retakeCount: extras.retakeCount ?? 0,
  warningLevel: extras.warningLevel || 'NONE',
  warningCount: extras.warningCount ?? 0,
  academicStatus: extras.academicStatus || 'NORMAL',
  recordStatus: 'ACTIVE',
  voidReason: '',
  updateTime: extras.updateTime || '2026-06-30 09:40'
})

export const academicStudents = [
  STU('acad-s-001', '陈晓峰', '2023010101', 'CL01', '软件2301班', { gpa: 3.5, avgScore: 88, obtainedCredits: 72 }),
  STU('acad-s-002', '林嘉怡', '2023010102', 'CL01', '软件2301班', { gender: '女', gpa: 3.7, avgScore: 90, obtainedCredits: 74 }),
  STU('acad-s-003', '赵子墨', '2023010103', 'CL01', '软件2301班', {
    gpa: 2.1, avgScore: 68, failedCount: 2, obtainedCredits: 58, makeupCount: 1, retakeCount: 1,
    warningLevel: 'MEDIUM', warningCount: 1, academicStatus: 'HELPING'
  }),
  STU('acad-s-004', '王雨桐', '2023010104', 'CL01', '软件2301班', {
    gender: '女', gpa: 1.6, avgScore: 55, failedCount: 3, obtainedCredits: 46, makeupCount: 2, retakeCount: 1,
    warningLevel: 'HIGH', warningCount: 2, academicStatus: 'WARNING', updateTime: '2026-07-01 15:20'
  }),
  STU('acad-s-005', '孙浩然', '2023010205', 'CL02', '软件2302班', {
    gpa: 2.6, avgScore: 74, failedCount: 1, obtainedCredits: 62, makeupCount: 1,
    warningLevel: 'LOW', warningCount: 1, academicStatus: 'WARNING'
  }),
  STU('acad-s-006', '吴思远', '2023010206', 'CL02', '软件2302班', { gpa: 3.2, avgScore: 84, obtainedCredits: 70 }),
  STU('acad-s-007', '郑婉婷', '2023010207', 'CL02', '软件2302班', {
    gender: '女', gpa: 2.4, avgScore: 72, obtainedCredits: 52, warningLevel: 'MEDIUM', warningCount: 1, academicStatus: 'WARNING'
  }),
  STU('acad-s-008', '刘俊熙', '2023010208', 'CL02', '软件2302班', {
    gpa: 2.8, avgScore: 76, failedCount: 1, obtainedCredits: 64, retakeCount: 1
  }),
  STU('acad-s-009', '黄一诺', '2023020109', 'CL03', '大数据2301班', {
    gender: '女', majorName: '大数据技术', counselor: '钱辅导', gpa: 3.8, avgScore: 92, obtainedCredits: 76
  }),
  STU('acad-s-010', '徐博文', '2023020110', 'CL03', '大数据2301班', {
    majorName: '大数据技术', counselor: '钱辅导', gpa: 2.9, avgScore: 78, obtainedCredits: 66,
    warningLevel: 'LOW', warningCount: 1, academicStatus: 'WARNING'
  }),
  STU('acad-s-011', '高子轩', '2023030112', 'CL04', '机电2301班', {
    collegeId: 'C02', collegeName: '智能制造学院', majorName: '机电一体化', counselor: '孙辅导',
    gpa: 3.0, avgScore: 82, obtainedCredits: 68
  }),
  STU('acad-s-012', '罗芷晴', '2023030113', 'CL04', '机电2301班', {
    gender: '女', collegeId: 'C02', collegeName: '智能制造学院', majorName: '机电一体化', counselor: '孙辅导',
    gpa: 2.3, avgScore: 70, failedCount: 1, obtainedCredits: 56, makeupCount: 1,
    warningLevel: 'MEDIUM', warningCount: 1, academicStatus: 'WARNING'
  })
]

/* ---------------- 课程摘要（同步自教务，本系统只读维护摘要） ---------------- */
export const courseRecords = [
  {
    id: 'crs-001', courseName: 'Web前端开发', term: '2025-2026-2', nature: 'REQUIRED', credit: 4,
    teacherName: '王芳', classNames: '软件2301班 / 软件2302班', studentCount: 86, avgScore: 81.5, passRate: 91.9, pendingGrades: 0
  },
  {
    id: 'crs-002', courseName: 'Java程序设计', term: '2025-2026-2', nature: 'REQUIRED', credit: 4,
    teacherName: '王芳', classNames: '软件2301班 / 软件2302班', studentCount: 86, avgScore: 76.2, passRate: 84.9, pendingGrades: 2
  },
  {
    id: 'crs-003', courseName: '数据库原理', term: '2025-2026-2', nature: 'REQUIRED', credit: 3,
    teacherName: '钱立群', classNames: '软件2301班 / 软件2302班 / 大数据2301班', studentCount: 128, avgScore: 74.8, passRate: 82.0, pendingGrades: 0
  },
  {
    id: 'crs-004', courseName: '高等数学', term: '2025-2026-1', nature: 'REQUIRED', credit: 4,
    teacherName: '孙晓梅', classNames: '全院大一班级', studentCount: 326, avgScore: 71.3, passRate: 78.5, pendingGrades: 0
  },
  {
    id: 'crs-005', courseName: '大学英语', term: '2025-2026-1', nature: 'REQUIRED', credit: 3,
    teacherName: '李华', classNames: '全院大一班级', studentCount: 326, avgScore: 75.6, passRate: 85.3, pendingGrades: 0
  },
  {
    id: 'crs-006', courseName: '计算机网络', term: '2025-2026-2', nature: 'ELECTIVE', credit: 2,
    teacherName: '吴刚', classNames: '软件2301班 / 大数据2301班', studentCount: 64, avgScore: 79.4, passRate: 93.8, pendingGrades: 0
  }
]

/* ---------------- 成绩记录 ---------------- */
const GRADE = (id, studentId, name, classId, className, courseId, courseName, term, nature, creditValue, score, examType, extras = {}) => ({
  id,
  studentId,
  name,
  classId,
  className,
  courseId,
  courseName,
  term,
  nature,
  creditValue,
  score,
  passStatus: extras.passStatus || (score >= 60 ? 'PASSED' : 'FAILED'),
  examType,
  sourceBatch: extras.sourceBatch || 'IMP-20260620-01',
  recordStatus: 'ACTIVE',
  voidReason: '',
  updateTime: extras.updateTime || '2026-06-20 10:30'
})

export const gradeRecords = [
  GRADE('acad-g-001', 'acad-s-001', '陈晓峰', 'CL01', '软件2301班', 'crs-001', 'Web前端开发', '2025-2026-2', 'REQUIRED', 4, 92, 'FINAL'),
  GRADE('acad-g-002', 'acad-s-002', '林嘉怡', 'CL01', '软件2301班', 'crs-001', 'Web前端开发', '2025-2026-2', 'REQUIRED', 4, 95, 'FINAL'),
  GRADE('acad-g-003', 'acad-s-004', '王雨桐', 'CL01', '软件2301班', 'crs-001', 'Web前端开发', '2025-2026-2', 'REQUIRED', 4, 52, 'FINAL', { updateTime: '2026-06-21 09:00' }),
  GRADE('acad-g-004', 'acad-s-004', '王雨桐', 'CL01', '软件2301班', 'crs-002', 'Java程序设计', '2025-2026-2', 'REQUIRED', 4, 48, 'FINAL'),
  GRADE('acad-g-005', 'acad-s-004', '王雨桐', 'CL01', '软件2301班', 'crs-004', '高等数学', '2025-2026-1', 'REQUIRED', 4, 55, 'MAKEUP', { sourceBatch: 'IMP-20260305-02' }),
  GRADE('acad-g-006', 'acad-s-003', '赵子墨', 'CL01', '软件2301班', 'crs-002', 'Java程序设计', '2025-2026-2', 'REQUIRED', 4, 54, 'FINAL'),
  GRADE('acad-g-007', 'acad-s-003', '赵子墨', 'CL01', '软件2301班', 'crs-003', '数据库原理', '2025-2026-2', 'REQUIRED', 3, 58, 'FINAL'),
  GRADE('acad-g-008', 'acad-s-005', '孙浩然', 'CL02', '软件2302班', 'crs-003', '数据库原理', '2025-2026-2', 'REQUIRED', 3, 56, 'FINAL'),
  GRADE('acad-g-009', 'acad-s-006', '吴思远', 'CL02', '软件2302班', 'crs-002', 'Java程序设计', '2025-2026-2', 'REQUIRED', 4, 85, 'FINAL'),
  GRADE('acad-g-010', 'acad-s-007', '郑婉婷', 'CL02', '软件2302班', 'crs-001', 'Web前端开发', '2025-2026-2', 'REQUIRED', 4, 73, 'FINAL'),
  GRADE('acad-g-011', 'acad-s-008', '刘俊熙', 'CL02', '软件2302班', 'crs-004', '高等数学', '2025-2026-1', 'REQUIRED', 4, 62, 'RETAKE', { sourceBatch: 'IMP-20260628-03', updateTime: '2026-06-28 16:10' }),
  GRADE('acad-g-012', 'acad-s-009', '黄一诺', 'CL03', '大数据2301班', 'crs-003', '数据库原理', '2025-2026-2', 'REQUIRED', 3, 96, 'FINAL'),
  GRADE('acad-g-013', 'acad-s-010', '徐博文', 'CL03', '大数据2301班', 'crs-006', '计算机网络', '2025-2026-2', 'ELECTIVE', 2, 66, 'FINAL'),
  GRADE('acad-g-014', 'acad-s-012', '罗芷晴', 'CL04', '机电2301班', 'crs-004', '高等数学', '2025-2026-1', 'REQUIRED', 4, 45, 'FINAL')
]

/* ---------------- 学分修读台账 ---------------- */
export const creditRecords = academicStudents.map((s, i) => {
  const gap = Math.max(0, Math.round((s.requiredCredits / 2 - s.obtainedCredits / 1) * 10) / 10)
  const midRequired = 60
  const behind = s.obtainedCredits < midRequired - 6
  return {
    id: `acad-c-${String(i + 1).padStart(3, '0')}`,
    studentId: s.id,
    name: s.name,
    classId: s.classId,
    className: s.className,
    collegeId: s.collegeId,
    obtained: s.obtainedCredits,
    required: s.requiredCredits,
    midRequired,
    categories: [
      { key: 'REQUIRED', label: '必修', obtained: Math.round(s.obtainedCredits * 0.7 * 10) / 10, required: 80 },
      { key: 'ELECTIVE', label: '选修', obtained: Math.round(s.obtainedCredits * 0.2 * 10) / 10, required: 24 },
      { key: 'PRACTICE', label: '实践', obtained: Math.round(s.obtainedCredits * 0.1 * 10) / 10, required: 16 }
    ],
    gap: s.obtainedCredits >= midRequired ? 0 : Math.round((midRequired - s.obtainedCredits) * 10) / 10,
    status: s.obtainedCredits >= midRequired ? 'ON_TRACK' : behind ? 'SEVERE' : 'BEHIND',
    term: '2025-2026-2',
    _gapHint: gap
  }
})

/* ---------------- 考试记录（学生详情页使用） ---------------- */
export const examRecords = [
  { id: 'acad-e-001', studentId: 'acad-s-004', courseName: 'Web前端开发', term: '2025-2026-2', examType: 'FINAL', examDate: '2026-06-18', result: '52 分 · 未通过' },
  { id: 'acad-e-002', studentId: 'acad-s-004', courseName: 'Java程序设计', term: '2025-2026-2', examType: 'FINAL', examDate: '2026-06-20', result: '48 分 · 未通过' },
  { id: 'acad-e-003', studentId: 'acad-s-004', courseName: '高等数学', term: '2025-2026-1', examType: 'MAKEUP', examDate: '2026-03-02', result: '55 分 · 未通过' },
  { id: 'acad-e-004', studentId: 'acad-s-003', courseName: 'Java程序设计', term: '2025-2026-2', examType: 'FINAL', examDate: '2026-06-20', result: '54 分 · 未通过' },
  { id: 'acad-e-005', studentId: 'acad-s-003', courseName: '数据库原理', term: '2025-2026-2', examType: 'FINAL', examDate: '2026-06-22', result: '58 分 · 未通过' },
  { id: 'acad-e-006', studentId: 'acad-s-001', courseName: 'Web前端开发', term: '2025-2026-2', examType: 'FINAL', examDate: '2026-06-18', result: '92 分 · 通过' }
]

/* ---------------- 补考记录 ---------------- */
export const makeupExamRecords = [
  {
    id: 'acad-mk-001', studentId: 'acad-s-004', name: '王雨桐', classId: 'CL01', className: '软件2301班', collegeId: 'C01',
    courseId: 'crs-001', courseName: 'Web前端开发', term: '2025-2026-2', originScore: 52,
    examDate: '2026-09-06 09:00 · 实训楼A302', status: 'PENDING_EXAM', remindCount: 1,
    recordStatus: 'ACTIVE', voidReason: '', updateTime: '2026-07-01 10:00'
  },
  {
    id: 'acad-mk-002', studentId: 'acad-s-004', name: '王雨桐', classId: 'CL01', className: '软件2301班', collegeId: 'C01',
    courseId: 'crs-002', courseName: 'Java程序设计', term: '2025-2026-2', originScore: 48,
    examDate: '2026-09-07 09:00 · 实训楼A302', status: 'PENDING_EXAM', remindCount: 1,
    recordStatus: 'ACTIVE', voidReason: '', updateTime: '2026-07-01 10:00'
  },
  {
    id: 'acad-mk-003', studentId: 'acad-s-005', name: '孙浩然', classId: 'CL02', className: '软件2302班', collegeId: 'C01',
    courseId: 'crs-003', courseName: '数据库原理', term: '2025-2026-2', originScore: 56,
    examDate: '2026-09-06 14:00 · 实训楼A304', status: 'PENDING_EXAM', remindCount: 0,
    recordStatus: 'ACTIVE', voidReason: '', updateTime: '2026-06-28 09:20'
  },
  {
    id: 'acad-mk-004', studentId: 'acad-s-003', name: '赵子墨', classId: 'CL01', className: '软件2301班', collegeId: 'C01',
    courseId: 'crs-003', courseName: '数据库原理', term: '2025-2026-2', originScore: 58,
    examDate: '2026-09-06 14:00 · 实训楼A304', status: 'PENDING_EXAM', remindCount: 2,
    recordStatus: 'ACTIVE', voidReason: '', updateTime: '2026-06-30 17:00'
  },
  {
    id: 'acad-mk-005', studentId: 'acad-s-012', name: '罗芷晴', classId: 'CL04', className: '机电2301班', collegeId: 'C02',
    courseId: 'crs-004', courseName: '高等数学', term: '2025-2026-1', originScore: 45,
    examDate: '2026-03-02 已考', status: 'FAILED', remindCount: 1,
    recordStatus: 'ACTIVE', voidReason: '', updateTime: '2026-03-05 11:00'
  }
]

/* ---------------- 重修记录 ---------------- */
export const retakeRecords = [
  {
    id: 'acad-rt-001', studentId: 'acad-s-004', name: '王雨桐', classId: 'CL01', className: '软件2301班', collegeId: 'C01',
    courseId: 'crs-004', courseName: '高等数学', retakeTerm: '2026-2027-1', reason: '补考未通过，转入重修',
    status: 'ENROLLING', recordStatus: 'ACTIVE', voidReason: '', updateTime: '2026-06-25 09:00'
  },
  {
    id: 'acad-rt-002', studentId: 'acad-s-003', name: '赵子墨', classId: 'CL01', className: '软件2301班', collegeId: 'C01',
    courseId: 'crs-002', courseName: 'Java程序设计', retakeTerm: '2026-2027-1', reason: '期末未通过且缺勤超 1/3，按规定直接重修',
    status: 'ENROLLING', recordStatus: 'ACTIVE', voidReason: '', updateTime: '2026-06-26 15:30'
  },
  {
    id: 'acad-rt-003', studentId: 'acad-s-008', name: '刘俊熙', classId: 'CL02', className: '软件2302班', collegeId: 'C01',
    courseId: 'crs-004', courseName: '高等数学', retakeTerm: '2025-2026-2', reason: '上学年未通过',
    status: 'PASSED', recordStatus: 'ACTIVE', voidReason: '', updateTime: '2026-06-28 16:10'
  }
]

/* ---------------- 学业预警 ---------------- */
export const academicWarnings = [
  {
    id: 'acad-w-001', code: 'AW-2026-0007', studentId: 'acad-s-004', name: '王雨桐', classId: 'CL01', className: '软件2301班', collegeId: 'C01',
    type: 'MULTI_FAIL', level: 'HIGH', reason: '本学期 2 门必修未通过，累计 3 门挂科（规则 ACAD-R03）',
    sourceRule: 'ACAD-R03 · 多门挂科自动预警', owner: '李敏（辅导员）', ownerId: 'u-limin',
    status: 'PROCESSING', triggerTime: '2026-06-22 08:00', deadline: '2026-07-10', overdue: false,
    remindCount: 2, recordStatus: 'ACTIVE', voidReason: ''
  },
  {
    id: 'acad-w-002', code: 'AW-2026-0008', studentId: 'acad-s-004', name: '王雨桐', classId: 'CL01', className: '软件2301班', collegeId: 'C01',
    type: 'CREDIT_GAP', level: 'HIGH', reason: '已获学分 46 / 中期应达 60，缺口 14 学分（规则 ACAD-R05）',
    sourceRule: 'ACAD-R05 · 学分进度预警', owner: '李敏（辅导员）', ownerId: 'u-limin',
    status: 'PENDING_HANDLE', triggerTime: '2026-06-30 08:00', deadline: '2026-07-15', overdue: false,
    remindCount: 0, recordStatus: 'ACTIVE', voidReason: ''
  },
  {
    id: 'acad-w-003', code: 'AW-2026-0009', studentId: 'acad-s-003', name: '赵子墨', classId: 'CL01', className: '软件2301班', collegeId: 'C01',
    type: 'MULTI_FAIL', level: 'MEDIUM', reason: '本学期 2 门必修未通过（规则 ACAD-R03）',
    sourceRule: 'ACAD-R03 · 多门挂科自动预警', owner: '李敏（辅导员）', ownerId: 'u-limin',
    status: 'PROCESSING', triggerTime: '2026-06-23 08:00', deadline: '2026-07-12', overdue: false,
    remindCount: 1, recordStatus: 'ACTIVE', voidReason: ''
  },
  {
    id: 'acad-w-004', code: 'AW-2026-0010', studentId: 'acad-s-007', name: '郑婉婷', classId: 'CL02', className: '软件2302班', collegeId: 'C01',
    type: 'CREDIT_GAP', level: 'MEDIUM', reason: '已获学分 52 / 中期应达 60，缺口 8 学分（规则 ACAD-R05）',
    sourceRule: 'ACAD-R05 · 学分进度预警', owner: '张文澜（学院管理员）', ownerId: 'u-zhangwenlan',
    status: 'PENDING_HANDLE', triggerTime: '2026-06-30 08:00', deadline: '2026-07-15', overdue: false,
    remindCount: 0, recordStatus: 'ACTIVE', voidReason: ''
  },
  {
    id: 'acad-w-005', code: 'AW-2026-0011', studentId: 'acad-s-010', name: '徐博文', classId: 'CL03', className: '大数据2301班', collegeId: 'C01',
    type: 'GRADE_DROP', level: 'LOW', reason: '连续两学期平均成绩下滑超过 8 分（规则 ACAD-R01）',
    sourceRule: 'ACAD-R01 · 成绩下滑预警', owner: '钱辅导（辅导员）', ownerId: 'u-qian',
    status: 'CLOSED', triggerTime: '2026-05-12 08:00', deadline: '2026-05-30', overdue: false,
    remindCount: 1, recordStatus: 'ACTIVE', voidReason: '', closeResult: '已面谈并制定学习计划，第 18 周复核成绩回升'
  },
  {
    id: 'acad-w-006', code: 'AW-2026-0012', studentId: 'acad-s-012', name: '罗芷晴', classId: 'CL04', className: '机电2301班', collegeId: 'C02',
    type: 'MULTI_FAIL', level: 'MEDIUM', reason: '高等数学补考未通过，转重修（规则 ACAD-R04）',
    sourceRule: 'ACAD-R04 · 补考未过预警', owner: '孙辅导（辅导员）', ownerId: 'u-sun',
    status: 'PROCESSING', triggerTime: '2026-03-06 08:00', deadline: '2026-07-20', overdue: false,
    remindCount: 1, recordStatus: 'ACTIVE', voidReason: ''
  }
]

/* ---------------- 预警干预 / 跟进记录 ---------------- */
export const interventionRecords = [
  {
    id: 'acad-i-001', warningId: 'acad-w-001', studentName: '王雨桐',
    time: '2026-06-24 15:00', way: 'TALK', wayLabel: '当面谈话',
    content: '与学生面谈，了解挂科原因：兼职时间过长影响学习，情绪状态一般。',
    result: '学生同意减少兼职时长，约定每周三晚自习辅导', nextPlan: '一周后复谈，同步任课教师课后辅导安排',
    operator: '李敏（辅导员）', status: 'OPEN', voidReason: ''
  },
  {
    id: 'acad-i-002', warningId: 'acad-w-001', studentName: '王雨桐',
    time: '2026-06-28 19:30', way: 'FAMILY', wayLabel: '家校联系',
    content: '电话联系家长，说明学业预警情况与补考安排。',
    result: '家长知晓并配合督促，同意暑期在家复习', nextPlan: '9 月初补考前再次提醒',
    operator: '李敏（辅导员）', status: 'OPEN', voidReason: ''
  },
  {
    id: 'acad-i-003', warningId: 'acad-w-003', studentName: '赵子墨',
    time: '2026-06-25 10:00', way: 'PLAN', wayLabel: '帮扶计划',
    content: '制定「一对一学习结对」帮扶计划，由陈晓峰同学结对辅导 Java 程序设计。',
    result: '帮扶计划已启动', nextPlan: '第 20 周检查作业完成情况',
    operator: '李敏（辅导员）', status: 'OPEN', voidReason: ''
  },
  {
    id: 'acad-i-004', warningId: 'acad-w-005', studentName: '徐博文',
    time: '2026-05-20 14:00', way: 'TALK', wayLabel: '当面谈话',
    content: '面谈了解成绩下滑原因：沉迷游戏，作息紊乱。',
    result: '制定作息与学习计划，宿舍长协助监督', nextPlan: '期末复核',
    operator: '钱辅导（辅导员）', status: 'CLOSED', voidReason: ''
  }
]

/* ---------------- 预警详情 ---------------- */
export const warningDetailExtras = {
  'acad-w-001': {
    relatedGrades: ['Web前端开发 · 52 分（期末）', 'Java程序设计 · 48 分（期末）', '高等数学 · 55 分（补考）'],
    relatedCredits: '已获学分 46 / 中期应达 60（缺口 14）',
    historyWarnings: ['AW-2025-0031 · 成绩下滑 · 已关闭（2025-12）'],
    suggestion: '建议维持高风险等级，暑期补考前每周跟进一次；若 9 月补考仍未通过，升级至学院学业帮扶专班。'
  },
  'acad-w-002': {
    relatedGrades: ['本学期 2 门必修未通过（合计 8 学分未获得）'],
    relatedCredits: '已获学分 46 / 中期应达 60（缺口 14）',
    historyWarnings: ['AW-2026-0007 · 多门挂科 · 跟进中'],
    suggestion: '与 AW-2026-0007 合并跟进，重点关注重修报名与学分补齐路径。'
  },
  'acad-w-003': {
    relatedGrades: ['Java程序设计 · 54 分（期末）', '数据库原理 · 58 分（期末）'],
    relatedCredits: '已获学分 58 / 中期应达 60（缺口 2）',
    historyWarnings: [],
    suggestion: '已启动结对帮扶，建议补考前完成两轮辅导。'
  }
}

/* ---------------- 审计日志 ---------------- */
export const auditLogs = [
  {
    id: 'acad-a-001', time: '2026-06-30 08:00', operator: '系统', roleName: '预警引擎',
    bizType: 'WARNING', bizId: 'acad-w-002', action: '触发预警',
    detail: 'ACAD-R05 学分进度预警命中：王雨桐 缺口 14 学分', before: '', after: 'PENDING_HANDLE'
  },
  {
    id: 'acad-a-002', time: '2026-06-28 19:35', operator: '李敏', roleName: '辅导员',
    bizType: 'INTERVENTION', bizId: 'acad-i-002', action: '新增跟进',
    detail: '王雨桐 · 家校联系，家长配合督促', before: '', after: 'OPEN'
  },
  {
    id: 'acad-a-003', time: '2026-06-20 10:30', operator: '周建国', roleName: '教务老师',
    bizType: 'IMPORT', bizId: 'IMP-20260620-01', action: '导入成绩',
    detail: '导入 2025-2026-2 期末成绩 428 条（校验通过 426 条，失败 2 条未导入）', before: '', after: ''
  },
  {
    id: 'acad-a-004', time: '2026-06-05 16:20', operator: '张文澜', roleName: '学院管理员',
    bizType: 'EXPORT', bizId: 'warningList', action: '导出预警名单',
    detail: '导出学业预警名单 6 条（手机号已脱敏，含水印）', before: '', after: ''
  },
  {
    id: 'acad-a-005', time: '2026-05-30 11:00', operator: '钱辅导', roleName: '辅导员',
    bizType: 'WARNING', bizId: 'acad-w-005', action: '关闭预警',
    detail: '徐博文 · 成绩下滑预警关闭：面谈后成绩回升', before: 'PROCESSING', after: 'CLOSED'
  }
]

/* ---------------- 看板 ---------------- */
export const dashboardSummary = {
  termName: '2025-2026 学年第二学期',
  termRange: '2026-02-23 ~ 2026-07-12',
  updateTime: '2026-07-03 08:30',
  flow: [
    { label: '数据同步', value: 3 },
    { label: '预警生成', value: 6 },
    { label: '跟进中', value: 3, active: true },
    { label: '已关闭', value: 1 },
    { label: '已归档', value: 0 }
  ],
  recentImportBatches: [
    { id: 'IMP-20260628-03', name: '重修考核成绩（高等数学）', time: '2026-06-28 16:10', total: 32, success: 32, failed: 0, operator: '周建国' },
    { id: 'IMP-20260620-01', name: '2025-2026-2 期末成绩', time: '2026-06-20 10:30', total: 428, success: 426, failed: 2, operator: '周建国' },
    { id: 'IMP-20260305-02', name: '2025-2026-1 补考成绩', time: '2026-03-05 09:40', total: 57, success: 57, failed: 0, operator: '周建国' }
  ],
  riskAlerts: [
    { id: 'acad-ra-001', level: 'HIGH', title: '1 名学生累计 3 门挂科且学分缺口超 10 分，存在毕业风险', link: 'warnings' },
    { id: 'acad-ra-002', level: 'MEDIUM', title: '2 条学分进度预警超过 3 天未领取处理', link: 'warnings' },
    { id: 'acad-ra-003', level: 'MEDIUM', title: '4 名学生 9 月补考未确认，需批量提醒', link: 'makeup' }
  ],
  todos: [
    { id: 'acad-t-001', label: '待处理学业预警', value: 2, link: 'warnings' },
    { id: 'acad-t-002', label: '待提醒补考学生', value: 4, link: 'makeup' },
    { id: 'acad-t-003', label: '学分严重滞后学生', value: 2, link: 'credits' }
  ]
}
