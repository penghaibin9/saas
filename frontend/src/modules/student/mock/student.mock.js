/**
 * 01 学生主档 — mock 数据源（唯一入口，页面禁止直引）
 * 30 条学生数据程序化生成，保证字典一致性（collegeId/majorId/classId/grade 均可在字典中找到）。
 * mock 含身份证/手机号原文——页面展示必须经 security 脱敏；禁止 console 输出。
 */
import {
  GENDER,
  EDUCATION_LEVEL,
  STUDENT_TYPE,
  STUDENT_STATUS,
  ACADEMIC_STATUS,
  IDENTITY_VERIFY_STATUS,
  ACCOUNT_STATUS,
  ACCOUNT_BIND_STATUS,
  REGISTRATION_STATUS,
  DATA_QUALITY_STATUS,
  RISK_FLAG
} from '../constants/student.constants'

/* ---------------- 字典（options 接口返回，页面下拉唯一来源） ---------------- */
export const colleges = [
  { id: 'col-01', name: '信息工程学院' },
  { id: 'col-02', name: '智能制造学院' },
  { id: 'col-03', name: '经济管理学院' }
]

export const majors = [
  { id: 'maj-01', collegeId: 'col-01', name: '软件技术' },
  { id: 'maj-02', collegeId: 'col-01', name: '大数据技术' },
  { id: 'maj-03', collegeId: 'col-02', name: '机电一体化' },
  { id: 'maj-04', collegeId: 'col-02', name: '工业机器人' },
  { id: 'maj-05', collegeId: 'col-03', name: '电子商务' }
]

export const classes = [
  { id: 'cls-01', majorId: 'maj-01', name: '软件2301' },
  { id: 'cls-02', majorId: 'maj-01', name: '软件2302' },
  { id: 'cls-03', majorId: 'maj-02', name: '大数据2301' },
  { id: 'cls-04', majorId: 'maj-03', name: '机电2301' },
  { id: 'cls-05', majorId: 'maj-04', name: '机器人2301' },
  { id: 'cls-06', majorId: 'maj-05', name: '电商2301' }
]

export const grades = [
  { id: '2023', name: '2023 级' },
  { id: '2024', name: '2024 级' },
  { id: '2025', name: '2025 级' }
]

export const academicYears = [
  { id: '2025-2026', name: '2025-2026 学年' },
  { id: '2024-2025', name: '2024-2025 学年' }
]

export const terms = [
  { id: 'T1', name: '第一学期' },
  { id: 'T2', name: '第二学期' }
]

/* ---------------- 学生生成（30 条，覆盖各状态剧本） ---------------- */
const SURNAMES = ['李', '王', '张', '刘', '陈', '杨', '黄', '周', '吴', '徐']
const GIVEN = ['明轩', '子涵', '雨欣', '浩然', '思远', '嘉怡', '志强', '静怡', '俊杰', '晓彤']

const pad = (n, w = 2) => String(n).padStart(w, '0')

function buildStudent(i) {
  const cls = classes[i % classes.length]
  const major = majors.find((m) => m.id === cls.majorId)
  const college = colleges.find((c) => c.id === major.collegeId)
  const grade = grades[i % grades.length]
  const gender = i % 3 === 0 ? GENDER.FEMALE : i % 7 === 0 ? GENDER.UNKNOWN : GENDER.MALE
  const name = SURNAMES[i % SURNAMES.length] + GIVEN[(i * 3) % GIVEN.length]

  // 剧本分布：0-17 常规在校；18 休学；19 保留；20 转学；21 退学；22-23 毕业；24 归档
  // 认证：i%5==1 待核验；i%9==4 退回；25 证件过期；i%11==6 未认证；其余已认证
  // 质量：26 缺必填；27 需复核；28 冲突；账号：i%6==2 未绑定；29 锁定
  const studentStatus =
    i === 18 ? STUDENT_STATUS.SUSPENDED
    : i === 19 ? STUDENT_STATUS.RETAINED
    : i === 20 ? STUDENT_STATUS.TRANSFERRED
    : i === 21 ? STUDENT_STATUS.DROPPED_OUT
    : i === 22 || i === 23 ? STUDENT_STATUS.GRADUATED
    : i === 24 ? STUDENT_STATUS.ARCHIVED
    : STUDENT_STATUS.ACTIVE

  const identityVerifyStatus =
    i === 25 ? IDENTITY_VERIFY_STATUS.EXPIRED
    : i % 9 === 4 ? IDENTITY_VERIFY_STATUS.REJECTED
    : i % 5 === 1 ? IDENTITY_VERIFY_STATUS.PENDING
    : i % 11 === 6 ? IDENTITY_VERIFY_STATUS.UNVERIFIED
    : IDENTITY_VERIFY_STATUS.VERIFIED

  const dataQuality =
    i === 26 ? DATA_QUALITY_STATUS.MISSING_REQUIRED
    : i === 27 ? DATA_QUALITY_STATUS.NEED_REVIEW
    : i === 28 ? DATA_QUALITY_STATUS.CONFLICT
    : DATA_QUALITY_STATUS.COMPLETE

  const accountBind =
    i === 29 ? ACCOUNT_BIND_STATUS.LOCKED : i % 6 === 2 ? ACCOUNT_BIND_STATUS.UNBOUND : ACCOUNT_BIND_STATUS.BOUND

  const academicStatus =
    i % 8 === 3 ? ACADEMIC_STATUS.WARNING : studentStatus === STUDENT_STATUS.GRADUATED ? ACADEMIC_STATUS.COMPLETED : ACADEMIC_STATUS.NORMAL

  const riskFlags = []
  if (academicStatus === ACADEMIC_STATUS.WARNING) riskFlags.push(RISK_FLAG.ACADEMIC_WARNING)
  if (dataQuality === DATA_QUALITY_STATUS.MISSING_REQUIRED) riskFlags.push(RISK_FLAG.DATA_MISSING)
  if (identityVerifyStatus === IDENTITY_VERIFY_STATUS.EXPIRED) riskFlags.push(RISK_FLAG.ID_EXPIRED)
  if (dataQuality === DATA_QUALITY_STATUS.NEED_REVIEW || dataQuality === DATA_QUALITY_STATUS.CONFLICT) riskFlags.push(RISK_FLAG.NEED_REVIEW)
  if (accountBind === ACCOUNT_BIND_STATUS.UNBOUND) riskFlags.push(RISK_FLAG.ACCOUNT_UNBOUND)

  const missing = dataQuality === DATA_QUALITY_STATUS.MISSING_REQUIRED
  const enrollmentYear = Number(grade.id)

  return {
    studentId: `stu-${pad(i + 1, 4)}`,
    studentNo: `${grade.id}${pad(i + 1, 4)}`,
    name,
    gender,
    idCard: missing ? '' : `43010${pad(i % 10, 1)}${enrollmentYear - 18}${pad((i % 12) + 1)}${pad((i % 27) + 1)}${pad(i, 4)}`,
    phone: missing ? '' : `139${pad(1000 + i * 7, 4)}${pad(2000 + i * 13, 4)}`,
    email: `s${grade.id}${pad(i + 1, 4)}@school-demo.edu.cn`,
    avatar: '',
    birthday: `${enrollmentYear - 18}-0${(i % 9) + 1}-1${i % 9}`,
    nationality: '汉族',
    politicalStatus: i % 4 === 0 ? '共青团员' : '群众',
    homeAddress: missing ? '' : `湖南省长沙市岳麓区示例街道${i + 1}号`,
    currentAddress: `学生公寓${(i % 8) + 1}栋${pad((i % 30) + 101, 3)}室`,
    schoolId: 'tenant-demo-a',
    schoolName: '演示职业技术学院',
    collegeId: college.id,
    collegeName: college.name,
    majorId: major.id,
    majorName: major.name,
    classId: cls.id,
    className: cls.name,
    grade: grade.id,
    enrollmentYear,
    educationLevel: i % 10 === 9 ? EDUCATION_LEVEL.SECONDARY : EDUCATION_LEVEL.HIGHER_VOCATIONAL,
    studentType: i % 12 === 11 ? STUDENT_TYPE.TRANSFER : STUDENT_TYPE.FULL_TIME,
    studentStatus,
    academicStatus,
    accountStatus:
      accountBind === ACCOUNT_BIND_STATUS.LOCKED ? ACCOUNT_STATUS.LOCKED
      : accountBind === ACCOUNT_BIND_STATUS.UNBOUND ? ACCOUNT_STATUS.UNBOUND
      : ACCOUNT_STATUS.NORMAL,
    identityVerifyStatus,
    idCardExpireDate: i === 25 ? '2026-05-01' : '2035-12-31',
    sourceChannel: i % 2 === 0 ? '统一招生导入' : '迎新登记',
    createdAt: `${enrollmentYear}-09-01 10:00`,
    updatedAt: '2026-07-02 09:00',
    // 学籍
    enrollmentDate: `${enrollmentYear}-09-01`,
    expectedGraduationDate: `${enrollmentYear + 3}-06-30`,
    academicYear: '2025-2026',
    academicTerm: 'T2',
    studyDuration: 3,
    isRegistered: i % 13 !== 5,
    registrationStatus: i % 13 === 5 ? REGISTRATION_STATUS.DELAYED : REGISTRATION_STATUS.REGISTERED,
    transferStatus: '',
    leaveStatus: studentStatus === STUDENT_STATUS.SUSPENDED ? 'ON_LEAVE' : '',
    graduationStatus: studentStatus === STUDENT_STATUS.GRADUATED ? 'GRADUATED' : '',
    // 账号
    userId: accountBind === ACCOUNT_BIND_STATUS.UNBOUND ? '' : `u-stu-${pad(i + 1, 4)}`,
    bindStatus: accountBind,
    lastLoginAt: accountBind === ACCOUNT_BIND_STATUS.BOUND ? '2026-07-01 20:1' + (i % 10) : '',
    mfaEnabled: false,
    forcePasswordChange: i % 15 === 8,
    mobileBound: accountBind === ACCOUNT_BIND_STATUS.BOUND,
    wechatBound: i % 4 !== 0 && accountBind === ACCOUNT_BIND_STATUS.BOUND,
    // 风险/标签
    riskFlags,
    specialTags: i % 14 === 10 ? ['困难帮扶'] : [],
    dataQualityTags: [dataQuality],
    remark: '',
    // 数据范围
    tenantId: 'tenant-demo-a',
    assignedUserIds: [],
    assignedTeacherIds: ['t-002']
  }
}

export const students = Array.from({ length: 30 }, (_, i) => buildStudent(i))

/* ---------------- 监护人（每生 1-2 位，字段含敏感原文） ---------------- */
export const guardians = students.flatMap((s, i) => {
  const list = [
    {
      guardianId: `g-${s.studentId}-1`,
      studentId: s.studentId,
      guardianName: s.name.slice(0, 1) + '父',
      relationship: '父亲',
      guardianPhone: `138${pad(3000 + i * 11, 4)}${pad(4000 + i * 3, 4)}`,
      guardianIdCard: `4301021975${pad((i % 12) + 1)}${pad((i % 27) + 1)}${pad(i, 4)}`,
      guardianAddress: s.homeAddress || '湖南省长沙市（未登记）',
      isEmergencyContact: true,
      isPrimaryGuardian: true
    }
  ]
  if (i % 3 === 0) {
    list.push({
      guardianId: `g-${s.studentId}-2`,
      studentId: s.studentId,
      guardianName: s.name.slice(0, 1) + '母',
      relationship: '母亲',
      guardianPhone: `137${pad(5000 + i * 9, 4)}${pad(6000 + i * 5, 4)}`,
      guardianIdCard: '',
      guardianAddress: s.homeAddress || '',
      isEmergencyContact: false,
      isPrimaryGuardian: false
    })
  }
  return list
})

/* ---------------- 时间线 / 核验记录 / 审计 ---------------- */
export const timelines = {}
export const verifyRecords = {}
export const auditLogs = {}

students.forEach((s) => {
  timelines[s.studentId] = [
    { time: s.createdAt, type: 'CREATED', title: '建立学生主档', operator: '系统导入', detail: s.sourceChannel },
    ...(s.identityVerifyStatus === 'VERIFIED'
      ? [{ time: `${s.enrollmentYear}-09-03 14:00`, type: 'IDENTITY', title: '身份核验通过', operator: '辅导员', detail: '' }]
      : []),
    ...(s.identityVerifyStatus === 'REJECTED'
      ? [{ time: '2026-06-20 10:00', type: 'IDENTITY', title: '身份核验退回', operator: '辅导员', detail: '证件照片模糊，请重新上传清晰版本' }]
      : []),
    ...(s.studentStatus === 'SUSPENDED'
      ? [{ time: '2026-03-01 09:00', type: 'STATUS', title: '状态变更：在校 → 休学', operator: '学籍管理员', detail: '因病休学一年' }]
      : [])
  ]
  verifyRecords[s.studentId] =
    s.identityVerifyStatus === 'REJECTED'
      ? [{ time: '2026-06-20 10:00', operator: '辅导员', action: 'REJECT', comment: '证件照片模糊，请重新上传清晰版本' }]
      : s.identityVerifyStatus === 'VERIFIED'
        ? [{ time: `${s.enrollmentYear}-09-03 14:00`, operator: '辅导员', action: 'APPROVE', comment: '' }]
        : []
  auditLogs[s.studentId] = [
    { time: s.createdAt, operator: '系统导入', action: '建档', before: '', after: '主档创建' }
  ]
})

/* ---------------- 模拟开关（错误/空态） ---------------- */
export const mockFlags = { forceError: false, forceEmpty: false }
export function setMockFlags(flags) {
  Object.assign(mockFlags, flags)
}

export function nowText() {
  const d = new Date()
  const p = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`
}
