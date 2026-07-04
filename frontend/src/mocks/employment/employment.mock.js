/**
 * 07 就业服务中心 — mock 数据源（内存态，可被 api 写操作变更）。
 * 约定：
 *  - 学校名/平台名/Logo/水印/角色/数据范围全部由 tenantBrandConfig 与 roles 提供，页面禁止硬编码。
 *  - 删除一律为逻辑作废（recordStatus = VOIDED），保留原因与审计。
 *  - permissionActions / fieldColumns / filterOptions / batchActions / importTemplates / exportOptions
 *    均由本文件下发，页面不得自行写死。
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
  watermarkText: '演示职业技术学院 · 就业服务中心'
}

/* ---------------- 角色与数据范围 ---------------- */
export const roles = [
  {
    roleId: 'EMP_TEACHER',
    roleName: '就业老师',
    dataScope: { code: 'COLLEGE', name: '信息工程学院' }
  },
  {
    roleId: 'COUNSELOR',
    roleName: '辅导员',
    dataScope: { code: 'CLASS', name: '软件2301班 / 软件2302班' }
  },
  {
    roleId: 'COLLEGE_ADMIN',
    roleName: '学院管理员',
    dataScope: { code: 'COLLEGE', name: '信息工程学院' }
  },
  {
    roleId: 'ACADEMIC_TEACHER',
    roleName: '教务老师',
    dataScope: { code: 'SCHOOL', name: '全校（统计只读）' }
  }
]

export const state = { currentRoleId: 'EMP_TEACHER' }

/* ---------------- 权限动作（按角色下发） ---------------- */
const FULL = {
  'employment.record.create': true,
  'employment.record.view': true,
  'employment.record.edit': true,
  'employment.record.void': true,
  'employment.record.import': true,
  'employment.record.export': true,
  'employment.record.batchRemind': true,
  'employment.record.batchMarkStatus': true,
  'employment.material.review': true,
  'employment.material.export': true,
  'employment.followup.create': true,
  'employment.followup.edit': true,
  'employment.followup.void': true,
  'employment.followup.export': true,
  'employment.unemployed.assign': true,
  'employment.unemployed.markEmployed': true,
  'employment.unemployed.markKeyHelp': true,
  'employment.unemployed.export': true,
  'employment.company.create': true,
  'employment.company.edit': true,
  'employment.company.disable': true,
  'employment.company.import': true,
  'employment.company.export': true,
  'employment.job.create': true,
  'employment.job.edit': true,
  'employment.job.disable': true,
  'employment.audit.view': true,
  'employment.columns.setting': true
}

/**
 * allowed=false 且 visible=true → 按钮置灰并提示原因；visible=false → 不渲染（涉密收敛）。
 */
export const permissionActionsByRole = {
  EMP_TEACHER: { actions: FULL, disabledReason: '' },
  COUNSELOR: {
    actions: {
      ...FULL,
      'employment.record.import': false,
      'employment.company.create': false,
      'employment.company.edit': false,
      'employment.company.disable': false,
      'employment.company.import': false,
      'employment.job.create': false,
      'employment.job.edit': false,
      'employment.job.disable': false,
      'employment.unemployed.assign': false
    },
    hidden: [],
    disabledReason: '辅导员角色仅可维护本班学生就业与跟进信息'
  },
  COLLEGE_ADMIN: { actions: FULL, disabledReason: '' },
  ACADEMIC_TEACHER: {
    actions: Object.fromEntries(
      Object.keys(FULL).map((k) => [k, k.endsWith('.view') || k === 'employment.audit.view' || k === 'employment.columns.setting'])
    ),
    hidden: [
      'employment.record.import',
      'employment.record.export',
      'employment.material.export',
      'employment.followup.export',
      'employment.unemployed.export',
      'employment.company.import',
      'employment.company.export'
    ],
    disabledReason: '教务老师为统计只读角色，不可执行业务写操作'
  }
}

/* ---------------- 字典 ---------------- */
export const statusOptions = {
  destinationType: [
    { value: 'SIGNED', label: '签约就业' },
    { value: 'FLEXIBLE', label: '灵活就业' },
    { value: 'FURTHER_STUDY', label: '升学' },
    { value: 'ENLISTED', label: '入伍' },
    { value: 'STARTUP', label: '自主创业' },
    { value: 'FREELANCE', label: '自由职业' },
    { value: 'UNEMPLOYED', label: '待就业' }
  ],
  verifyStatus: [
    { value: 'PENDING_VERIFY', label: '待核验' },
    { value: 'VERIFIED', label: '已核验' },
    { value: 'RETURNED', label: '已退回' }
  ],
  materialStatus: [
    { value: 'SUBMITTED', label: '待审核' },
    { value: 'REVIEWING', label: '审核中' },
    { value: 'APPROVED', label: '已通过' },
    { value: 'RETURNED', label: '退回补充' },
    { value: 'REJECTED', label: '已驳回' }
  ],
  materialType: [
    { value: 'AGREEMENT', label: '就业协议' },
    { value: 'CONTRACT', label: '劳动合同' },
    { value: 'OFFER', label: '录用通知' },
    { value: 'STUDY_PROOF', label: '升学证明' },
    { value: 'ENLIST_PROOF', label: '入伍证明' },
    { value: 'STARTUP_PROOF', label: '创业证明' },
    { value: 'OTHER', label: '其他材料' }
  ],
  helpLevel: [
    { value: 'NORMAL', label: '常规跟进' },
    { value: 'KEY_HELP', label: '重点帮扶' }
  ],
  recordStatus: [
    { value: 'ACTIVE', label: '有效' },
    { value: 'VOIDED', label: '已作废' }
  ],
  followUpWay: [
    { value: 'PHONE', label: '电话联系' },
    { value: 'FACE', label: '面谈' },
    { value: 'RECOMMEND', label: '岗位推荐' },
    { value: 'VISIT', label: '走访' }
  ],
  followUpStatus: [
    { value: 'OPEN', label: '跟进中' },
    { value: 'CLOSED', label: '已闭环' },
    { value: 'VOIDED', label: '已作废' }
  ],
  companyStatus: [
    { value: 'ACTIVE', label: '合作中' },
    { value: 'DISABLED', label: '已停用' }
  ],
  jobStatus: [
    { value: 'OPEN', label: '招聘中' },
    { value: 'CLOSED', label: '已停止' }
  ],
  riskLevel: [
    { value: 'LOW', label: '低风险' },
    { value: 'MEDIUM', label: '中风险' },
    { value: 'HIGH', label: '高风险' }
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
  grades: [{ value: '2026', label: '2026届' }]
}

/* ---------------- 列设置 ---------------- */
export const fieldColumns = {
  studentList: [
    { key: 'name', title: '姓名', locked: true, default: true },
    { key: 'studentNo', title: '学号', default: true },
    { key: 'className', title: '班级', default: true },
    { key: 'destinationType', title: '去向类型', default: true },
    { key: 'companyName', title: '单位 / 院校', default: true },
    { key: 'jobTitle', title: '岗位', default: false },
    { key: 'salaryRange', title: '薪资区间', sensitive: true, default: false },
    { key: 'phone', title: '手机号', sensitive: true, default: false },
    { key: 'verifyStatus', title: '核验状态', default: true },
    { key: 'materialStatus', title: '材料状态', default: true },
    { key: 'helpLevel', title: '帮扶级别', default: true },
    { key: 'updateTime', title: '更新时间', default: false },
    { key: 'actions', title: '操作', locked: true, default: true }
  ],
  materialList: [
    { key: 'name', title: '学生', locked: true, default: true },
    { key: 'className', title: '班级', default: true },
    { key: 'materialType', title: '材料类型', default: true },
    { key: 'fileName', title: '材料文件', default: true },
    { key: 'submitTime', title: '提交时间', default: true },
    { key: 'status', title: '审核状态', default: true },
    { key: 'reviewer', title: '审核人', default: false },
    { key: 'actions', title: '操作', locked: true, default: true }
  ],
  unemployedList: [
    { key: 'name', title: '姓名', locked: true, default: true },
    { key: 'className', title: '班级', default: true },
    { key: 'unemployedReason', title: '未就业原因', default: true },
    { key: 'helpLevel', title: '帮扶级别', default: true },
    { key: 'riskLevel', title: '风险', default: true },
    { key: 'assignedTeacher', title: '负责老师', default: true },
    { key: 'lastFollowUpTime', title: '最近跟进', default: true },
    { key: 'followUpCount', title: '跟进次数', default: false },
    { key: 'actions', title: '操作', locked: true, default: true }
  ],
  followUpList: [
    { key: 'studentName', title: '学生', locked: true, default: true },
    { key: 'className', title: '班级', default: true },
    { key: 'followTime', title: '跟进时间', default: true },
    { key: 'way', title: '跟进方式', default: true },
    { key: 'content', title: '跟进内容', default: true },
    { key: 'result', title: '结果', default: true },
    { key: 'operator', title: '记录人', default: false },
    { key: 'status', title: '状态', default: true },
    { key: 'actions', title: '操作', locked: true, default: true }
  ],
  companyList: [
    { key: 'name', title: '企业名称', locked: true, default: true },
    { key: 'industry', title: '行业', default: true },
    { key: 'nature', title: '性质', default: false },
    { key: 'city', title: '城市', default: true },
    { key: 'cooperationLevel', title: '合作级别', default: true },
    { key: 'jobCount', title: '在招岗位', default: true },
    { key: 'hiredCount', title: '已录用', default: true },
    { key: 'status', title: '状态', default: true },
    { key: 'actions', title: '操作', locked: true, default: true }
  ],
  jobList: [
    { key: 'title', title: '岗位名称', locked: true, default: true },
    { key: 'companyName', title: '企业', default: true },
    { key: 'category', title: '岗位类别', default: true },
    { key: 'salaryRange', title: '薪资区间', default: true },
    { key: 'headcount', title: '需求人数', default: true },
    { key: 'signedCount', title: '已签约', default: true },
    { key: 'status', title: '状态', default: true },
    { key: 'actions', title: '操作', locked: true, default: true }
  ]
}

/* ---------------- 批量操作 ---------------- */
export const batchActions = {
  studentList: [
    { key: 'batchRemind', label: '批量提醒填报', permission: 'employment.record.batchRemind' },
    { key: 'batchMarkStatus', label: '批量标记去向', permission: 'employment.record.batchMarkStatus' },
    { key: 'batchExport', label: '导出选中', permission: 'employment.record.export' }
  ],
  materialList: [
    { key: 'batchApprove', label: '批量通过', permission: 'employment.material.review' },
    { key: 'batchReturn', label: '批量退回', permission: 'employment.material.review' }
  ],
  unemployedList: [
    { key: 'batchRemind', label: '批量提醒', permission: 'employment.record.batchRemind' },
    { key: 'batchAssign', label: '批量分配就业老师', permission: 'employment.unemployed.assign' },
    { key: 'batchExport', label: '导出选中', permission: 'employment.unemployed.export' }
  ]
}

/* ---------------- 导入模板 ---------------- */
export const importTemplates = {
  studentList: {
    key: 'studentList',
    name: '就业学生台账导入模板',
    fileName: '就业学生导入模板.xlsx',
    fields: [
      { key: 'studentNo', label: '学号', required: true, example: '2023010101' },
      { key: 'name', label: '姓名', required: true, example: '张三' },
      { key: 'destinationType', label: '去向类型', required: true, example: '签约就业' },
      { key: 'companyName', label: '单位/院校名称', required: false, example: '杭州云启科技有限公司' },
      { key: 'jobTitle', label: '岗位', required: false, example: '前端开发工程师' },
      { key: 'signDate', label: '签约时间', required: false, example: '2026-05-12' }
    ]
  },
  companyList: {
    key: 'companyList',
    name: '企业与岗位导入模板',
    fileName: '企业岗位导入模板.xlsx',
    fields: [
      { key: 'companyName', label: '企业名称', required: true, example: '杭州云启科技有限公司' },
      { key: 'creditCode', label: '统一社会信用代码', required: true, example: '91330100MA27XXXX' },
      { key: 'industry', label: '行业', required: true, example: '软件和信息技术服务业' },
      { key: 'jobTitle', label: '岗位名称', required: false, example: '前端开发工程师' },
      { key: 'headcount', label: '需求人数', required: false, example: '5' }
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
      { key: 'base', label: '基础信息', fields: ['姓名', '学号', '班级', '去向类型'] },
      { key: 'employ', label: '就业信息', fields: ['单位/院校', '岗位', '签约时间', '核验状态'] },
      {
        key: 'sensitive',
        label: '敏感信息（默认脱敏）',
        sensitive: true,
        fields: ['手机号', '薪资区间', '身份证号（仅脱敏）']
      }
    ],
    materialList: [
      { key: 'base', label: '审核记录', fields: ['学生', '材料类型', '提交时间', '审核状态', '审核人', '审核意见'] }
    ],
    unemployedList: [
      { key: 'base', label: '未就业名单', fields: ['姓名', '班级', '未就业原因', '帮扶级别', '负责老师', '最近跟进'] },
      { key: 'sensitive', label: '敏感信息（默认脱敏）', sensitive: true, fields: ['手机号'] }
    ],
    followUpList: [{ key: 'base', label: '跟进记录', fields: ['学生', '跟进时间', '方式', '内容', '结果', '记录人'] }],
    companyList: [
      { key: 'base', label: '企业信息', fields: ['企业名称', '信用代码', '行业', '城市', '合作级别'] },
      { key: 'job', label: '岗位信息', fields: ['岗位名称', '类别', '薪资区间', '需求人数', '已签约'] }
    ]
  },
  maskDefault: true,
  idCardPlainForbidden: true,
  watermarkNote: '导出文件将自动嵌入水印（学校名 · 操作人 · 时间 · 用途），并写入审计日志。',
  auditNotice: '本次导出行为将被完整记录并可追溯，请确认导出用途合规。'
}

/* ---------------- 就业学生台账 ---------------- */
const STU = (
  id,
  name,
  no,
  classId,
  className,
  destinationType,
  companyName,
  jobTitle,
  salaryRange,
  verifyStatus,
  materialStatus,
  helpLevel,
  riskLevel,
  extras = {}
) => ({
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
  grade: '2026届',
  phone: extras.phone || '13800001234',
  idCard: extras.idCard || '330102200501011234',
  destinationType,
  companyName,
  jobTitle,
  salaryRange,
  contractType: extras.contractType || (destinationType === 'SIGNED' ? 'AGREEMENT' : ''),
  signDate: extras.signDate || '',
  isMatchMajor: extras.isMatchMajor ?? true,
  fromInternship: extras.fromInternship ?? false,
  verifyStatus,
  materialStatus,
  helpLevel,
  riskLevel,
  recordStatus: 'ACTIVE',
  voidReason: '',
  counselor: extras.counselor || '李辅导',
  employmentTeacher: extras.employmentTeacher || '王就业',
  unemployedReason: extras.unemployedReason || '',
  lastFollowUpTime: extras.lastFollowUpTime || '',
  followUpCount: extras.followUpCount || 0,
  updateTime: extras.updateTime || '2026-06-28 10:20'
})

export const employmentStudents = [
  STU('emp-s-001', '陈晓峰', '2023010101', 'CL01', '软件2301班', 'SIGNED', '杭州云启科技有限公司', '前端开发工程师', '6k-8k', 'VERIFIED', 'APPROVED', 'NORMAL', 'LOW', {
    signDate: '2026-05-12',
    fromInternship: true
  }),
  STU('emp-s-002', '林嘉怡', '2023010102', 'CL01', '软件2301班', 'SIGNED', '宁波数联智能有限公司', '测试工程师', '5k-7k', 'PENDING_VERIFY', 'SUBMITTED', 'NORMAL', 'LOW', {
    gender: '女',
    signDate: '2026-06-02'
  }),
  STU('emp-s-003', '赵子墨', '2023010103', 'CL01', '软件2301班', 'FURTHER_STUDY', '浙江工业职业技术大学', '专升本 · 软件工程', '', 'VERIFIED', 'APPROVED', 'NORMAL', 'LOW'),
  STU('emp-s-004', '王雨桐', '2023010104', 'CL01', '软件2301班', 'UNEMPLOYED', '', '', '', 'PENDING_VERIFY', 'SUBMITTED', 'KEY_HELP', 'HIGH', {
    gender: '女',
    unemployedReason: '求职意向未明确，多次面试未通过',
    lastFollowUpTime: '2026-06-25 15:00',
    followUpCount: 3
  }),
  STU('emp-s-005', '孙浩然', '2023010205', 'CL02', '软件2302班', 'FLEXIBLE', '自由接单（UI 设计）', '自由职业设计师', '4k-6k', 'RETURNED', 'RETURNED', 'NORMAL', 'MEDIUM', {
    counselor: '周辅导'
  }),
  STU('emp-s-006', '吴思远', '2023010206', 'CL02', '软件2302班', 'ENLISTED', '中国人民解放军', '义务兵', '', 'VERIFIED', 'APPROVED', 'NORMAL', 'LOW', {
    counselor: '周辅导'
  }),
  STU('emp-s-007', '郑婉婷', '2023010207', 'CL02', '软件2302班', 'UNEMPLOYED', '', '', '', 'PENDING_VERIFY', 'SUBMITTED', 'KEY_HELP', 'HIGH', {
    gender: '女',
    counselor: '周辅导',
    unemployedReason: '家庭困难，需要就近就业',
    lastFollowUpTime: '2026-06-20 09:30',
    followUpCount: 5
  }),
  STU('emp-s-008', '刘俊熙', '2023010208', 'CL02', '软件2302班', 'STARTUP', '杭州星尘文化创意工作室', '创始人', '', 'PENDING_VERIFY', 'REVIEWING', 'NORMAL', 'MEDIUM', {
    counselor: '周辅导'
  }),
  STU('emp-s-009', '黄一诺', '2023020109', 'CL03', '大数据2301班', 'SIGNED', '上海慧算数据服务有限公司', '数据分析专员', '6k-8k', 'VERIFIED', 'APPROVED', 'NORMAL', 'LOW', {
    gender: '女',
    majorName: '大数据技术',
    counselor: '钱辅导',
    signDate: '2026-04-28'
  }),
  STU('emp-s-010', '徐博文', '2023020110', 'CL03', '大数据2301班', 'UNEMPLOYED', '', '', '', 'PENDING_VERIFY', 'SUBMITTED', 'NORMAL', 'MEDIUM', {
    majorName: '大数据技术',
    counselor: '钱辅导',
    unemployedReason: '备考公务员，暂缓求职',
    lastFollowUpTime: '2026-06-18 14:00',
    followUpCount: 2
  }),
  STU('emp-s-011', '马诗涵', '2023020111', 'CL03', '大数据2301班', 'FREELANCE', '短视频内容创作者', '自媒体运营', '3k-5k', 'RETURNED', 'RETURNED', 'NORMAL', 'MEDIUM', {
    gender: '女',
    majorName: '大数据技术',
    counselor: '钱辅导'
  }),
  STU('emp-s-012', '高子轩', '2023030112', 'CL04', '机电2301班', 'SIGNED', '宁波精工智造股份有限公司', '设备运维技术员', '5k-7k', 'VERIFIED', 'APPROVED', 'NORMAL', 'LOW', {
    collegeId: 'C02',
    collegeName: '智能制造学院',
    majorName: '机电一体化',
    counselor: '孙辅导',
    employmentTeacher: '吴就业',
    signDate: '2026-05-30',
    fromInternship: true
  }),
  STU('emp-s-013', '罗芷晴', '2023030113', 'CL04', '机电2301班', 'UNEMPLOYED', '', '', '', 'PENDING_VERIFY', 'SUBMITTED', 'KEY_HELP', 'HIGH', {
    gender: '女',
    collegeId: 'C02',
    collegeName: '智能制造学院',
    majorName: '机电一体化',
    counselor: '孙辅导',
    employmentTeacher: '吴就业',
    unemployedReason: '身体原因暂缓就业，需持续关注',
    lastFollowUpTime: '2026-06-27 16:40',
    followUpCount: 4
  }),
  STU('emp-s-014', '朱天佑', '2023030114', 'CL04', '机电2301班', 'SIGNED', '苏州联合汽车电子有限公司', '产线工艺员', '6k-7k', 'PENDING_VERIFY', 'REVIEWING', 'NORMAL', 'LOW', {
    collegeId: 'C02',
    collegeName: '智能制造学院',
    majorName: '机电一体化',
    counselor: '孙辅导',
    employmentTeacher: '吴就业',
    signDate: '2026-06-15'
  })
]

/* ---------------- 就业材料 ---------------- */
export const employmentMaterials = [
  {
    id: 'emp-m-001',
    studentId: 'emp-s-002',
    name: '林嘉怡',
    className: '软件2301班',
    materialType: 'AGREEMENT',
    fileName: '就业协议书-林嘉怡.pdf',
    submitTime: '2026-06-03 10:12',
    status: 'SUBMITTED',
    reviewer: '',
    reviewTime: '',
    returnReason: '',
    remark: '首次提交'
  },
  {
    id: 'emp-m-002',
    studentId: 'emp-s-005',
    name: '孙浩然',
    className: '软件2302班',
    materialType: 'OTHER',
    fileName: '灵活就业证明-孙浩然.jpg',
    submitTime: '2026-06-10 09:40',
    status: 'RETURNED',
    reviewer: '王就业',
    reviewTime: '2026-06-11 15:20',
    returnReason: '证明材料缺少甲方盖章，请补充盖章页后重新上传',
    remark: ''
  },
  {
    id: 'emp-m-003',
    studentId: 'emp-s-008',
    name: '刘俊熙',
    className: '软件2302班',
    materialType: 'STARTUP_PROOF',
    fileName: '营业执照-星尘文化.pdf',
    submitTime: '2026-06-18 14:05',
    status: 'REVIEWING',
    reviewer: '王就业',
    reviewTime: '',
    returnReason: '',
    remark: '创业证明需核对经营范围'
  },
  {
    id: 'emp-m-004',
    studentId: 'emp-s-001',
    name: '陈晓峰',
    className: '软件2301班',
    materialType: 'CONTRACT',
    fileName: '劳动合同-陈晓峰.pdf',
    submitTime: '2026-05-13 11:30',
    status: 'APPROVED',
    reviewer: '王就业',
    reviewTime: '2026-05-14 09:10',
    returnReason: '',
    remark: ''
  },
  {
    id: 'emp-m-005',
    studentId: 'emp-s-011',
    name: '马诗涵',
    className: '大数据2301班',
    materialType: 'OTHER',
    fileName: '自由职业情况说明-马诗涵.docx',
    submitTime: '2026-06-20 16:55',
    status: 'RETURNED',
    reviewer: '王就业',
    reviewTime: '2026-06-21 10:00',
    returnReason: '说明材料未体现收入来源，请补充平台后台截图或流水证明',
    remark: ''
  },
  {
    id: 'emp-m-006',
    studentId: 'emp-s-014',
    name: '朱天佑',
    className: '机电2301班',
    materialType: 'AGREEMENT',
    fileName: '就业协议书-朱天佑.pdf',
    submitTime: '2026-06-16 08:50',
    status: 'SUBMITTED',
    reviewer: '',
    reviewTime: '',
    returnReason: '',
    remark: ''
  }
]

/* ---------------- 跟进记录 ---------------- */
export const followUpRecords = [
  {
    id: 'emp-f-001',
    studentId: 'emp-s-004',
    studentName: '王雨桐',
    className: '软件2301班',
    followTime: '2026-06-25 15:00',
    way: 'PHONE',
    content: '沟通求职意向，推荐 2 个本地前端岗位',
    result: '同意投递杭州云启、数联智能两家企业',
    nextPlan: '一周后回访面试进展',
    operator: '王就业',
    status: 'OPEN',
    voidReason: ''
  },
  {
    id: 'emp-f-002',
    studentId: 'emp-s-007',
    studentName: '郑婉婷',
    className: '软件2302班',
    followTime: '2026-06-20 09:30',
    way: 'FACE',
    content: '面谈家庭情况，说明就近就业帮扶政策',
    result: '纳入重点帮扶名单，优先推荐本地岗位',
    nextPlan: '联系宁波精工智造安排定向面试',
    operator: '周辅导',
    status: 'OPEN',
    voidReason: ''
  },
  {
    id: 'emp-f-003',
    studentId: 'emp-s-010',
    studentName: '徐博文',
    className: '大数据2301班',
    followTime: '2026-06-18 14:00',
    way: 'PHONE',
    content: '确认备考计划，提醒同步保留就业选项',
    result: '学生确认 8 月前更新去向',
    nextPlan: '8 月初回访考试结果',
    operator: '钱辅导',
    status: 'OPEN',
    voidReason: ''
  },
  {
    id: 'emp-f-004',
    studentId: 'emp-s-013',
    studentName: '罗芷晴',
    className: '机电2301班',
    followTime: '2026-06-27 16:40',
    way: 'VISIT',
    content: '家访了解身体恢复情况，介绍居家远程岗位',
    result: '家长同意先尝试远程客服岗位',
    nextPlan: '推送 3 个远程岗位并跟踪投递',
    operator: '吴就业',
    status: 'OPEN',
    voidReason: ''
  },
  {
    id: 'emp-f-005',
    studentId: 'emp-s-004',
    studentName: '王雨桐',
    className: '软件2301班',
    followTime: '2026-06-10 10:00',
    way: 'RECOMMEND',
    content: '推荐参加校园双选会（6月15日场）',
    result: '已到场，投递 3 份简历',
    nextPlan: '跟进双选会企业反馈',
    operator: '王就业',
    status: 'CLOSED',
    voidReason: ''
  }
]

/* ---------------- 企业与岗位 ---------------- */
export const companyList = [
  {
    id: 'emp-c-001',
    name: '杭州云启科技有限公司',
    creditCode: '91330100MA27K1XX0A',
    industry: '软件和信息技术服务业',
    nature: '民营企业',
    city: '杭州',
    contactPerson: '沈经理',
    contactPhone: '13900112233',
    cooperationLevel: '深度合作',
    status: 'ACTIVE',
    disableReason: '',
    jobCount: 2,
    hiredCount: 3
  },
  {
    id: 'emp-c-002',
    name: '宁波数联智能有限公司',
    creditCode: '91330200MA2AF2XX1B',
    industry: '互联网数据服务',
    nature: '民营企业',
    city: '宁波',
    contactPerson: '楼主管',
    contactPhone: '13700445566',
    cooperationLevel: '常规合作',
    status: 'ACTIVE',
    disableReason: '',
    jobCount: 1,
    hiredCount: 1
  },
  {
    id: 'emp-c-003',
    name: '宁波精工智造股份有限公司',
    creditCode: '91330200MA2CD3XX2C',
    industry: '智能装备制造',
    nature: '股份制企业',
    city: '宁波',
    contactPerson: '祝主任',
    contactPhone: '13600778899',
    cooperationLevel: '深度合作',
    status: 'ACTIVE',
    disableReason: '',
    jobCount: 2,
    hiredCount: 2
  },
  {
    id: 'emp-c-004',
    name: '上海慧算数据服务有限公司',
    creditCode: '91310100MA1FL4XX3D',
    industry: '数据处理与存储服务',
    nature: '民营企业',
    city: '上海',
    contactPerson: '康总监',
    contactPhone: '13500990011',
    cooperationLevel: '常规合作',
    status: 'DISABLED',
    disableReason: '2026-06 复核未通过：岗位薪资与承诺不符，暂停合作',
    jobCount: 0,
    hiredCount: 1
  }
]

export const jobList = [
  {
    id: 'emp-j-001',
    companyId: 'emp-c-001',
    companyName: '杭州云启科技有限公司',
    title: '前端开发工程师',
    category: '软件开发',
    salaryRange: '6k-8k',
    headcount: 5,
    signedCount: 2,
    status: 'OPEN',
    disableReason: '',
    publishTime: '2026-03-01'
  },
  {
    id: 'emp-j-002',
    companyId: 'emp-c-001',
    companyName: '杭州云启科技有限公司',
    title: '运维支持工程师',
    category: '运维支持',
    salaryRange: '5k-7k',
    headcount: 3,
    signedCount: 0,
    status: 'OPEN',
    disableReason: '',
    publishTime: '2026-04-10'
  },
  {
    id: 'emp-j-003',
    companyId: 'emp-c-002',
    companyName: '宁波数联智能有限公司',
    title: '测试工程师',
    category: '测试质量',
    salaryRange: '5k-7k',
    headcount: 2,
    signedCount: 1,
    status: 'OPEN',
    disableReason: '',
    publishTime: '2026-03-20'
  },
  {
    id: 'emp-j-004',
    companyId: 'emp-c-003',
    companyName: '宁波精工智造股份有限公司',
    title: '设备运维技术员',
    category: '智能制造',
    salaryRange: '5k-7k',
    headcount: 6,
    signedCount: 2,
    status: 'OPEN',
    disableReason: '',
    publishTime: '2026-02-15'
  },
  {
    id: 'emp-j-005',
    companyId: 'emp-c-003',
    companyName: '宁波精工智造股份有限公司',
    title: '质检员（可远程培训）',
    category: '质量管理',
    salaryRange: '4k-6k',
    headcount: 4,
    signedCount: 0,
    status: 'CLOSED',
    disableReason: '本批次招聘已满',
    publishTime: '2026-01-20'
  }
]

/* ---------------- 审计日志 ---------------- */
export const auditLogs = [
  {
    id: 'emp-a-001',
    time: '2026-06-21 10:00',
    operator: '王就业',
    roleName: '就业老师',
    bizType: 'MATERIAL',
    bizId: 'emp-m-005',
    action: '退回材料',
    detail: '退回《自由职业情况说明-马诗涵.docx》：说明材料未体现收入来源',
    before: 'SUBMITTED',
    after: 'RETURNED'
  },
  {
    id: 'emp-a-002',
    time: '2026-06-14 09:10',
    operator: '王就业',
    roleName: '就业老师',
    bizType: 'MATERIAL',
    bizId: 'emp-m-004',
    action: '审核通过',
    detail: '通过《劳动合同-陈晓峰.pdf》',
    before: 'SUBMITTED',
    after: 'APPROVED'
  },
  {
    id: 'emp-a-003',
    time: '2026-06-20 09:35',
    operator: '周辅导',
    roleName: '辅导员',
    bizType: 'FOLLOWUP',
    bizId: 'emp-f-002',
    action: '新增跟进',
    detail: '郑婉婷 · 面谈家庭情况，纳入重点帮扶',
    before: '',
    after: 'OPEN'
  },
  {
    id: 'emp-a-004',
    time: '2026-06-05 16:20',
    operator: '王就业',
    roleName: '就业老师',
    bizType: 'EXPORT',
    bizId: 'studentList',
    action: '导出台账',
    detail: '导出就业学生台账 12 条（手机号/薪资已脱敏，含水印）',
    before: '',
    after: ''
  }
]

/* ---------------- 看板 ---------------- */
export const dashboardSummary = {
  batchName: '2026 届毕业生就业批次',
  batchPeriod: '2026-03-01 ~ 2026-08-31',
  updateTime: '2026-07-03 08:30',
  kpis: [
    { key: 'total', label: '毕业生总数', value: '14', trend: '', trendQuality: 'neutral' },
    { key: 'implemented', label: '去向已落实', value: '10', trend: '+2 本周', trendQuality: 'good' },
    { key: 'rate', label: '去向落实率', value: '71.4%', trend: '+3.6% 周环比', trendQuality: 'good' },
    { key: 'unemployed', label: '未就业', value: '4', trend: '-1 本周', trendQuality: 'good' },
    { key: 'keyHelp', label: '重点帮扶', value: '3', trend: '持平', trendQuality: 'neutral' },
    { key: 'pendingMaterial', label: '材料待审核', value: '2', trend: '+1 今日', trendQuality: 'bad' }
  ],
  flow: [
    { label: '待填报', value: 0 },
    { label: '已填报', value: 4 },
    { label: '材料核验中', value: 4, active: true },
    { label: '已核验', value: 6 },
    { label: '已归档', value: 0 }
  ],
  collegeRates: [
    { name: '信息工程学院', total: 11, implemented: 8, rate: 72.7 },
    { name: '智能制造学院', total: 3, implemented: 2, rate: 66.7 }
  ],
  destinationDist: [
    { label: '签约就业', value: 5 },
    { label: '灵活就业', value: 1 },
    { label: '升学', value: 1 },
    { label: '入伍', value: 1 },
    { label: '自主创业', value: 1 },
    { label: '自由职业', value: 1 },
    { label: '待就业', value: 4 }
  ],
  riskAlerts: [
    { id: 'emp-r-001', level: 'HIGH', title: '3 名重点帮扶学生超过 7 天未更新跟进', link: 'unemployed' },
    { id: 'emp-r-002', level: 'MEDIUM', title: '2 份就业材料被退回后学生尚未重新提交', link: 'materials' },
    { id: 'emp-r-003', level: 'MEDIUM', title: '1 家合作企业被停用，请复核其关联学生去向', link: 'companies' }
  ],
  todos: [
    { id: 'emp-t-001', label: '待审核就业材料', value: 2, link: 'materials' },
    { id: 'emp-t-002', label: '待核验就业记录', value: 6, link: 'students' },
    { id: 'emp-t-003', label: '未就业学生待跟进', value: 4, link: 'unemployed' }
  ]
}
