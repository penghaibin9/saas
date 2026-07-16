/**
 * 角色 / 权限 / 数据范围配置
 * ------------------------------------------------------------
 * 小程序端先支持：学生 + 5 类教师身份 + 学院管理员。
 * 说明：
 *  - side：进入学生端(student) 还是教师端(teacher)
 *  - homeRoute：该身份登录后的默认首页
 *  - dataScope：数据范围占位（真实由权限中心下发）
 *  - permissionActions：权限按钮占位（页面按此控制按钮显隐）
 *  - workbench：教师端工作台首屏聚焦模块
 */

export const ROLE = {
  STUDENT: 'student',
  COUNSELOR: 'counselor', // 辅导员 / 班主任
  MENTOR: 'mentor', // 毕业设计指导教师
  INTERN_MENTOR: 'intern_mentor', // 实习指导教师
  EMPLOYMENT: 'employment', // 就业老师
  ACADEMIC: 'academic', // 教务老师
  COLLEGE_ADMIN: 'college_admin' // 学院管理员
}

export const roleConfigs = {
  [ROLE.STUDENT]: {
    key: ROLE.STUDENT,
    label: '学生',
    side: 'student',
    homeRoute: '/pages/student/home/index',
    dataScope: 'SELF',
    dataScopeText: '本人',
    permissionActions: [
      'service.apply', 'material.submit', 'internship.checkin',
      'internship.weekly.submit', 'leave.apply', 'employment.report', 'profile.correct'
    ]
  },
  [ROLE.COUNSELOR]: {
    key: ROLE.COUNSELOR,
    label: '辅导员',
    side: 'teacher',
    homeRoute: '/pages/teacher/workbench/index',
    dataScope: 'CLASS',
    dataScopeText: '所负责班级',
    workbench: ['risk', 'approval', 'contact'],
    quickActions: [
      { key: 'myClasses', label: '我的班级', icon: '🏫' },
      { key: 'myStudents', label: '我的学生', icon: '👥' },
      { key: 'talk', label: '谈心谈话', icon: '💬' },
      { key: 'mental', label: '心理关注', icon: '🧠' },
      { key: 'contact', label: '联系学生', icon: '☎' },
      { key: 'record', label: '记录联系', icon: '✎' },
      { key: 'risk', label: '风险学生', icon: '⚠' },
      { key: 'care', label: '创建关怀', icon: '♥' },
      { key: 'affairs', label: '学工待办', icon: '📋' },
      { key: 'campus-service', label: '在校服务', icon: '📄' },
      { key: 'affairs-stats', label: '学工统计', icon: '📈' },
      { key: 'notifyPublish', label: '发布通知', icon: '📣' },
      { key: 'orientationVerify', label: '迎新核验', icon: '▣' }
    ],
    permissionActions: ['approval.handle', 'risk.handle', 'student.contact', 'care.create', 'student360.view']
  },
  [ROLE.MENTOR]: {
    key: ROLE.MENTOR,
    label: '指导教师',
    side: 'teacher',
    homeRoute: '/pages/teacher/workbench/index',
    dataScope: 'MENTEES',
    dataScopeText: '本人指导学生',
    workbench: ['gd-review', 'guide'],
    quickActions: [
      { key: 'topic-review', label: '选题审核', icon: '📝' },
      { key: 'review-open', label: '批阅开题', icon: '▤' },
      { key: 'review-mid', label: '批阅中期', icon: '▥' },
      { key: 'review-result', label: '批阅成果', icon: '▦' },
      { key: 'guide-log', label: '指导记录', icon: '✎' }
    ],
    permissionActions: ['gd.review', 'gd.return', 'gd.guidelog', 'student360.view']
  },
  [ROLE.INTERN_MENTOR]: {
    key: ROLE.INTERN_MENTOR,
    label: '实习指导教师',
    side: 'teacher',
    homeRoute: '/pages/teacher/workbench/index',
    dataScope: 'INTERNS',
    dataScopeText: '本人实习学生',
    workbench: ['intern-review', 'leave', 'risk'],
    quickActions: [
      { key: 'weekly', label: '批阅周报', icon: '▤' },
      { key: 'checkin', label: '异常打卡', icon: '📍' },
      { key: 'leave', label: '请假审批', icon: '✈' },
      { key: 'visit', label: '新增巡访', icon: '✎' }
    ],
    permissionActions: ['intern.weekly.review', 'intern.leave.approve', 'intern.checkin.handle', 'visit.create']
  },
  [ROLE.EMPLOYMENT]: {
    key: ROLE.EMPLOYMENT,
    label: '就业老师',
    side: 'teacher',
    homeRoute: '/pages/teacher/workbench/index',
    dataScope: 'COLLEGE',
    dataScopeText: '本学院范围',
    workbench: ['employment', 'unemployed'],
    quickActions: [
      { key: 'follow', label: '就业跟进', icon: '☎' },
      { key: 'recommend', label: '岗位推荐', icon: '★' },
      { key: 'verify', label: '去向核验', icon: '✓' },
      { key: 'unemployed', label: '未就业', icon: '⚑' }
    ],
    permissionActions: ['employment.follow', 'employment.verify', 'job.recommend', 'student360.view']
  },
  [ROLE.ACADEMIC]: {
    key: ROLE.ACADEMIC,
    label: '教务老师',
    side: 'teacher',
    homeRoute: '/pages/teacher/workbench/index',
    dataScope: 'COLLEGE',
    dataScopeText: '本学院范围',
    workbench: ['academic', 'warning', 'status'],
    quickActions: [
      { key: 'warning', label: '异常预警', icon: '⚠' },
      { key: 'progress', label: '学业进度', icon: '▤' },
      { key: 'status', label: '学籍异动', icon: '⇄' },
      { key: 'approval', label: '待审批', icon: '✓' },
      { key: 'notifyPublish', label: '发布通知', icon: '📣' }
    ],
    permissionActions: ['academic.warning.handle', 'status.handle', 'approval.handle']
  },
  [ROLE.COLLEGE_ADMIN]: {
    key: ROLE.COLLEGE_ADMIN,
    label: '学院管理员',
    side: 'teacher',
    homeRoute: '/pages/teacher/workbench/index',
    dataScope: 'COLLEGE',
    dataScopeText: '本学院范围',
    workbench: ['overview', 'risk', 'approval'],
    quickActions: [
      { key: 'overview', label: '学院数据', icon: '▦' },
      { key: 'risk', label: '风险概览', icon: '⚠' },
      { key: 'urge', label: '移动催办', icon: '☎' },
      { key: 'approval', label: '待审批', icon: '✓' },
      { key: 'notifyPublish', label: '发布通知', icon: '📣' },
      { key: 'orientationDashboard', label: '迎新看板', icon: '🎒' }
    ],
    permissionActions: ['college.overview', 'risk.handle', 'approval.handle', 'urge.send']
  }
}

// 教师端「多身份切换」：同一个人可绑定多个教师身份（08B 3.2 当前工作上下文）
export const teacherIdentities = [
  ROLE.COUNSELOR, ROLE.MENTOR, ROLE.INTERN_MENTOR, ROLE.EMPLOYMENT, ROLE.ACADEMIC, ROLE.COLLEGE_ADMIN
]

export function getRoleConfig(roleKey) {
  return roleConfigs[roleKey] || roleConfigs[ROLE.STUDENT]
}

export function hasAction(roleKey, action) {
  const cfg = getRoleConfig(roleKey)
  return (cfg.permissionActions || []).includes(action)
}

export default roleConfigs
