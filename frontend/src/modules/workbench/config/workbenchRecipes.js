/**
 * 工作台「角色配方」——一个外壳 + 可复用积木 + 每个角色一份积木清单。
 *
 * 设计对标 Microsoft Dynamics 365 Role Center：
 *   - 每个角色一个首页（profile ↔ role center），不是一个首页加过滤器；
 *   - 内容顺序固定 Headline（先给结论）→ Cues（可点击的数字磁贴）→ 明细；
 *   - 数字磁贴必须能下钻到「已筛选好的业务列表」，点不动的数字等于没做。
 *
 * 后端角色（app/core/permissions.py）→ 十二模板（T1–T12）：
 *   T1 ACADEMIC_TEACHER | T2 ACADEMIC_ADMIN | T3 COLLEGE_ADMIN
 *   T4 COUNSELOR | T5 STUDENT_AFFAIRS(_ADMIN) | T6 专项（心理/资助/团委/宿管）
 *   T7 GD_MENTOR | T8 毕设管理 | T9 毕设评审 | T10 INTERN_MENTOR
 *   T11 EMPLOYMENT_TEACHER | T12 管理监督（领导/校管/系统/审计/组织人事）
 * PLATFORM_SUPER_ADMIN 走独立平台入口，不进本配方。
 *
 * cue.source：
 *   'summary.<字段>'  → GET /todos/summary
 *   'todoType.<类型>' → GET /admin/todos/count.byType（仅登记已有 UnifiedTodo 写入的类型）
 *   'stats.<字段>'    → GET /stats/workbench（按数据范围收敛）
 *
 * 硬规则：无真实写入的待办类型不得做分类假磁贴；无权限可达的下钻路径不得挂快捷入口。
 */

/** 待办类型 → 业务落点（带已筛选参数，禁止空壳根路径） */
export const TODO_TYPE_ROUTES = {
  LEAVE_APPROVAL: '/admin/student-affairs/leave?status=PENDING',
  LEAVE_OVERDUE: '/admin/student-affairs/leave/ledger?status=OVERDUE',
  LEAVE_CANCEL: '/admin/student-affairs/leave?status=CANCEL_PENDING',
  LEAVE_EXTENSION: '/admin/student-affairs/leave/followup?status=PENDING',
  DISCIPLINE_APPROVAL: '/admin/student-affairs/discipline?status=PENDING',
  DISCIPLINE_REMOVE: '/admin/student-affairs/discipline?status=REMOVE_PENDING',
  AID_APPROVAL: '/admin/student-affairs/aid?status=PENDING',
  AID_ADJUST: '/admin/student-affairs/aid?status=ADJUST_PENDING',
  FUNDING_APPROVAL: '/admin/student-affairs/funding?status=PENDING',
  RISK_HANDLE: '/admin/student-affairs/risk?status=PENDING',
  AA_STATUS_APPROVAL: '/admin/academic-affairs/status-changes/approval?status=PENDING',
  AA_SCHEDULE_CHANGE_APPROVAL: '/admin/academic-affairs/schedule-change/approval?status=PENDING',
  ACAD_WARNING_HANDLE: '/admin/academic-affairs/warnings?status=OPEN',
  AA_GRADE_ENTRY: '/admin/academic-affairs/grade-entry?filter=pending',
  GD_PROPOSAL_REVIEW: '/admin/graduation/proposals?status=PENDING',
  GD_FINAL_REVIEW: '/admin/graduation/finals?status=PENDING',
  GD_TOPIC_CHANGE_REVIEW: '/admin/graduation/topic-changes?status=PENDING',
  GD_DEFENSE_SCORE: '/admin/graduation/defense-grade?panel=defense&status=PENDING',
  INTERN_WEEKLY_REVIEW: '/admin/internship/reports?status=PENDING',
  INTERN_LEAVE_APPROVAL: '/admin/internship/leaves?status=PENDING',
  INTERN_EXCEPTION_HANDLE: '/admin/internship/exceptions?status=PENDING',
  INTERN_VISIT_RECTIFY: '/admin/internship/guidance?status=RECTIFY',
  DORM_TRANSFER: '/admin/student-affairs/dorm/transfer?status=PENDING',
  DORM_EXCEPTION: '/admin/student-affairs/dorm/exception?status=PENDING_HANDLE',
  EMPLOYMENT_FOLLOWUP: '/admin/employment/followups?status=OPEN'
}

const TODO_ALL = '/admin/approval/todos'
const MY_SCHEDULE = '/admin/academic-affairs/schedule/teacher'
const COCKPIT = '/admin/data-center'
const AUDIT_LOGS = '/admin/system/logs'
const SYSTEM_HOME = '/admin/system'

/** 通用汇总磁贴（含 B5 临近截止；下钻带 urgency 筛选） */
const SUMMARY_CUES = [
  { key: 'pending', title: '待我处理', source: 'summary.pending', accent: 'primary', to: `${TODO_ALL}?status=PENDING` },
  { key: 'overdue', title: '已逾期', source: 'summary.overdue', accent: 'risk', to: `${TODO_ALL}?urgency=OVERDUE` },
  { key: 'nearDeadline', title: '24小时内到期', source: 'summary.nearDeadline', accent: 'warning', to: `${TODO_ALL}?urgency=NEAR` },
  { key: 'doneToday', title: '今日已完成', source: 'summary.doneToday', accent: 'success', to: `${TODO_ALL}?status=DONE` }
]

function withTodoType(path, todoType) {
  const base = path || TODO_ALL
  const sep = base.includes('?') ? '&' : '?'
  return `${base}${sep}todoType=${encodeURIComponent(todoType)}`
}

function typeCue(key, title, accent) {
  return {
    key,
    title,
    source: `todoType.${key}`,
    accent,
    to: withTodoType(TODO_TYPE_ROUTES[key] || TODO_ALL, key)
  }
}

function statsCue(key, title, accent, to) {
  return { key, title, source: `stats.${key}`, accent, to }
}

function pendingHeadline(labelWhenEmpty) {
  return (d) => {
    const s = (d && d.summary) || {}
    if (s.overdue > 0) return `有 ${s.overdue} 项已逾期，建议先处理`
    if (s.nearDeadline > 0) return `有 ${s.nearDeadline} 项将在 24 小时内到期`
    if (s.pending > 0) return `今天有 ${s.pending} 项待你处理`
    return labelWhenEmpty
  }
}

/** 优先用范围内统计说人话，再回落待办汇总 */
function statsFirstHeadline(statsKey, whenPositive, whenEmpty) {
  const base = pendingHeadline(whenEmpty)
  return (d) => {
    const n = Number((d && d.stats && d.stats[statsKey]) || 0)
    if (n > 0) return whenPositive(n)
    return base(d)
  }
}

const SA_TYPE_CUES = [
  typeCue('LEAVE_APPROVAL', '待批请假', 'primary'),
  typeCue('RISK_HANDLE', '风险待处置', 'risk'),
  typeCue('DISCIPLINE_APPROVAL', '违纪待处理', 'warning'),
  typeCue('AID_APPROVAL', '困难认定待审', 'primary'),
  typeCue('FUNDING_APPROVAL', '资助待审', 'primary'),
  typeCue('LEAVE_OVERDUE', '逾期未销假', 'risk')
]

const AA_TYPE_CUES = [
  typeCue('AA_STATUS_APPROVAL', '学籍异动待审', 'warning'),
  typeCue('AA_SCHEDULE_CHANGE_APPROVAL', '调停课待审', 'primary'),
  typeCue('ACAD_WARNING_HANDLE', '学业预警待处置', 'risk')
]

const GD_MENTOR_TYPE_CUES = [
  typeCue('GD_PROPOSAL_REVIEW', '开题待批阅', 'primary'),
  typeCue('GD_FINAL_REVIEW', '成果待批阅', 'warning'),
  typeCue('GD_TOPIC_CHANGE_REVIEW', '选题变更待审', 'primary')
]

const SCOPE_STUDENT_STATS = [
  statsCue('pendingApproval', '待我审批', 'primary', `${TODO_ALL}?status=PENDING`),
  statsCue('studentTotal', '范围内学生', 'primary', '/admin/campus-service/classes'),
  statsCue('academicWarning', '学业预警在办', 'warning', TODO_TYPE_ROUTES.ACAD_WARNING_HANDLE),
  statsCue('orientationPending', '迎新待报到', 'primary', '/admin/orientation/students?status=PENDING')
]

const SCHOOL_STATS = [
  statsCue('pendingApproval', '待我审批', 'primary', `${TODO_ALL}?status=PENDING`),
  // 旧「在校服务·学生服务台账」已退役，在册学生统一进学生主档列表
  statsCue('studentTotal', '在册学生', 'primary', '/admin/student/list'),
  statsCue('academicWarning', '学业预警在办', 'warning', TODO_TYPE_ROUTES.ACAD_WARNING_HANDLE),
  statsCue('unemployed', '未就业学生', 'warning', '/admin/employment/unemployed?status=UNEMPLOYED'),
  statsCue('orientationPending', '迎新待报到', 'primary', '/admin/orientation/students?status=PENDING')
]

export const RECIPES = {
  // ── T4 辅导员 ──
  COUNSELOR: {
    template: 'T4',
    label: '辅导员工作台',
    headline: pendingHeadline('今日无待办，一切正常'),
    summaryCues: SUMMARY_CUES,
    statsCues: [
      statsCue('pendingApproval', '待我审批', 'primary', TODO_ALL),
      statsCue('studentTotal', '我的学生', 'primary', '/admin/campus-service/classes'),
      statsCue('academicWarning', '学业预警在办', 'warning', '/admin/academic-affairs/warnings'),
      statsCue('orientationPending', '迎新待报到', 'primary', '/admin/orientation/students')
    ],
    typeCues: SA_TYPE_CUES,
    quickLinks: [
      { label: '我的班级', to: '/admin/campus-service/classes' },
      { label: '谈心谈话', to: '/admin/student-affairs/talk' },
      { label: '风险台账', to: '/admin/student-affairs/risk' }
    ]
  },

  // ── T1 任课教师：待录成绩写 UnifiedTodo(AA_GRADE_ENTRY) + B8 课表积木 ──
  ACADEMIC_TEACHER: {
    template: 'T1',
    label: '任课教师工作台',
    headline: pendingHeadline('今日无待办，可去录入成绩或查看课表'),
    summaryCues: SUMMARY_CUES,
    statsCues: [],
    typeCues: [typeCue('AA_GRADE_ENTRY', '待录成绩', 'primary')],
    showSchedule: true,
    quickLinks: [
      { label: '成绩录入', to: TODO_TYPE_ROUTES.AA_GRADE_ENTRY },
      { label: '我的课表', to: MY_SCHEDULE },
      { label: '教学任务', to: '/admin/academic-affairs/teaching-tasks' },
      { label: '发起调停课', to: '/admin/academic-affairs/schedule-change/apply' }
    ]
  },

  // ── T2 教务老师（全校）──
  ACADEMIC_ADMIN: {
    template: 'T2',
    label: '教务工作台',
    headline: pendingHeadline('今日无待办，一切正常'),
    summaryCues: SUMMARY_CUES,
    statsCues: [
      statsCue('pendingApproval', '待我审批', 'primary', `${TODO_ALL}?status=PENDING`),
      statsCue('academicWarning', '学业预警在办', 'warning', TODO_TYPE_ROUTES.ACAD_WARNING_HANDLE),
      statsCue('studentTotal', '范围内学生', 'primary', '/admin/academic-affairs/roster')
    ],
    typeCues: AA_TYPE_CUES,
    showSchedule: true,
    quickLinks: [
      { label: '异动审批', to: TODO_TYPE_ROUTES.AA_STATUS_APPROVAL },
      { label: '调停课审批', to: TODO_TYPE_ROUTES.AA_SCHEDULE_CHANGE_APPROVAL },
      { label: '我的课表', to: MY_SCHEDULE },
      { label: '学业预警', to: TODO_TYPE_ROUTES.ACAD_WARNING_HANDLE },
      { label: '成绩管理', to: '/admin/academic-affairs/grade-overview' }
    ]
  },

  // ── T3 院级教学秘书 / 学院管理员：本院口径（数据范围由后端 COLLEGE 收敛）──
  COLLEGE_ADMIN: {
    template: 'T3',
    label: '学院管理工作台',
    headline: pendingHeadline('本院今日无待办，一切正常'),
    summaryCues: SUMMARY_CUES,
    statsCues: SCOPE_STUDENT_STATS,
    typeCues: [...AA_TYPE_CUES, ...SA_TYPE_CUES, ...GD_MENTOR_TYPE_CUES],
    quickLinks: [
      { label: '本院异动审批', to: TODO_TYPE_ROUTES.AA_STATUS_APPROVAL },
      { label: '本院调停课', to: TODO_TYPE_ROUTES.AA_SCHEDULE_CHANGE_APPROVAL },
      { label: '本院风险台账', to: '/admin/student-affairs/risk' },
      { label: '本院毕设学生', to: '/admin/graduation/students?panel=progress' },
      { label: '本院实习学生', to: '/admin/internship/students' }
    ]
  },

  // ── T5 学工处管理员（全校学工口径）──
  STUDENT_AFFAIRS_ADMIN: {
    template: 'T5',
    label: '学工管理工作台',
    headline: pendingHeadline('全校学工今日无待处置事项'),
    summaryCues: SUMMARY_CUES,
    statsCues: SCHOOL_STATS,
    typeCues: SA_TYPE_CUES,
    quickLinks: [
      { label: '风险台账', to: '/admin/student-affairs/risk' },
      { label: '违纪处分', to: '/admin/student-affairs/discipline' },
      { label: '困难认定', to: '/admin/student-affairs/aid' },
      { label: '资助评审', to: '/admin/student-affairs/funding' },
      { label: '学工看板', to: '/admin/student-affairs' }
    ]
  },

  // ── T6a 心理老师 ──
  PSYCHOLOGY_TEACHER: {
    template: 'T6',
    label: '心理工作台',
    headline: pendingHeadline('本条线今日无待办'),
    summaryCues: SUMMARY_CUES,
    statsCues: [
      statsCue('pendingApproval', '待我审批', 'primary', TODO_ALL),
      statsCue('studentTotal', '授权学生', 'primary', '/admin/student-affairs/mental')
    ],
    typeCues: [typeCue('RISK_HANDLE', '风险待处置', 'risk')],
    quickLinks: [
      { label: '心理关注名单', to: '/admin/student-affairs/mental' },
      { label: '危机升级', to: '/admin/student-affairs/mental/crisis' },
      { label: '谈心谈话', to: '/admin/student-affairs/talk' },
      { label: '风险台账', to: '/admin/student-affairs/risk' }
    ]
  },

  // ── T6b 资助老师 ──
  FUNDING_TEACHER: {
    template: 'T6',
    label: '资助工作台',
    headline: pendingHeadline('本条线今日无待审'),
    summaryCues: SUMMARY_CUES,
    statsCues: [
      statsCue('pendingApproval', '待我审批', 'primary', TODO_ALL),
      statsCue('studentTotal', '范围内学生', 'primary', '/admin/student-affairs/aid')
    ],
    typeCues: [
      typeCue('AID_APPROVAL', '困难认定待审', 'primary'),
      typeCue('FUNDING_APPROVAL', '资助待审', 'primary'),
      typeCue('AID_ADJUST', '认定调整待审', 'warning')
    ],
    quickLinks: [
      { label: '困难认定', to: '/admin/student-affairs/aid' },
      { label: '资助评审', to: '/admin/student-affairs/funding' },
      { label: '公示待办', to: '/admin/student-affairs/funding/publicity' },
      { label: '发放台账', to: '/admin/student-affairs/funding/disbursements' }
    ]
  },

  // ── T6c 团委：活动域无审批节点 UnifiedTodo 写入点，诚实能力=汇总+真实入口（不造假磁贴）──
  YOUTH_LEAGUE: {
    template: 'T6',
    label: '团学工作台',
    headline: pendingHeadline('本条线今日无待办，可去发布活动或管理社团'),
    summaryCues: SUMMARY_CUES,
    statsCues: [statsCue('pendingApproval', '待我审批', 'primary', `${TODO_ALL}?status=PENDING`)],
    typeCues: [],
    capabilityNote: '团学活动以发布与管理为主，暂无分类待办写入；数字来自通用待办汇总。',
    quickLinks: [
      { label: '学生活动', to: '/admin/student-affairs/activity' },
      { label: '社团管理', to: '/admin/student-affairs/activity/clubs' },
      { label: '学生组织', to: '/admin/student-affairs/activity/organizations' },
      { label: '党团建设', to: '/admin/student-affairs/activity/party-league' },
      { label: '志愿服务', to: '/admin/student-affairs/activity/volunteer' }
    ]
  },

  // ── T6d 宿管：调宿/异常写 UnifiedTodo ──
  DORM_MANAGER: {
    template: 'T6',
    label: '宿舍管理工作台',
    headline: pendingHeadline('负责楼栋今日无待办，可去检查或处理异常'),
    summaryCues: SUMMARY_CUES,
    statsCues: [statsCue('pendingApproval', '待我审批', 'primary', `${TODO_ALL}?status=PENDING`)],
    typeCues: [
      typeCue('DORM_TRANSFER', '调宿待审', 'primary'),
      typeCue('DORM_EXCEPTION', '宿舍异常待处置', 'risk')
    ],
    quickLinks: [
      { label: '宿舍异常', to: TODO_TYPE_ROUTES.DORM_EXCEPTION },
      { label: '宿舍检查', to: '/admin/student-affairs/dorm/check' },
      { label: '入住管理', to: '/admin/student-affairs/dorm/checkin' },
      { label: '调宿退宿', to: TODO_TYPE_ROUTES.DORM_TRANSFER },
      { label: '房源管理', to: '/admin/student-affairs/dorm/resource' }
    ]
  },

  // ── T7 毕设导师 ──
  GD_MENTOR: {
    template: 'T7',
    label: '毕设导师工作台',
    headline: pendingHeadline('今日无待办，可查看指导学生进度'),
    summaryCues: SUMMARY_CUES,
    statsCues: [statsCue('pendingApproval', '待我审批', 'primary', TODO_ALL)],
    typeCues: GD_MENTOR_TYPE_CUES,
    quickLinks: [
      { label: '我指导的学生', to: '/admin/graduation/students' },
      { label: '开题材料', to: '/admin/graduation/proposals' },
      { label: '成果提交', to: '/admin/graduation/finals' },
      { label: '过程指导', to: '/admin/graduation/process?panel=guidance' }
    ]
  },

  // ── T8 毕设管理（校/院/专业管理员）：进度与卡壳学生入口真实 ──
  GRADUATION_ADMIN: {
    template: 'T8',
    label: '毕设管理工作台',
    headline: pendingHeadline('毕设管理今日无待办'),
    summaryCues: SUMMARY_CUES,
    statsCues: [
      statsCue('pendingApproval', '待我审批', 'primary', TODO_ALL),
      statsCue('studentTotal', '范围内学生', 'primary', '/admin/graduation/students?panel=roster')
    ],
    typeCues: GD_MENTOR_TYPE_CUES,
    quickLinks: [
      { label: '学生进度', to: '/admin/graduation/students?panel=progress' },
      { label: '未选题学生', to: '/admin/graduation/students?panel=topic' },
      { label: '问题预警', to: '/admin/graduation/risk-archive?panel=risk' },
      { label: '开题批阅', to: '/admin/graduation/proposals' },
      { label: '毕设统计', to: '/admin/graduation/stats-report' }
    ]
  },

  // ── T9a 评阅人：成果评阅真实待办类型 ──
  GD_REVIEWER: {
    template: 'T9',
    label: '毕设评阅工作台',
    headline: pendingHeadline('今日无待评阅'),
    summaryCues: SUMMARY_CUES,
    statsCues: [statsCue('pendingApproval', '待我审批', 'primary', TODO_ALL)],
    typeCues: [typeCue('GD_FINAL_REVIEW', '成果待评阅', 'warning')],
    quickLinks: [
      { label: '成果批阅', to: '/admin/graduation/finals' },
      { label: '教师评阅', to: '/admin/graduation/defense-grade?panel=review' },
      { label: '查重记录', to: '/admin/graduation/defense-grade?panel=plagiarism' }
    ]
  },

  // ── T9b 答辩秘书：答辩安排/发布真实入口；无假评阅数 ──
  GD_DEFENSE_SECRETARY: {
    template: 'T9',
    label: '答辩秘书工作台',
    headline: pendingHeadline('今日无答辩待办，可去安排或发布'),
    summaryCues: SUMMARY_CUES,
    statsCues: [statsCue('pendingApproval', '待我审批', 'primary', TODO_ALL)],
    typeCues: [],
    quickLinks: [
      { label: '答辩安排', to: '/admin/graduation/defense' },
      { label: '答辩评分', to: '/admin/graduation/defense-grade?panel=defense' },
      { label: '成绩评定', to: '/admin/graduation/defense-grade?panel=grade' },
      { label: '专家库', to: '/admin/graduation/more?panel=experts' }
    ]
  },

  // ── T9c 答辩专家：待打分写 UnifiedTodo(GD_DEFENSE_SCORE) ──
  GD_DEFENSE_EXPERT: {
    template: 'T9',
    label: '答辩专家工作台',
    headline: pendingHeadline('今日无待打分任务'),
    summaryCues: SUMMARY_CUES,
    statsCues: [],
    typeCues: [typeCue('GD_DEFENSE_SCORE', '答辩待打分', 'warning')],
    quickLinks: [
      { label: '答辩评分', to: TODO_TYPE_ROUTES.GD_DEFENSE_SCORE },
      { label: '答辩安排', to: '/admin/graduation/defense' }
    ]
  },

  // ── T10 实习导师 ──
  INTERN_MENTOR: {
    template: 'T10',
    label: '实习指导工作台',
    headline: pendingHeadline('今日无待办，可查看实习生与周报'),
    summaryCues: SUMMARY_CUES,
    statsCues: [statsCue('pendingApproval', '待我审批', 'primary', TODO_ALL)],
    typeCues: [
      typeCue('INTERN_WEEKLY_REVIEW', '周报待批', 'primary'),
      typeCue('INTERN_LEAVE_APPROVAL', '实习请假待审', 'warning'),
      typeCue('INTERN_EXCEPTION_HANDLE', '打卡异常待处置', 'risk'),
      typeCue('INTERN_VISIT_RECTIFY', '巡访整改待跟进', 'warning')
    ],
    quickLinks: [
      { label: '我的实习生', to: '/admin/internship/students' },
      { label: '周报审阅', to: '/admin/internship/reports' },
      { label: '巡访指导', to: '/admin/internship/guidance' },
      { label: '考勤请假', to: '/admin/internship/attendance' }
    ]
  },

  // ── T11 就业老师：未就业统计 + 分配后的跟进待办 ──
  EMPLOYMENT_TEACHER: {
    template: 'T11',
    label: '就业工作台',
    headline: statsFirstHeadline(
      'unemployed',
      (n) => `范围内有 ${n} 名学生未落实去向，建议跟进`,
      '今日无就业待办，可查看去向落实情况'
    ),
    summaryCues: SUMMARY_CUES,
    statsCues: [
      statsCue('unemployed', '未就业学生', 'warning', '/admin/employment/unemployed?status=UNEMPLOYED'),
      statsCue('studentTotal', '范围内学生', 'primary', '/admin/employment/students'),
      statsCue('pendingApproval', '待我审批', 'primary', `${TODO_ALL}?status=PENDING`)
    ],
    typeCues: [typeCue('EMPLOYMENT_FOLLOWUP', '就业跟进待办', 'warning')],
    quickLinks: [
      { label: '未就业帮扶', to: '/admin/employment/unemployed?status=UNEMPLOYED' },
      { label: '就业跟进', to: TODO_TYPE_ROUTES.EMPLOYMENT_FOLLOWUP },
      { label: '材料审核', to: '/admin/employment/materials?status=PENDING' },
      { label: '就业学生', to: '/admin/employment/students' },
      { label: '就业看板', to: '/admin/employment' }
    ]
  },

  // ── T12a 校/院领导：只读驾驶舱 + 范围内指标 ──
  LEADER: {
    template: 'T12',
    label: '领导驾驶工作台',
    headline: statsFirstHeadline(
      'studentTotal',
      (n) => `当前范围内在册学生 ${n} 人，可查看驾驶舱`,
      '今日无告警待办，可查看领导驾驶舱'
    ),
    summaryCues: SUMMARY_CUES,
    statsCues: SCHOOL_STATS,
    typeCues: [],
    quickLinks: [
      { label: '领导驾驶舱', to: COCKPIT },
      { label: '生命周期总览', to: '/admin/data-center/lifecycle' },
      { label: '风险预警', to: '/admin/data-center/risk' },
      { label: '排行分析', to: '/admin/data-center/rankings' }
    ]
  },

  // ── T12b 学校管理员 ──
  SCHOOL_ADMIN: {
    template: 'T12',
    label: '学校管理工作台',
    headline: pendingHeadline('今日无待办，可查看全校运行与驾驶舱'),
    summaryCues: SUMMARY_CUES,
    statsCues: SCHOOL_STATS,
    typeCues: [],
    quickLinks: [
      { label: '领导驾驶舱', to: COCKPIT },
      { label: '系统管理', to: SYSTEM_HOME },
      { label: '安全审计', to: AUDIT_LOGS },
      { label: '全部待办', to: TODO_ALL },
      { label: '学工看板', to: '/admin/student-affairs' }
    ]
  },

  // ── T12c 系统管理员 ──
  SYS_ADMIN: {
    template: 'T12',
    label: '系统管理工作台',
    headline: pendingHeadline('今日无系统待办，可去查看审计与配置'),
    summaryCues: SUMMARY_CUES,
    statsCues: [statsCue('pendingApproval', '待我审批', 'primary', TODO_ALL)],
    typeCues: [],
    quickLinks: [
      { label: '系统管理', to: SYSTEM_HOME },
      { label: '安全审计', to: AUDIT_LOGS },
      { label: '全部待办', to: TODO_ALL }
    ]
  },

  // ── T12d 安全审计 ──
  SECURITY_AUDITOR: {
    template: 'T12',
    label: '安全审计工作台',
    headline: pendingHeadline('今日无审计待办，可去审查日志与驾驶舱'),
    summaryCues: SUMMARY_CUES,
    statsCues: [
      statsCue('pendingApproval', '待我审批', 'primary', TODO_ALL),
      statsCue('studentTotal', '在册学生', 'primary', COCKPIT)
    ],
    typeCues: [],
    quickLinks: [
      { label: '安全审计', to: AUDIT_LOGS },
      { label: '领导驾驶舱', to: COCKPIT },
      { label: '风险预警', to: '/admin/data-center/risk' },
      { label: '实习风险', to: '/admin/internship/risks' }
    ]
  },

  // ── T12e 组织人事：辅导员考评 ──
  ORG_PERSONNEL: {
    template: 'T12',
    label: '组织人事工作台',
    headline: pendingHeadline('今日无考评待办，可去组织辅导员考评'),
    summaryCues: SUMMARY_CUES,
    statsCues: [statsCue('pendingApproval', '待我审批', 'primary', TODO_ALL)],
    typeCues: [],
    quickLinks: [
      { label: '辅导员考评', to: '/admin/student-affairs/counselor-eval' },
      { label: '学工看板', to: '/admin/student-affairs' },
      { label: '全部待办', to: TODO_ALL }
    ]
  },

  // ── 兜底 ──
  DEFAULT: {
    template: 'DEFAULT',
    label: '我的工作台',
    headline: pendingHeadline('今日无待办，一切正常'),
    summaryCues: SUMMARY_CUES,
    statsCues: [statsCue('pendingApproval', '待我审批', 'primary', TODO_ALL)],
    typeCues: [],
    quickLinks: [{ label: '全部待办', to: TODO_ALL }]
  }
}

/** 同模板多角色别名（不复制页面，只复用配方对象） */
const RECIPE_ALIASES = {
  STUDENT_AFFAIRS: 'STUDENT_AFFAIRS_ADMIN',
  GD_COLLEGE_ADMIN: 'GRADUATION_ADMIN',
  GD_MAJOR_ADMIN: 'GRADUATION_ADMIN'
}

/** 以后端 /todos/summary.role 为准；未登记角色一律 DEFAULT。 */
export function resolveRecipe(roleCode) {
  const code = String(roleCode || '').toUpperCase()
  if (!code || code === 'PLATFORM_SUPER_ADMIN') return RECIPES.DEFAULT
  const aliased = RECIPE_ALIASES[code] || code
  return RECIPES[aliased] || RECIPES.DEFAULT
}

/** 测试/审计用：十二模板是否都有至少一个真实角色落点 */
export const TEMPLATE_ROLE_COVERAGE = {
  T1: ['ACADEMIC_TEACHER'],
  T2: ['ACADEMIC_ADMIN'],
  T3: ['COLLEGE_ADMIN'],
  T4: ['COUNSELOR'],
  T5: ['STUDENT_AFFAIRS_ADMIN', 'STUDENT_AFFAIRS'],
  T6: ['PSYCHOLOGY_TEACHER', 'FUNDING_TEACHER', 'YOUTH_LEAGUE', 'DORM_MANAGER'],
  T7: ['GD_MENTOR'],
  T8: ['GRADUATION_ADMIN', 'GD_COLLEGE_ADMIN', 'GD_MAJOR_ADMIN'],
  T9: ['GD_REVIEWER', 'GD_DEFENSE_SECRETARY', 'GD_DEFENSE_EXPERT'],
  T10: ['INTERN_MENTOR'],
  T11: ['EMPLOYMENT_TEACHER'],
  T12: ['LEADER', 'SCHOOL_ADMIN', 'SYS_ADMIN', 'SECURITY_AUDITOR', 'ORG_PERSONNEL']
}
