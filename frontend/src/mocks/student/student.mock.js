/**
 * 学生中心（学生主档 / 学生360 / 学籍身份）mock 数据（01 学生主档与身份中心深化设计口径）。
 * 与 mocks/internship/internship.mock.js 保持同一租户世界观（演示职业技术学院 / 软件学院 / 赵一凡等）。
 * 页面禁止直接 import 本文件，必须经 modules/student/api/student.api.js 获取。
 * 所有品牌 / 角色 / 数据范围 / 权限均从这里返回，页面与组件不允许写死。
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

/** 运行时状态：当前激活角色（switchRole 演示多角色权限差异用） */
export const mockRuntime = { activeRoleCode: 'REGISTRAR' }

/**
 * 角色档案：学生中心 5 类核心角色。
 * permissionActions：visible=false 不渲染（涉密入口）；visible=true && allowed=false 置灰并提示 reason。
 * metricKeys：看板可见指标（不同角色看到的指标不同）。
 * scopeClassIds / scopeCollegeIds：数据范围过滤依据（空数组 = 全校）。
 */
export const roleProfiles = {
  REGISTRAR: {
    currentRole: { userId: 'u-reg-01', userName: '郑雅琴', roleCode: 'REGISTRAR', roleName: '学籍老师' },
    dataScope: { scopeCode: 'SCHOOL_ROSTER', scopeName: '全校学籍口径' },
    scopeClassIds: [],
    scopeCollegeIds: [],
    metricKeys: ['total', 'active', 'pendingIdentity', 'pendingCorrection', 'statusChangedMonth', 'dataComplete'],
    permissionActions: {
      viewList: { visible: true, allowed: true, reason: '' },
      viewDetail: { visible: true, allowed: true, reason: '' },
      viewSensitive: { visible: true, allowed: true, reason: '' },
      createStudent: { visible: true, allowed: true, reason: '' },
      editStudent: { visible: true, allowed: true, reason: '' },
      voidStudent: { visible: true, allowed: true, reason: '' },
      importStudents: { visible: true, allowed: true, reason: '' },
      exportStudents: { visible: true, allowed: true, reason: '' },
      exportArchive: { visible: true, allowed: true, reason: '' },
      batchAssignClass: { visible: true, allowed: true, reason: '' },
      batchAssignCounselor: { visible: true, allowed: true, reason: '' },
      batchRemind: { visible: true, allowed: true, reason: '' },
      changeStatus: { visible: true, allowed: true, reason: '' },
      batchChangeStatus: { visible: true, allowed: true, reason: '' },
      exportStatusRecords: { visible: true, allowed: true, reason: '' },
      reviewIdentity: { visible: true, allowed: true, reason: '' },
      markIdentityAbnormal: { visible: true, allowed: true, reason: '' },
      exportIdentityRecords: { visible: true, allowed: true, reason: '' },
      reviewCorrection: { visible: true, allowed: true, reason: '' },
      exportCorrections: { visible: true, allowed: true, reason: '' },
      createRiskTag: { visible: true, allowed: true, reason: '' },
      editRiskTag: { visible: true, allowed: true, reason: '' },
      voidRiskTag: { visible: true, allowed: true, reason: '' },
      followRiskTag: { visible: true, allowed: true, reason: '' },
      batchRemindRisk: { visible: true, allowed: true, reason: '' },
      exportRiskList: { visible: true, allowed: true, reason: '' },
      viewAudit: { visible: true, allowed: true, reason: '' },
      columnSettings: { visible: true, allowed: true, reason: '' }
    }
  },
  COUNSELOR: {
    currentRole: { userId: 't-003', userName: '李敏', roleCode: 'COUNSELOR', roleName: '辅导员' },
    dataScope: { scopeCode: 'MY_CLASSES', scopeName: '所带班级（软件2301 / 软件2302）' },
    scopeClassIds: ['c-2301', 'c-2302'],
    scopeCollegeIds: ['col-01'],
    metricKeys: ['total', 'active', 'highRisk', 'riskFollowing', 'pendingCorrection', 'dataComplete'],
    permissionActions: {
      viewList: { visible: true, allowed: true, reason: '' },
      viewDetail: { visible: true, allowed: true, reason: '' },
      viewSensitive: { visible: true, allowed: false, reason: '明文查看敏感信息需「学籍老师」或「系统管理员」角色' },
      createStudent: { visible: true, allowed: false, reason: '新增学生主档需「学籍老师」角色' },
      editStudent: { visible: true, allowed: false, reason: '编辑主档信息需「学籍老师」或「学院管理员」角色' },
      voidStudent: { visible: false, allowed: false, reason: '作废主档仅学籍老师 / 系统管理员可见' },
      importStudents: { visible: false, allowed: false, reason: '批量导入仅学籍老师 / 系统管理员可见' },
      exportStudents: { visible: true, allowed: true, reason: '仅限所带班级名单，含水印' },
      exportArchive: { visible: true, allowed: false, reason: '导出完整学生档案需「学籍老师」角色' },
      batchAssignClass: { visible: false, allowed: false, reason: '批量分班仅学籍老师 / 学院管理员可见' },
      batchAssignCounselor: { visible: false, allowed: false, reason: '批量分配辅导员仅学籍老师 / 学院管理员可见' },
      batchRemind: { visible: true, allowed: true, reason: '' },
      changeStatus: { visible: true, allowed: false, reason: '学籍状态变更需「学籍老师」或「学院管理员」角色' },
      batchChangeStatus: { visible: false, allowed: false, reason: '批量状态变更仅学籍老师可见' },
      exportStatusRecords: { visible: true, allowed: false, reason: '导出学籍变更记录需「学籍老师」角色' },
      reviewIdentity: { visible: true, allowed: false, reason: '人工复核需「学籍老师」角色' },
      markIdentityAbnormal: { visible: true, allowed: false, reason: '标记核验异常需「学籍老师」角色' },
      exportIdentityRecords: { visible: true, allowed: false, reason: '导出核验记录需「学籍老师」角色' },
      reviewCorrection: { visible: true, allowed: false, reason: '信息更正审核需「学籍老师」或「学院管理员」角色' },
      exportCorrections: { visible: true, allowed: false, reason: '导出更正记录需「学籍老师」角色' },
      createRiskTag: { visible: true, allowed: true, reason: '' },
      editRiskTag: { visible: true, allowed: true, reason: '' },
      voidRiskTag: { visible: true, allowed: true, reason: '' },
      followRiskTag: { visible: true, allowed: true, reason: '' },
      batchRemindRisk: { visible: true, allowed: true, reason: '' },
      exportRiskList: { visible: true, allowed: true, reason: '仅限所带班级名单，含水印' },
      viewAudit: { visible: true, allowed: true, reason: '' },
      columnSettings: { visible: true, allowed: true, reason: '' }
    }
  },
  COLLEGE_ADMIN: {
    currentRole: { userId: 'u-col-01', userName: '周建国', roleCode: 'COLLEGE_ADMIN', roleName: '学院管理员' },
    dataScope: { scopeCode: 'MY_COLLEGE', scopeName: '本学院（软件学院）' },
    scopeClassIds: [],
    scopeCollegeIds: ['col-01'],
    metricKeys: ['total', 'active', 'pendingCorrection', 'pendingIdentity', 'highRisk', 'dataComplete'],
    permissionActions: {
      viewList: { visible: true, allowed: true, reason: '' },
      viewDetail: { visible: true, allowed: true, reason: '' },
      viewSensitive: { visible: true, allowed: false, reason: '明文查看敏感信息需「学籍老师」或「系统管理员」角色' },
      createStudent: { visible: true, allowed: false, reason: '新增学生主档需「学籍老师」角色' },
      editStudent: { visible: true, allowed: true, reason: '' },
      voidStudent: { visible: true, allowed: false, reason: '作废主档需「学籍老师」或「系统管理员」角色' },
      importStudents: { visible: true, allowed: false, reason: '批量导入需「学籍老师」角色' },
      exportStudents: { visible: true, allowed: true, reason: '仅限本学院台账，含水印' },
      exportArchive: { visible: true, allowed: false, reason: '导出完整学生档案需「学籍老师」角色' },
      batchAssignClass: { visible: true, allowed: true, reason: '' },
      batchAssignCounselor: { visible: true, allowed: true, reason: '' },
      batchRemind: { visible: true, allowed: true, reason: '' },
      changeStatus: { visible: true, allowed: true, reason: '' },
      batchChangeStatus: { visible: true, allowed: false, reason: '批量状态变更需「学籍老师」角色' },
      exportStatusRecords: { visible: true, allowed: true, reason: '' },
      reviewIdentity: { visible: true, allowed: false, reason: '人工复核需「学籍老师」角色' },
      markIdentityAbnormal: { visible: true, allowed: false, reason: '标记核验异常需「学籍老师」角色' },
      exportIdentityRecords: { visible: true, allowed: true, reason: '' },
      reviewCorrection: { visible: true, allowed: true, reason: '' },
      exportCorrections: { visible: true, allowed: true, reason: '' },
      createRiskTag: { visible: true, allowed: true, reason: '' },
      editRiskTag: { visible: true, allowed: true, reason: '' },
      voidRiskTag: { visible: true, allowed: true, reason: '' },
      followRiskTag: { visible: true, allowed: true, reason: '' },
      batchRemindRisk: { visible: true, allowed: true, reason: '' },
      exportRiskList: { visible: true, allowed: true, reason: '' },
      viewAudit: { visible: true, allowed: true, reason: '' },
      columnSettings: { visible: true, allowed: true, reason: '' }
    }
  },
  ACADEMIC: {
    currentRole: { userId: 'u-aca-01', userName: '孙晓梅', roleCode: 'ACADEMIC', roleName: '教务老师' },
    dataScope: { scopeCode: 'SCHOOL_ACADEMIC', scopeName: '全校（教学口径）' },
    scopeClassIds: [],
    scopeCollegeIds: [],
    metricKeys: ['total', 'active', 'academicWarning', 'graduatingCount', 'dataComplete'],
    permissionActions: {
      viewList: { visible: true, allowed: true, reason: '' },
      viewDetail: { visible: true, allowed: true, reason: '' },
      viewSensitive: { visible: true, allowed: false, reason: '明文查看敏感信息需「学籍老师」或「系统管理员」角色' },
      createStudent: { visible: false, allowed: false, reason: '新增主档仅学籍老师可见' },
      editStudent: { visible: true, allowed: false, reason: '编辑主档信息需「学籍老师」或「学院管理员」角色' },
      voidStudent: { visible: false, allowed: false, reason: '作废主档仅学籍老师 / 系统管理员可见' },
      importStudents: { visible: false, allowed: false, reason: '批量导入仅学籍老师可见' },
      exportStudents: { visible: true, allowed: true, reason: '教学口径台账，敏感字段脱敏' },
      exportArchive: { visible: false, allowed: false, reason: '完整档案导出仅学籍老师可见' },
      batchAssignClass: { visible: false, allowed: false, reason: '批量分班仅学籍老师 / 学院管理员可见' },
      batchAssignCounselor: { visible: false, allowed: false, reason: '批量分配辅导员仅学籍老师 / 学院管理员可见' },
      batchRemind: { visible: true, allowed: true, reason: '' },
      changeStatus: { visible: true, allowed: false, reason: '学籍状态变更需「学籍老师」或「学院管理员」角色' },
      batchChangeStatus: { visible: false, allowed: false, reason: '批量状态变更仅学籍老师可见' },
      exportStatusRecords: { visible: true, allowed: true, reason: '' },
      reviewIdentity: { visible: true, allowed: false, reason: '人工复核需「学籍老师」角色' },
      markIdentityAbnormal: { visible: true, allowed: false, reason: '标记核验异常需「学籍老师」角色' },
      exportIdentityRecords: { visible: true, allowed: false, reason: '导出核验记录需「学籍老师」角色' },
      reviewCorrection: { visible: true, allowed: false, reason: '信息更正审核需「学籍老师」或「学院管理员」角色' },
      exportCorrections: { visible: true, allowed: false, reason: '导出更正记录需「学籍老师」角色' },
      createRiskTag: { visible: true, allowed: false, reason: '创建风险标签需「辅导员」「学籍老师」或「学院管理员」角色' },
      editRiskTag: { visible: true, allowed: false, reason: '编辑风险标签需「辅导员」「学籍老师」或「学院管理员」角色' },
      voidRiskTag: { visible: false, allowed: false, reason: '作废风险标签对当前角色不可见' },
      followRiskTag: { visible: true, allowed: false, reason: '风险跟进需「辅导员」或「学籍老师」角色' },
      batchRemindRisk: { visible: true, allowed: false, reason: '批量提醒需「辅导员」或「学籍老师」角色' },
      exportRiskList: { visible: true, allowed: false, reason: '导出风险名单需「辅导员」「学籍老师」或「学院管理员」角色' },
      viewAudit: { visible: true, allowed: true, reason: '' },
      columnSettings: { visible: true, allowed: true, reason: '' }
    }
  },
  SYS_ADMIN: {
    currentRole: { userId: 'u-sys-01', userName: '管理员甲', roleCode: 'SYS_ADMIN', roleName: '系统管理员' },
    dataScope: { scopeCode: 'SCHOOL_ALL', scopeName: '全校（含配置域）' },
    scopeClassIds: [],
    scopeCollegeIds: [],
    metricKeys: ['total', 'accountUnbound', 'dataComplete', 'auditWeek', 'pendingIdentity'],
    permissionActions: {
      viewList: { visible: true, allowed: true, reason: '' },
      viewDetail: { visible: true, allowed: true, reason: '' },
      viewSensitive: { visible: true, allowed: true, reason: '' },
      createStudent: { visible: true, allowed: true, reason: '' },
      editStudent: { visible: true, allowed: true, reason: '' },
      voidStudent: { visible: true, allowed: true, reason: '' },
      importStudents: { visible: true, allowed: true, reason: '' },
      exportStudents: { visible: true, allowed: true, reason: '' },
      exportArchive: { visible: true, allowed: true, reason: '' },
      batchAssignClass: { visible: true, allowed: true, reason: '' },
      batchAssignCounselor: { visible: true, allowed: true, reason: '' },
      batchRemind: { visible: true, allowed: true, reason: '' },
      changeStatus: { visible: true, allowed: false, reason: '学籍业务变更需「学籍老师」或「学院管理员」角色发起' },
      batchChangeStatus: { visible: true, allowed: false, reason: '批量状态变更需「学籍老师」角色发起' },
      exportStatusRecords: { visible: true, allowed: true, reason: '' },
      reviewIdentity: { visible: true, allowed: false, reason: '业务复核需「学籍老师」角色，系统管理员仅可查看' },
      markIdentityAbnormal: { visible: true, allowed: true, reason: '' },
      exportIdentityRecords: { visible: true, allowed: true, reason: '' },
      reviewCorrection: { visible: true, allowed: false, reason: '业务审核需「学籍老师」或「学院管理员」角色' },
      exportCorrections: { visible: true, allowed: true, reason: '' },
      createRiskTag: { visible: true, allowed: false, reason: '风险标签由业务角色维护，系统管理员仅可查看' },
      editRiskTag: { visible: true, allowed: false, reason: '风险标签由业务角色维护，系统管理员仅可查看' },
      voidRiskTag: { visible: true, allowed: true, reason: '' },
      followRiskTag: { visible: true, allowed: false, reason: '风险跟进由业务角色执行' },
      batchRemindRisk: { visible: true, allowed: false, reason: '批量提醒由业务角色执行' },
      exportRiskList: { visible: true, allowed: true, reason: '' },
      viewAudit: { visible: true, allowed: true, reason: '' },
      columnSettings: { visible: true, allowed: true, reason: '' }
    }
  }
}

/** 看板指标定义（value 由 api 依据数据实时计算，禁止写死指标值） */
export const metricDefs = {
  total: { label: '在册学生', unit: '人' },
  active: { label: '在读学生', unit: '人' },
  pendingIdentity: { label: '待复核身份', unit: '条' },
  pendingCorrection: { label: '待审更正申请', unit: '条' },
  statusChangedMonth: { label: '本月学籍异动', unit: '条' },
  dataComplete: { label: '主档完整率', unit: '%' },
  highRisk: { label: '高风险学生', unit: '人' },
  riskFollowing: { label: '风险跟进中', unit: '条' },
  academicWarning: { label: '学业预警', unit: '人' },
  graduatingCount: { label: '毕业年级学生', unit: '人' },
  accountUnbound: { label: '账号未绑定', unit: '人' },
  auditWeek: { label: '近 7 日审计事件', unit: '条' }
}

/* ================= 组织字典 ================= */
export const collegeList = [
  { value: 'col-01', label: '软件学院' },
  { value: 'col-02', label: '智能制造学院' }
]

export const majorList = [
  { value: 'maj-01', label: '软件技术', collegeId: 'col-01' },
  { value: 'maj-02', label: '大数据技术', collegeId: 'col-01' },
  { value: 'maj-03', label: '机电一体化技术', collegeId: 'col-02' }
]

export const classList = [
  { value: 'c-2301', label: '软件2301', majorId: 'maj-01', collegeId: 'col-01', counselorName: '李敏' },
  { value: 'c-2302', label: '软件2302', majorId: 'maj-01', collegeId: 'col-01', counselorName: '李敏' },
  { value: 'c-2201', label: '软件2201', majorId: 'maj-01', collegeId: 'col-01', counselorName: '王芳' },
  { value: 'c-2601', label: '大数据2601', majorId: 'maj-02', collegeId: 'col-01', counselorName: '陈立' },
  { value: 'c-2401', label: '机电2301', majorId: 'maj-03', collegeId: 'col-02', counselorName: '高翔' }
]

export const counselorOptions = [
  { value: '李敏', label: '李敏（软件学院）' },
  { value: '王芳', label: '王芳（软件学院）' },
  { value: '陈立', label: '陈立（软件学院）' },
  { value: '高翔', label: '高翔（智能制造学院）' }
]

/* ================= 学生主档 ================= */
function stu(overrides) {
  return {
    studentId: '',
    name: '',
    gender: '男',
    studentNo: '',
    idCard: '',
    phone: '',
    collegeId: 'col-01',
    collegeName: '软件学院',
    majorId: 'maj-01',
    majorName: '软件技术',
    classId: 'c-2301',
    className: '软件2301',
    grade: '2023级',
    enrollDate: '2023-09-05',
    counselorName: '李敏',
    studentStatus: 'ACTIVE',
    identityVerifyStatus: 'VERIFIED',
    accountBindStatus: 'BOUND',
    riskLevel: 'NONE',
    dataCompleteness: 100,
    voided: false,
    voidReason: '',
    updatedAt: '2026-06-28 10:00',
    ...overrides
  }
}

export const students = [
  stu({
    studentId: 'stu-001',
    name: '赵一凡',
    studentNo: '2023115001',
    idCard: '420101200501011234',
    phone: '13812340001',
    riskLevel: 'HIGH',
    dataCompleteness: 98,
    updatedAt: '2026-07-02 09:12'
  }),
  stu({
    studentId: 'stu-002',
    name: '钱雨桐',
    gender: '女',
    studentNo: '2023115002',
    idCard: '420101200503022345',
    phone: '13812340002'
  }),
  stu({
    studentId: 'stu-003',
    name: '孙浩然',
    studentNo: '2023115003',
    idCard: '420101200507033456',
    phone: '13812340003',
    riskLevel: 'LOW'
  }),
  stu({
    studentId: 'stu-004',
    name: '李思颖',
    gender: '女',
    studentNo: '2023115004',
    idCard: '420101200504044567',
    phone: '13812340004',
    studentStatus: 'SUSPENDED',
    riskLevel: 'MEDIUM',
    updatedAt: '2026-06-12 15:40'
  }),
  stu({
    studentId: 'stu-005',
    name: '周子墨',
    studentNo: '2023115021',
    idCard: '420102200506055678',
    phone: '13812340005',
    classId: 'c-2302',
    className: '软件2302'
  }),
  stu({
    studentId: 'stu-006',
    name: '吴佳琪',
    gender: '女',
    studentNo: '2023115022',
    idCard: '420102200508066789',
    phone: '13812340006',
    classId: 'c-2302',
    className: '软件2302',
    identityVerifyStatus: 'PENDING',
    accountBindStatus: 'UNBOUND',
    dataCompleteness: 82
  }),
  stu({
    studentId: 'stu-007',
    name: '郑博文',
    studentNo: '2023115023',
    idCard: '420102200502077890',
    phone: '13812340007',
    classId: 'c-2302',
    className: '软件2302',
    identityVerifyStatus: 'REJECTED',
    riskLevel: 'LOW',
    dataCompleteness: 90
  }),
  stu({
    studentId: 'stu-008',
    name: '王梓萱',
    gender: '女',
    studentNo: '2023115024',
    idCard: '420102200509088901',
    phone: '13812340008',
    classId: 'c-2302',
    className: '软件2302'
  }),
  stu({
    studentId: 'stu-009',
    name: '冯天佑',
    studentNo: '2022115011',
    idCard: '420103200409099012',
    phone: '13812340009',
    classId: 'c-2201',
    className: '软件2201',
    grade: '2022级',
    enrollDate: '2022-09-06',
    counselorName: '王芳',
    studentStatus: 'GRADUATED',
    updatedAt: '2026-06-30 17:20'
  }),
  stu({
    studentId: 'stu-010',
    name: '陈可欣',
    gender: '女',
    studentNo: '2026115001',
    idCard: '420104200801011123',
    phone: '13812340010',
    majorId: 'maj-02',
    majorName: '大数据技术',
    classId: 'c-2601',
    className: '大数据2601',
    grade: '2026级',
    enrollDate: '2026-09-01',
    counselorName: '陈立',
    studentStatus: 'ADMITTED',
    identityVerifyStatus: 'PENDING',
    accountBindStatus: 'UNBOUND',
    dataCompleteness: 68
  }),
  stu({
    studentId: 'stu-011',
    name: '褚明轩',
    studentNo: '2023214001',
    idCard: '420105200503111234',
    phone: '13812340011',
    collegeId: 'col-02',
    collegeName: '智能制造学院',
    majorId: 'maj-03',
    majorName: '机电一体化技术',
    classId: 'c-2401',
    className: '机电2301',
    counselorName: '高翔',
    studentStatus: 'DROPPED',
    updatedAt: '2026-05-20 11:02'
  }),
  stu({
    studentId: 'stu-012',
    name: '卫子昂',
    studentNo: '2023115099',
    idCard: '420101200505121345',
    phone: '13812340012',
    studentStatus: 'VOIDED',
    voided: true,
    voidReason: '重复建档，与 2023115001 合并',
    updatedAt: '2026-04-18 09:30'
  })
]

/* ================= 学生360 扩展档案 ================= */
const DETAIL_PRESETS = {
  'stu-001': {
    orientation: {
      finished: true,
      steps: [
        { name: '线上报到', status: 'COMPLETED', time: '2023-08-28 10:21' },
        { name: '缴费确认', status: 'COMPLETED', time: '2023-08-29 09:02' },
        { name: '宿舍分配', status: 'COMPLETED', time: '2023-08-30 14:11' },
        { name: '现场注册', status: 'COMPLETED', time: '2023-09-05 08:40' }
      ]
    },
    serviceRecords: [
      { id: 'svc-1', type: '请假', title: '事假 2 天（家庭事务）', status: 'APPROVED', time: '2026-03-12' },
      { id: 'svc-2', type: '奖助', title: '国家励志奖学金申请', status: 'PENDING_REVIEW', time: '2026-06-10' }
    ],
    academic: {
      gpa: 2.1,
      earnedCredits: 86,
      requiredCredits: 120,
      warningLevel: '橙色预警',
      courses: [
        { name: 'Java 程序设计', term: '2025-2026-1', score: 58, retake: true },
        { name: '数据库原理', term: '2025-2026-1', score: 71, retake: false },
        { name: 'Web 前端开发', term: '2025-2026-2', score: 66, retake: false }
      ]
    },
    internship: {
      enterpriseName: '华信智能科技有限公司',
      positionName: 'Java 开发实习生',
      status: 'ONBOARD',
      statusLabel: '在岗中',
      attendanceRate: '78%',
      reportSummary: '已交 3 / 应交 4',
      advisorName: '刘强'
    },
    graduationDesign: {
      topic: '基于 SpringBoot 的校园二手交易平台设计与实现',
      advisorName: '王芳',
      stage: '中期检查',
      stageStatus: 'RETURNED',
      score: ''
    },
    employment: {
      intent: '企业就业（软件开发方向）',
      offerCount: 0,
      agreementStatus: '未签约',
      trackStatus: '求职中'
    }
  },
  'stu-004': {
    orientation: {
      finished: true,
      steps: [
        { name: '线上报到', status: 'COMPLETED', time: '2023-08-28 11:05' },
        { name: '缴费确认', status: 'COMPLETED', time: '2023-08-29 10:12' },
        { name: '宿舍分配', status: 'COMPLETED', time: '2023-08-30 15:30' },
        { name: '现场注册', status: 'COMPLETED', time: '2023-09-05 09:22' }
      ]
    },
    serviceRecords: [
      { id: 'svc-3', type: '休学', title: '因病休学申请（一学年）', status: 'APPROVED', time: '2026-06-12' },
      { id: 'svc-4', type: '心理关怀', title: '心理中心月度回访', status: 'PROCESSING', time: '2026-06-25' }
    ],
    academic: {
      gpa: 3.1,
      earnedCredits: 92,
      requiredCredits: 120,
      warningLevel: '',
      courses: [
        { name: '软件测试基础', term: '2025-2026-1', score: 84, retake: false },
        { name: '数据库原理', term: '2025-2026-1', score: 79, retake: false }
      ]
    },
    internship: null,
    graduationDesign: null,
    employment: null
  },
  'stu-009': {
    orientation: { finished: true, steps: [] },
    serviceRecords: [],
    academic: {
      gpa: 3.4,
      earnedCredits: 126,
      requiredCredits: 120,
      warningLevel: '',
      courses: []
    },
    internship: {
      enterpriseName: '华信智能科技有限公司',
      positionName: '运维实习生',
      status: 'ARCHIVED',
      statusLabel: '已归档',
      attendanceRate: '97%',
      reportSummary: '已交 16 / 应交 16',
      advisorName: '刘强'
    },
    graduationDesign: {
      topic: '中小企业网络运维自动化方案设计',
      advisorName: '王芳',
      stage: '已答辩',
      stageStatus: 'COMPLETED',
      score: '86（良好）'
    },
    employment: {
      intent: '企业就业',
      offerCount: 2,
      agreementStatus: '已签约（华信智能科技有限公司）',
      trackStatus: '已就业'
    }
  }
}

/** 其余学生用通用模板生成（保持数据来自 mock，不在页面写死） */
export function getDetailPreset(studentId) {
  if (DETAIL_PRESETS[studentId]) return DETAIL_PRESETS[studentId]
  return {
    orientation: {
      finished: true,
      steps: [
        { name: '线上报到', status: 'COMPLETED', time: '2023-08-28' },
        { name: '缴费确认', status: 'COMPLETED', time: '2023-08-29' },
        { name: '宿舍分配', status: 'COMPLETED', time: '2023-08-30' },
        { name: '现场注册', status: 'COMPLETED', time: '2023-09-05' }
      ]
    },
    serviceRecords: [],
    academic: { gpa: 3.0, earnedCredits: 90, requiredCredits: 120, warningLevel: '', courses: [] },
    internship: null,
    graduationDesign: null,
    employment: null
  }
}

/* ================= 学籍状态变更记录 ================= */
export const statusChangeRecords = [
  {
    id: 'sc-001',
    studentId: 'stu-004',
    studentName: '李思颖',
    className: '软件2301',
    fromStatus: 'ACTIVE',
    toStatus: 'SUSPENDED',
    reason: '因病申请休学一学年，附三甲医院诊断证明',
    attachment: '休学申请表-李思颖.pdf',
    operator: '郑雅琴',
    roleName: '学籍老师',
    operatedAt: '2026-06-12 15:40'
  },
  {
    id: 'sc-002',
    studentId: 'stu-009',
    studentName: '冯天佑',
    className: '软件2201',
    fromStatus: 'ACTIVE',
    toStatus: 'GRADUATED',
    reason: '2026 届毕业审核通过，准予毕业',
    attachment: '',
    operator: '郑雅琴',
    roleName: '学籍老师',
    operatedAt: '2026-06-30 17:20'
  },
  {
    id: 'sc-003',
    studentId: 'stu-011',
    studentName: '褚明轩',
    className: '机电2301',
    fromStatus: 'ACTIVE',
    toStatus: 'DROPPED',
    reason: '本人申请退学，监护人已签字确认',
    attachment: '退学申请表-褚明轩.pdf',
    operator: '郑雅琴',
    roleName: '学籍老师',
    operatedAt: '2026-05-20 11:02'
  },
  {
    id: 'sc-004',
    studentId: 'stu-010',
    studentName: '陈可欣',
    className: '大数据2601',
    fromStatus: 'ADMITTED',
    toStatus: 'ADMITTED',
    reason: '2026 级新生录取信息导入建档',
    attachment: '',
    operator: '管理员甲',
    roleName: '系统管理员',
    operatedAt: '2026-06-20 10:05'
  }
]

/* ================= 身份核验记录 ================= */
export const identityRecords = [
  {
    id: 'iv-001',
    studentId: 'stu-006',
    studentName: '吴佳琪',
    className: '软件2302',
    method: '公安实名比对',
    result: 'PENDING',
    similarity: '',
    checkedAt: '2026-07-01 09:20',
    status: 'PENDING_REVIEW',
    reviewer: '',
    reviewComment: ''
  },
  {
    id: 'iv-002',
    studentId: 'stu-007',
    studentName: '郑博文',
    className: '软件2302',
    method: '人脸识别核验',
    result: 'FAIL',
    similarity: '61%',
    checkedAt: '2026-06-28 14:35',
    status: 'PENDING_REVIEW',
    reviewer: '',
    reviewComment: '相似度低于阈值，需人工复核'
  },
  {
    id: 'iv-003',
    studentId: 'stu-010',
    studentName: '陈可欣',
    className: '大数据2601',
    method: '录取库比对',
    result: 'PENDING',
    similarity: '',
    checkedAt: '2026-06-21 08:12',
    status: 'PENDING_REVIEW',
    reviewer: '',
    reviewComment: '新生首次核验，等待证件照上传'
  },
  {
    id: 'iv-004',
    studentId: 'stu-001',
    studentName: '赵一凡',
    className: '软件2301',
    method: '公安实名比对',
    result: 'PASS',
    similarity: '99%',
    checkedAt: '2026-03-02 10:00',
    status: 'CONFIRMED',
    reviewer: '郑雅琴',
    reviewComment: '比对一致'
  },
  {
    id: 'iv-005',
    studentId: 'stu-002',
    studentName: '钱雨桐',
    className: '软件2301',
    method: '人脸识别核验',
    result: 'PASS',
    similarity: '97%',
    checkedAt: '2026-03-02 10:03',
    status: 'CONFIRMED',
    reviewer: '郑雅琴',
    reviewComment: ''
  },
  {
    id: 'iv-006',
    studentId: 'stu-011',
    studentName: '褚明轩',
    className: '机电2301',
    method: '证件 OCR 识别',
    result: 'FAIL',
    similarity: '',
    checkedAt: '2026-04-10 16:44',
    status: 'ABNORMAL',
    reviewer: '管理员甲',
    reviewComment: '证件照片模糊且有效期存疑，已标记异常并通知学生重传'
  }
]

/* ================= 信息更正申请 ================= */
export const correctionRequests = [
  {
    id: 'cr-001',
    studentId: 'stu-003',
    studentName: '孙浩然',
    className: '软件2301',
    fieldKey: 'phone',
    fieldLabel: '手机号',
    oldValue: '13812340003',
    newValue: '13998765432',
    sensitive: true,
    reason: '原号码停用，更换为本人新办号码',
    attachments: ['运营商开户凭证.jpg'],
    channel: '学生小程序',
    submitTime: '2026-07-01 20:15',
    status: 'PENDING_REVIEW',
    reviewer: '',
    reviewTime: '',
    reviewComment: ''
  },
  {
    id: 'cr-002',
    studentId: 'stu-006',
    studentName: '吴佳琪',
    className: '软件2302',
    fieldKey: 'homeAddress',
    fieldLabel: '家庭住址',
    oldValue: '湖北省武汉市江岸区解放大道 1001 号',
    newValue: '湖北省武汉市洪山区珞喻路 152 号',
    sensitive: false,
    reason: '家庭搬迁，同步更新通讯地址',
    attachments: [],
    channel: '学生小程序',
    submitTime: '2026-06-30 18:40',
    status: 'PENDING_REVIEW',
    reviewer: '',
    reviewTime: '',
    reviewComment: ''
  },
  {
    id: 'cr-003',
    studentId: 'stu-002',
    studentName: '钱雨桐',
    className: '软件2301',
    fieldKey: 'name',
    fieldLabel: '姓名',
    oldValue: '钱雨彤',
    newValue: '钱雨桐',
    sensitive: false,
    reason: '录取信息录入错字，与身份证不一致',
    attachments: ['身份证正面.jpg'],
    channel: 'PC 学生门户',
    submitTime: '2026-06-18 09:25',
    status: 'APPROVED',
    reviewer: '郑雅琴',
    reviewTime: '2026-06-18 15:02',
    reviewComment: '已核对身份证原件，准予更正'
  },
  {
    id: 'cr-004',
    studentId: 'stu-007',
    studentName: '郑博文',
    className: '软件2302',
    fieldKey: 'idCard',
    fieldLabel: '身份证号',
    oldValue: '420102200502077890',
    newValue: '420102200502077891',
    sensitive: true,
    reason: '身份证号末位录入有误',
    attachments: [],
    channel: '学生小程序',
    submitTime: '2026-06-26 11:10',
    status: 'RETURNED',
    reviewer: '郑雅琴',
    reviewTime: '2026-06-27 10:30',
    reviewComment: '证件类关键字段更正必须上传身份证正反面照片，请补充材料后重新提交'
  },
  {
    id: 'cr-005',
    studentId: 'stu-010',
    studentName: '陈可欣',
    className: '大数据2601',
    fieldKey: 'guardianPhone',
    fieldLabel: '监护人电话',
    oldValue: '13700001111',
    newValue: '13700002222',
    sensitive: true,
    reason: '监护人更换联系方式',
    attachments: [],
    channel: '迎新小程序',
    submitTime: '2026-06-29 21:08',
    status: 'PENDING_REVIEW',
    reviewer: '',
    reviewTime: '',
    reviewComment: ''
  }
]

/* ================= 学生风险标签 ================= */
export const riskTags = [
  {
    id: 'rt-001',
    studentId: 'stu-001',
    studentName: '赵一凡',
    className: '软件2301',
    tagType: 'INTERNSHIP',
    tagTypeLabel: '实习风险',
    level: 'HIGH',
    title: '连续 3 天实习打卡异常',
    description: '实习考勤触发 INT-R07 规则自动生成，需辅导员与实习指导教师联动核实',
    source: 'SYSTEM',
    sourceLabel: '系统预警',
    status: 'FOLLOWING',
    owner: '李敏',
    createdAt: '2026-07-02 08:00',
    voidReason: '',
    followUps: [
      { time: '2026-07-02 10:30', who: '李敏', note: '已电话联系学生，本人称企业调整驻场地点导致定位偏移，待企业导师书面确认' }
    ]
  },
  {
    id: 'rt-002',
    studentId: 'stu-001',
    studentName: '赵一凡',
    className: '软件2301',
    tagType: 'ACADEMIC',
    tagTypeLabel: '学业风险',
    level: 'MEDIUM',
    title: 'Java 程序设计课程不及格待重修',
    description: '2025-2026-1 学期核心课程 58 分，已进入橙色学业预警名单',
    source: 'SYSTEM',
    sourceLabel: '系统预警',
    status: 'ACTIVE',
    owner: '李敏',
    createdAt: '2026-02-25 09:00',
    voidReason: '',
    followUps: []
  },
  {
    id: 'rt-003',
    studentId: 'stu-004',
    studentName: '李思颖',
    className: '软件2301',
    tagType: 'PSYCH',
    tagTypeLabel: '心理关怀',
    level: 'MEDIUM',
    title: '休学期间月度心理回访',
    description: '休学关怀方案要求每月回访一次并记录，回访结果同步心理中心',
    source: 'MANUAL',
    sourceLabel: '人工创建',
    status: 'FOLLOWING',
    owner: '李敏',
    createdAt: '2026-06-13 09:40',
    voidReason: '',
    followUps: [
      { time: '2026-06-25 16:00', who: '李敏', note: '6 月回访完成，情绪平稳，家属陪同复诊正常' }
    ]
  },
  {
    id: 'rt-004',
    studentId: 'stu-003',
    studentName: '孙浩然',
    className: '软件2301',
    tagType: 'FINANCE',
    tagTypeLabel: '经济困难',
    level: 'LOW',
    title: '家庭经济困难建档',
    description: '已纳入资助名单，关注奖助申请与勤工俭学安排',
    source: 'MANUAL',
    sourceLabel: '人工创建',
    status: 'ACTIVE',
    owner: '李敏',
    createdAt: '2025-10-11 14:20',
    voidReason: '',
    followUps: []
  },
  {
    id: 'rt-005',
    studentId: 'stu-007',
    studentName: '郑博文',
    className: '软件2302',
    tagType: 'IDENTITY',
    tagTypeLabel: '身份异常',
    level: 'LOW',
    title: '人脸核验未通过待复核',
    description: '人脸识别相似度 61%，低于阈值，等待学籍老师人工复核',
    source: 'SYSTEM',
    sourceLabel: '系统预警',
    status: 'ACTIVE',
    owner: '郑雅琴',
    createdAt: '2026-06-28 14:36',
    voidReason: '',
    followUps: []
  },
  {
    id: 'rt-006',
    studentId: 'stu-005',
    studentName: '周子墨',
    className: '软件2302',
    tagType: 'ACADEMIC',
    tagTypeLabel: '学业风险',
    level: 'LOW',
    title: '上学期两门课程缓考',
    description: '缓考课程已在本学期补考通过，风险解除',
    source: 'MANUAL',
    sourceLabel: '人工创建',
    status: 'RESOLVED',
    owner: '李敏',
    createdAt: '2026-03-05 10:10',
    voidReason: '',
    followUps: [{ time: '2026-04-22 11:00', who: '李敏', note: '补考成绩 74 / 78，均已通过，标记解除' }]
  },
  {
    id: 'rt-007',
    studentId: 'stu-008',
    studentName: '王梓萱',
    className: '软件2302',
    tagType: 'PSYCH',
    tagTypeLabel: '心理关怀',
    level: 'LOW',
    title: '新生适应期关注（误报）',
    description: '入学问卷误触发，经面谈确认无需跟进',
    source: 'SYSTEM',
    sourceLabel: '系统预警',
    status: 'VOIDED',
    owner: '李敏',
    createdAt: '2025-09-20 09:00',
    voidReason: '问卷答题误操作导致误报，经辅导员两次面谈确认无风险',
    followUps: []
  }
]

/* ================= 导入 / 导出 ================= */
export const importTemplates = [
  {
    id: 'tpl-001',
    name: '学生主档导入模板 v3.2',
    description: '含基础信息 / 学籍信息 / 联系方式 / 监护人 4 个分组，必填 18 个字段',
    fieldCount: 42,
    updatedAt: '2026-05-30',
    fileName: 'student-profile-import-v3.2.xlsx'
  },
  {
    id: 'tpl-002',
    name: '学籍异动导入模板 v1.4',
    description: '用于批量休学 / 复学 / 转专业等异动登记，需附异动原因与依据文号',
    fieldCount: 12,
    updatedAt: '2026-04-12',
    fileName: 'student-status-change-v1.4.xlsx'
  },
  {
    id: 'tpl-003',
    name: '风险标签导入模板 v1.1',
    description: '用于批量导入风险标签建档（类型 / 等级 / 责任人 / 说明）',
    fieldCount: 9,
    updatedAt: '2026-03-02',
    fileName: 'student-risk-tag-v1.1.xlsx'
  }
]

export const exportOptions = {
  scopes: [
    { value: 'CURRENT_SCOPE', label: '当前数据范围全部学生', desc: '按当前角色数据范围导出，超范围数据不可选' },
    { value: 'FILTERED', label: '当前筛选结果', desc: '与列表筛选条件一致' },
    { value: 'SELECTED', label: '勾选的学生', desc: '仅导出列表中勾选的记录' }
  ],
  fieldGroups: [
    {
      key: 'basic',
      label: '基础信息',
      fields: [
        { key: 'name', label: '姓名', sensitive: false },
        { key: 'studentNo', label: '学号', sensitive: false },
        { key: 'gender', label: '性别', sensitive: false },
        { key: 'orgPath', label: '学院 / 专业 / 班级', sensitive: false },
        { key: 'grade', label: '年级', sensitive: false }
      ]
    },
    {
      key: 'contact',
      label: '联系与证件（默认脱敏）',
      fields: [
        { key: 'phone', label: '手机号', sensitive: true },
        { key: 'idCard', label: '身份证号', sensitive: true },
        { key: 'homeAddress', label: '家庭住址', sensitive: true }
      ]
    },
    {
      key: 'status',
      label: '学籍与风险',
      fields: [
        { key: 'studentStatus', label: '学籍状态', sensitive: false },
        { key: 'identityVerifyStatus', label: '身份核验状态', sensitive: false },
        { key: 'riskLevel', label: '风险等级', sensitive: false }
      ]
    }
  ],
  purposes: [
    { value: 'REPORT', label: '上级报表报送' },
    { value: 'AUDIT', label: '校内审计 / 检查' },
    { value: 'WORK', label: '日常业务办理' }
  ]
}

/** 导入 / 导出任务回执（新任务 unshift 到最前） */
export const transferTasks = [
  {
    id: 'task-9001',
    type: 'EXPORT',
    typeLabel: '导出',
    title: '2026 届毕业生学籍台账',
    fileName: 'graduate-roster-20260630.xlsx',
    totalRows: 1,
    successRows: 1,
    failedRows: 0,
    status: 'COMPLETED',
    operator: '郑雅琴',
    roleName: '学籍老师',
    time: '2026-06-30 17:35',
    masked: true,
    watermark: true,
    auditId: 'AUD-20260630-102'
  },
  {
    id: 'task-9002',
    type: 'IMPORT',
    typeLabel: '导入',
    title: '2026 级新生录取名单首批',
    fileName: 'freshmen-batch1.xlsx',
    totalRows: 1,
    successRows: 1,
    failedRows: 0,
    status: 'COMPLETED',
    operator: '管理员甲',
    roleName: '系统管理员',
    time: '2026-06-20 10:05',
    masked: false,
    watermark: false,
    auditId: 'AUD-20260620-071'
  }
]

/** 导入校验错误预览（validateImport 返回，行号为模拟） */
export const importValidatePreset = {
  totalRows: 96,
  validRows: 92,
  errorRows: 4,
  errors: [
    { row: 8, field: '身份证号', message: '校验位不合法' },
    { row: 23, field: '班级', message: '「软件2399」不存在于班级字典' },
    { row: 41, field: '手机号', message: '与在册学生 2023115003 重复' },
    { row: 77, field: '姓名', message: '必填字段为空' }
  ]
}

/* ================= 表格列配置（列设置） ================= */
export const fieldColumns = {
  studentList: [
    { key: 'student', title: '学生', locked: true, visible: true },
    { key: 'orgPath', title: '学院 / 专业 / 班级', locked: false, visible: true },
    { key: 'grade', title: '年级', locked: false, visible: true },
    { key: 'counselorName', title: '辅导员', locked: false, visible: true },
    { key: 'phone', title: '手机号', locked: false, visible: true },
    { key: 'idCard', title: '身份证号', locked: false, visible: false },
    { key: 'studentStatus', title: '学籍状态', locked: false, visible: true },
    { key: 'identityVerifyStatus', title: '身份核验', locked: false, visible: true },
    { key: 'riskLevel', title: '风险', locked: false, visible: true },
    { key: 'dataCompleteness', title: '完整度', locked: false, visible: false },
    { key: 'updatedAt', title: '更新时间', locked: false, visible: false },
    { key: 'actions', title: '操作', locked: true, visible: true }
  ]
}

/* ================= 字典 ================= */
export const statusOptions = {
  studentStatus: [
    { value: 'ADMITTED', label: '已录取' },
    { value: 'ACTIVE', label: '在读' },
    { value: 'SUSPENDED', label: '休学' },
    { value: 'GRADUATED', label: '已毕业' },
    { value: 'DROPPED', label: '退学' },
    { value: 'VOIDED', label: '已作废' }
  ],
  studentStatusFlow: [
    { value: 'ADMITTED', label: '已录取' },
    { value: 'ACTIVE', label: '在读' },
    { value: 'SUSPENDED', label: '休学' },
    { value: 'GRADUATED', label: '已毕业' },
    { value: 'DROPPED', label: '退学' }
  ],
  identityVerifyStatus: [
    { value: 'VERIFIED', label: '已核验' },
    { value: 'PENDING', label: '待核验' },
    { value: 'REJECTED', label: '核验退回' },
    { value: 'ABNORMAL', label: '核验异常' }
  ],
  identityRecordStatus: [
    { value: 'PENDING_REVIEW', label: '待复核' },
    { value: 'CONFIRMED', label: '已确认' },
    { value: 'ABNORMAL', label: '已标记异常' }
  ],
  identityResult: [
    { value: 'PASS', label: '比对通过' },
    { value: 'FAIL', label: '比对未通过' },
    { value: 'PENDING', label: '等待比对' }
  ],
  correctionStatus: [
    { value: 'PENDING_REVIEW', label: '待审核' },
    { value: 'APPROVED', label: '已通过' },
    { value: 'RETURNED', label: '已退回' }
  ],
  riskLevel: [
    { value: 'LOW', label: '低风险' },
    { value: 'MEDIUM', label: '中风险' },
    { value: 'HIGH', label: '高风险' }
  ],
  riskTagType: [
    { value: 'ACADEMIC', label: '学业风险' },
    { value: 'PSYCH', label: '心理关怀' },
    { value: 'FINANCE', label: '经济困难' },
    { value: 'INTERNSHIP', label: '实习风险' },
    { value: 'EMPLOYMENT', label: '就业风险' },
    { value: 'IDENTITY', label: '身份异常' },
    { value: 'DISCIPLINE', label: '纪律关注' }
  ],
  riskTagStatus: [
    { value: 'ACTIVE', label: '生效中' },
    { value: 'FOLLOWING', label: '跟进中' },
    { value: 'RESOLVED', label: '已解除' },
    { value: 'VOIDED', label: '已作废' }
  ],
  accountBindStatus: [
    { value: 'BOUND', label: '已绑定' },
    { value: 'UNBOUND', label: '未绑定' }
  ],
  correctionChannel: [
    { value: '学生小程序', label: '学生小程序' },
    { value: 'PC 学生门户', label: 'PC 学生门户' },
    { value: '迎新小程序', label: '迎新小程序' }
  ]
}

export const filterOptions = {
  colleges: collegeList,
  majors: majorList,
  classes: classList.map((c) => ({ value: c.value, label: c.label })),
  grades: [
    { value: '2022级', label: '2022级' },
    { value: '2023级', label: '2023级' },
    { value: '2026级', label: '2026级' }
  ],
  counselors: counselorOptions
}

/* ================= 审计留痕（模块级，新事件 unshift） ================= */
export const auditLogs = [
  {
    id: 'aud-001',
    time: '2026-07-02 09:12',
    operator: '李敏',
    roleName: '辅导员',
    action: '风险跟进',
    targetType: 'RISK_TAG',
    targetName: '赵一凡 · 连续 3 天实习打卡异常',
    detail: '新增跟进记录（电话核实驻场地点变更）',
    result: '成功'
  },
  {
    id: 'aud-002',
    time: '2026-06-30 17:35',
    operator: '郑雅琴',
    roleName: '学籍老师',
    action: '导出台账',
    targetType: 'EXPORT',
    targetName: '2026 届毕业生学籍台账',
    detail: '脱敏导出 + 水印（用途：上级报表报送）',
    result: '成功'
  },
  {
    id: 'aud-003',
    time: '2026-06-30 17:20',
    operator: '郑雅琴',
    roleName: '学籍老师',
    action: '学籍状态变更',
    targetType: 'STUDENT',
    targetName: '冯天佑（2022115011）',
    detail: '在读 → 已毕业（2026 届毕业审核通过）',
    result: '成功'
  },
  {
    id: 'aud-004',
    time: '2026-06-27 10:30',
    operator: '郑雅琴',
    roleName: '学籍老师',
    action: '更正审核退回',
    targetType: 'CORRECTION',
    targetName: '郑博文 · 身份证号更正',
    detail: '退回原因：证件类关键字段必须上传身份证正反面照片',
    result: '成功'
  },
  {
    id: 'aud-005',
    time: '2026-06-20 10:05',
    operator: '管理员甲',
    roleName: '系统管理员',
    action: '批量导入',
    targetType: 'IMPORT',
    targetName: '2026 级新生录取名单首批',
    detail: '导入 1 条，成功 1 条，失败 0 条',
    result: '成功'
  },
  {
    id: 'aud-006',
    time: '2026-06-18 15:02',
    operator: '郑雅琴',
    roleName: '学籍老师',
    action: '更正审核通过',
    targetType: 'CORRECTION',
    targetName: '钱雨桐 · 姓名更正',
    detail: '钱雨彤 → 钱雨桐（已核对身份证原件）',
    result: '成功'
  }
]
