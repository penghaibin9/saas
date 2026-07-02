/**
 * 演示剧本数据库（V2.1 §10 Mock 数据剧本规范）
 * 五个标准演示角色互相关联：学生 ↔ 班级 ↔ 老师 ↔ 企业 ↔ 毕设 ↔ 实习 ↔ 打卡 ↔ 周报 ↔ 就业 ↔ 待办 ↔ 消息。
 * 驾驶舱指标一律由本文件数据经 utils/aggregate 计算，禁止任何地方硬编码指标值。
 */

/** 剧本基准日（“今天”），所有日期围绕它展开 */
export const TODAY = '2026-07-02'
/** 当前实习周次（用于本周周报提交率计算） */
export const CURRENT_WEEK = 4

/* ================= 教师 ================= */
export const teachers = [
  {
    id: 't-001',
    name: '王芳',
    identities: ['毕设导师'],
    college: '软件学院',
    dataScope: '本人指导毕设学生'
  },
  {
    id: 't-002',
    name: '刘强',
    identities: ['实习指导教师'],
    college: '软件学院',
    dataScope: '本人指导实习学生'
  },
  {
    id: 't-003',
    name: '李敏',
    identities: ['辅导员', '就业老师'],
    college: '软件学院',
    dataScope: '所带班级学生'
  }
]

/* ================= 企业 ================= */
export const enterprises = [
  {
    id: 'ent-001',
    name: '华信智能科技有限公司',
    industry: '软件与信息服务',
    riskFlag: 'NORMAL',
    mentorName: '周工',
    mentorPhone: '13800001111'
  },
  {
    id: 'ent-002',
    name: '星辰网络技术有限公司',
    industry: '互联网',
    riskFlag: 'HIGH_RISK',
    mentorName: '吴经理',
    mentorPhone: '13900002222'
  }
]

/* ================= 学生（五个剧本角色） ================= */
export const students = [
  {
    id: 'stu-001',
    studentId: 'S2026-000001',
    name: '赵一凡',
    college: '软件学院',
    major: '软件技术',
    classId: 'c-2301',
    className: '软件2301',
    stage: '岗位实习',
    status: 'RISK',
    riskLevel: 'HIGH',
    counselorId: 't-003',
    internAdvisorId: 't-002',
    phone: '13512346867',
    lastActivity: '连续 3 天打卡异常，第 4 周周报未提交'
  },
  {
    id: 'stu-002',
    studentId: 'S2026-000002',
    name: '陈思雨',
    college: '智能制造学院',
    major: '机电一体化',
    classId: 'c-2302j',
    className: '机电2302',
    stage: '毕业设计',
    status: 'ACTIVE',
    riskLevel: 'LOW',
    counselorId: 't-003',
    gdAdvisorId: 't-001',
    internAdvisorId: 't-002',
    phone: '13612347788',
    lastActivity: '开题优秀，中期已通过，企业拟录用'
  },
  {
    id: 'stu-003',
    studentId: 'S2026-000003',
    name: '李佳',
    college: '软件学院',
    major: '软件技术',
    classId: 'c-2302',
    className: '软件2302',
    stage: '毕业就业',
    status: 'ACTIVE',
    riskLevel: 'MEDIUM',
    counselorId: 't-003',
    phone: '13712348899',
    lastActivity: '就业证明材料被退回，待重新上传'
  },
  {
    id: 'stu-004',
    studentId: 'S2026-000004',
    name: '王浩',
    college: '软件学院',
    major: '软件技术',
    classId: 'c-2301',
    className: '软件2301',
    stage: '毕业设计',
    status: 'RISK',
    riskLevel: 'MEDIUM',
    counselorId: 't-003',
    gdAdvisorId: 't-001',
    phone: '13812349900',
    lastActivity: '开题报告逾期 2 天未提交'
  },
  {
    id: 'stu-005',
    studentId: 'S2026-000005',
    name: '张明',
    college: '软件学院',
    major: '软件技术',
    classId: 'c-2301',
    className: '软件2301',
    stage: '岗位实习',
    status: 'ACTIVE',
    riskLevel: 'LOW',
    counselorId: 't-003',
    gdAdvisorId: 't-001',
    internAdvisorId: 't-002',
    phone: '13912340011',
    lastActivity: '实习正常，周报按时提交'
  }
]

/* ================= 毕业设计任务 ================= */
export const gdTasks = [
  {
    id: 'gd-001',
    studentId: 'stu-002',
    title: '基于机器视觉的零件缺陷检测系统',
    advisorId: 't-001',
    batch: '2026届毕业设计批次',
    nodes: {
      opening: {
        status: 'APPROVED',
        deadline: '2026-06-30',
        submittedAt: '2026-06-20',
        score: '优秀'
      },
      midterm: { status: 'APPROVED', deadline: '2026-07-20', submittedAt: '2026-06-28' },
      final: { status: 'PENDING_SUBMIT', deadline: '2026-08-30' }
    }
  },
  {
    id: 'gd-002',
    studentId: 'stu-004',
    title: '校园二手交易小程序设计与实现',
    advisorId: 't-001',
    batch: '2026届毕业设计批次',
    nodes: {
      opening: { status: 'OVERDUE', deadline: '2026-06-30' },
      midterm: { status: 'NOT_STARTED', deadline: '2026-07-20' },
      final: { status: 'NOT_STARTED', deadline: '2026-08-30' }
    }
  },
  {
    id: 'gd-003',
    studentId: 'stu-005',
    title: '实习打卡数据可视化分析平台',
    advisorId: 't-001',
    batch: '2026届毕业设计批次',
    nodes: {
      opening: {
        status: 'APPROVED',
        deadline: '2026-06-30',
        submittedAt: '2026-06-25',
        score: '良好'
      },
      midterm: { status: 'PENDING_REVIEW', deadline: '2026-07-20', submittedAt: '2026-07-01' },
      final: { status: 'NOT_STARTED', deadline: '2026-08-30' }
    }
  }
]

/* ================= 实习记录 ================= */
export const internships = [
  {
    id: 'int-001',
    studentId: 'stu-001',
    enterpriseId: 'ent-002',
    post: '前端开发实习生',
    advisorId: 't-002',
    status: 'ONBOARD',
    riskLevel: 'HIGH',
    startDate: '2026-06-08',
    intendedHire: false
  },
  {
    id: 'int-002',
    studentId: 'stu-002',
    enterpriseId: 'ent-001',
    post: '设备调试实习生',
    advisorId: 't-002',
    status: 'ONBOARD',
    riskLevel: 'LOW',
    startDate: '2026-06-08',
    intendedHire: true
  },
  {
    id: 'int-003',
    studentId: 'stu-005',
    enterpriseId: 'ent-001',
    post: '测试实习生',
    advisorId: 't-002',
    status: 'ONBOARD',
    riskLevel: 'LOW',
    startDate: '2026-06-08',
    intendedHire: false
  }
]

/* ================= 打卡记录（近 4 个工作日 + 今天） =================
   赵一凡：6-29 / 6-30 / 7-01 连续 3 天异常，今天未打卡（剧本核心）
   陈思雨、张明：全部正常 */
export const checkins = [
  // 赵一凡
  { id: 'ck-101', studentId: 'stu-001', date: '2026-06-26', status: 'NORMAL' },
  {
    id: 'ck-102',
    studentId: 'stu-001',
    date: '2026-06-29',
    status: 'ABNORMAL',
    note: '定位超出实习范围'
  },
  { id: 'ck-103', studentId: 'stu-001', date: '2026-06-30', status: 'MISSING', note: '未打卡' },
  {
    id: 'ck-104',
    studentId: 'stu-001',
    date: '2026-07-01',
    status: 'ABNORMAL',
    note: '定位超出实习范围'
  },
  // 陈思雨
  { id: 'ck-201', studentId: 'stu-002', date: '2026-06-29', status: 'NORMAL' },
  { id: 'ck-202', studentId: 'stu-002', date: '2026-06-30', status: 'NORMAL' },
  { id: 'ck-203', studentId: 'stu-002', date: '2026-07-01', status: 'NORMAL' },
  { id: 'ck-204', studentId: 'stu-002', date: '2026-07-02', status: 'NORMAL' },
  // 张明
  { id: 'ck-301', studentId: 'stu-005', date: '2026-06-29', status: 'NORMAL' },
  { id: 'ck-302', studentId: 'stu-005', date: '2026-06-30', status: 'NORMAL' },
  { id: 'ck-303', studentId: 'stu-005', date: '2026-07-01', status: 'NORMAL' },
  { id: 'ck-304', studentId: 'stu-005', date: '2026-07-02', status: 'NORMAL' }
]

/* ================= 实习周报（当前第 4 周） =================
   赵一凡第 4 周未提交（剧本核心）；张明、陈思雨按时提交 */
export const weeklyReports = [
  {
    id: 'wr-101',
    studentId: 'stu-001',
    week: 1,
    status: 'APPROVED',
    submittedAt: '2026-06-12',
    reviewerId: 't-002'
  },
  {
    id: 'wr-102',
    studentId: 'stu-001',
    week: 2,
    status: 'APPROVED',
    submittedAt: '2026-06-19',
    reviewerId: 't-002'
  },
  {
    id: 'wr-103',
    studentId: 'stu-001',
    week: 3,
    status: 'RETURNED',
    submittedAt: '2026-06-26',
    reviewerId: 't-002',
    returnReason: '周报内容过于简单，请补充本周工作内容与收获'
  },
  // 赵一凡第 4 周：无记录 = 未提交
  {
    id: 'wr-201',
    studentId: 'stu-002',
    week: 1,
    status: 'APPROVED',
    submittedAt: '2026-06-12',
    reviewerId: 't-002'
  },
  {
    id: 'wr-202',
    studentId: 'stu-002',
    week: 2,
    status: 'APPROVED',
    submittedAt: '2026-06-19',
    reviewerId: 't-002'
  },
  {
    id: 'wr-203',
    studentId: 'stu-002',
    week: 3,
    status: 'APPROVED',
    submittedAt: '2026-06-26',
    reviewerId: 't-002'
  },
  { id: 'wr-204', studentId: 'stu-002', week: 4, status: 'SUBMITTED', submittedAt: '2026-07-01' },
  {
    id: 'wr-301',
    studentId: 'stu-005',
    week: 1,
    status: 'APPROVED',
    submittedAt: '2026-06-12',
    reviewerId: 't-002'
  },
  {
    id: 'wr-302',
    studentId: 'stu-005',
    week: 2,
    status: 'APPROVED',
    submittedAt: '2026-06-19',
    reviewerId: 't-002'
  },
  {
    id: 'wr-303',
    studentId: 'stu-005',
    week: 3,
    status: 'APPROVED',
    submittedAt: '2026-06-26',
    reviewerId: 't-002'
  },
  { id: 'wr-304', studentId: 'stu-005', week: 4, status: 'SUBMITTED', submittedAt: '2026-07-02' }
]

/* ================= 就业记录 ================= */
export const employments = [
  {
    id: 'emp-001',
    studentId: 'stu-003',
    direction: 'EMPLOYED',
    company: '长沙某软件公司',
    materialStatus: 'RETURNED',
    returnReason: '就业证明材料不清晰，请重新扫描上传',
    verifierId: 't-003'
  },
  {
    id: 'emp-002',
    studentId: 'stu-002',
    direction: 'INTENTION',
    company: '华信智能科技有限公司',
    materialStatus: 'PENDING'
  }
]

/* ================= 待办 ================= */
export const todos = [
  // 学生侧
  {
    id: 'td-001',
    ownerType: 'student',
    ownerId: 'stu-001',
    title: '提交第 4 周实习周报',
    sourceModule: '岗位实习',
    studentId: 'stu-001',
    deadline: '2026-07-01',
    priority: 'high',
    status: 'OVERDUE',
    overdue: true
  },
  {
    id: 'td-002',
    ownerType: 'student',
    ownerId: 'stu-001',
    title: '补充第 3 周周报（被退回）',
    sourceModule: '岗位实习',
    studentId: 'stu-001',
    deadline: '2026-07-03',
    priority: 'high',
    status: 'RETURNED',
    overdue: false,
    returnReason: '周报内容过于简单，请补充本周工作内容与收获'
  },
  {
    id: 'td-003',
    ownerType: 'student',
    ownerId: 'stu-003',
    title: '重新上传就业证明材料',
    sourceModule: '毕业就业',
    studentId: 'stu-003',
    deadline: '2026-07-05',
    priority: 'medium',
    status: 'RETURNED',
    overdue: false,
    returnReason: '就业证明材料不清晰，请重新扫描上传'
  },
  {
    id: 'td-004',
    ownerType: 'student',
    ownerId: 'stu-004',
    title: '提交毕业设计开题报告',
    sourceModule: '毕业设计',
    studentId: 'stu-004',
    deadline: '2026-06-30',
    priority: 'high',
    status: 'OVERDUE',
    overdue: true
  },
  // 教师侧
  {
    id: 'td-101',
    ownerType: 'teacher',
    ownerId: 't-002',
    title: '处理赵一凡连续 3 天打卡异常',
    sourceModule: '岗位实习',
    studentId: 'stu-001',
    deadline: '2026-07-02',
    priority: 'high',
    status: 'PENDING_HANDLE',
    overdue: false
  },
  {
    id: 'td-102',
    ownerType: 'teacher',
    ownerId: 't-002',
    title: '批阅张明第 4 周周报',
    sourceModule: '岗位实习',
    studentId: 'stu-005',
    deadline: '2026-07-04',
    priority: 'medium',
    status: 'PENDING_REVIEW',
    overdue: false
  },
  {
    id: 'td-103',
    ownerType: 'teacher',
    ownerId: 't-002',
    title: '批阅陈思雨第 4 周周报',
    sourceModule: '岗位实习',
    studentId: 'stu-002',
    deadline: '2026-07-04',
    priority: 'medium',
    status: 'PENDING_REVIEW',
    overdue: false
  },
  {
    id: 'td-104',
    ownerType: 'teacher',
    ownerId: 't-001',
    title: '催办王浩开题报告（已逾期 2 天）',
    sourceModule: '毕业设计',
    studentId: 'stu-004',
    deadline: '2026-07-02',
    priority: 'high',
    status: 'PENDING_HANDLE',
    overdue: false
  },
  {
    id: 'td-105',
    ownerType: 'teacher',
    ownerId: 't-001',
    title: '批阅张明中期检查材料',
    sourceModule: '毕业设计',
    studentId: 'stu-005',
    deadline: '2026-07-06',
    priority: 'medium',
    status: 'PENDING_REVIEW',
    overdue: false
  },
  {
    id: 'td-106',
    ownerType: 'teacher',
    ownerId: 't-003',
    title: '核验李佳重新上传的就业材料',
    sourceModule: '毕业就业',
    studentId: 'stu-003',
    deadline: '2026-07-06',
    priority: 'medium',
    status: 'PENDING_HANDLE',
    overdue: false
  },
  // 企业侧
  {
    id: 'td-201',
    ownerType: 'enterprise',
    ownerId: 'ent-001',
    title: '确认陈思雨录用意向',
    sourceModule: '岗位实习',
    studentId: 'stu-002',
    deadline: '2026-07-10',
    priority: 'medium',
    status: 'PENDING_HANDLE',
    overdue: false
  },
  {
    id: 'td-202',
    ownerType: 'enterprise',
    ownerId: 'ent-001',
    title: '提交张明月度企业评价',
    sourceModule: '岗位实习',
    studentId: 'stu-005',
    deadline: '2026-07-08',
    priority: 'low',
    status: 'PENDING_HANDLE',
    overdue: false
  }
]

/* ================= 消息 ================= */
export const messages = [
  {
    id: 'msg-001',
    toType: 'student',
    toId: 'stu-001',
    title: '你已连续 3 天打卡异常，请尽快说明情况',
    source: '岗位实习',
    time: '2026-07-01 18:00',
    read: false,
    needHandle: true,
    studentId: 'stu-001'
  },
  {
    id: 'msg-002',
    toType: 'student',
    toId: 'stu-001',
    title: '第 3 周周报被退回，请查看退回原因',
    source: '岗位实习',
    time: '2026-06-27 10:20',
    read: true,
    needHandle: true,
    studentId: 'stu-001'
  },
  {
    id: 'msg-003',
    toType: 'student',
    toId: 'stu-003',
    title: '就业证明材料被退回，请重新上传',
    source: '毕业就业',
    time: '2026-07-01 15:40',
    read: false,
    needHandle: true,
    studentId: 'stu-003'
  },
  {
    id: 'msg-004',
    toType: 'student',
    toId: 'stu-004',
    title: '开题报告已逾期，请尽快提交',
    source: '毕业设计',
    time: '2026-07-01 09:00',
    read: false,
    needHandle: true,
    studentId: 'stu-004'
  },
  {
    id: 'msg-005',
    toType: 'student',
    toId: 'stu-002',
    title: '恭喜！华信智能科技已提交录用意向',
    source: '毕业就业',
    time: '2026-06-30 16:30',
    read: true,
    needHandle: false,
    studentId: 'stu-002'
  },
  {
    id: 'msg-101',
    toType: 'teacher',
    toId: 't-002',
    title: '赵一凡今日仍未打卡，风险升级提醒',
    source: '岗位实习',
    time: '2026-07-02 09:30',
    read: false,
    needHandle: true,
    studentId: 'stu-001'
  },
  {
    id: 'msg-102',
    toType: 'teacher',
    toId: 't-001',
    title: '王浩开题报告逾期 2 天未提交',
    source: '毕业设计',
    time: '2026-07-02 08:00',
    read: false,
    needHandle: true,
    studentId: 'stu-004'
  },
  {
    id: 'msg-201',
    toType: 'enterprise',
    toId: 'ent-001',
    title: '请确认陈思雨的录用意向',
    source: '岗位实习',
    time: '2026-07-01 14:00',
    read: false,
    needHandle: true,
    studentId: 'stu-002'
  }
]

/** 关联查询小工具（mock 层内部使用） */
export const findStudent = (id) => students.find((s) => s.id === id)
export const findTeacher = (id) => teachers.find((t) => t.id === id)
export const findEnterprise = (id) => enterprises.find((e) => e.id === id)
