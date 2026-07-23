/**
 * 工作台「角色配方」——一个外壳 + 可复用积木 + 每个角色一份积木清单。
 *
 * 设计对标 Microsoft Dynamics 365 Role Center：
 *   - 每个角色一个首页（profile ↔ role center），不是一个首页加过滤器；
 *   - 内容顺序固定 Headline（先给结论）→ Cues（可点击的数字磁贴）→ 明细；
 *   - 数字磁贴必须能下钻到「已筛选好的业务列表」，点不动的数字等于没做。
 *
 * 后端 27 个角色（app/core/permissions.py ROLE_PERMISSIONS）收敛为若干模板；
 * 未登记的角色回落 DEFAULT（只给通用待办，不臆造该角色的业务卡片）。
 *
 * cue.source 取数来源：
 *   'summary.<字段>'  → GET /todos/summary（本人可见范围）
 *   'todoType.<类型>' → GET /admin/todos/count 的 byType（本人可见范围）
 *   'stats.<字段>'    → GET /stats/workbench（按数据范围收敛的关键指标 B2/B4）
 *   'message.unread'  → GET /admin/messages/count
 *
 * 积木：
 *   B2 待我审批 → stats.pendingApproval
 *   B4 关键指标 → stats.studentTotal / academicWarning / orientationPending 等
 *   B5 临近截止 → SUMMARY_CUES.nearDeadline（24h 内到期，下钻全部待办）
 *   B8 我的课表 → quickLinks「我的课表」→ /admin/academic-affairs/schedule/teacher
 *
 * 已落地：T4 辅导员、T1 任课教师、T2 教务老师、T7 毕设导师、T10 实习导师 + DEFAULT。
 * T7/T10 业务待办由 P5 写入 UnifiedTodo（开题/成果/选题变更；周报/请假/异常/巡访整改）。
 */

/** 待办类型 → 该类型的业务落点（点磁贴要能到已筛选的列表，不能落到空白模块首页） */
export const TODO_TYPE_ROUTES = {
  LEAVE_APPROVAL: '/admin/campus-service/leave',
  LEAVE_OVERDUE: '/admin/campus-service/leave-ledger',
  DISCIPLINE_APPROVAL: '/admin/student-affairs/discipline',
  AID_APPROVAL: '/admin/student-affairs/aid',
  FUNDING_APPROVAL: '/admin/student-affairs/funding',
  RISK_HANDLE: '/admin/student-affairs/risk',
  // 异动/调停课审批落审批工作台，不是台账首页（避免「点待审却进列表」）
  AA_STATUS_APPROVAL: '/admin/academic-affairs/status-changes/approval',
  AA_SCHEDULE_CHANGE_APPROVAL: '/admin/academic-affairs/schedule-change/approval',
  ACAD_WARNING_HANDLE: '/admin/academic-affairs/warnings',
  GD_PROPOSAL_REVIEW: '/admin/graduation/proposals',
  GD_FINAL_REVIEW: '/admin/graduation/finals',
  GD_TOPIC_CHANGE_REVIEW: '/admin/graduation/topic-changes',
  INTERN_WEEKLY_REVIEW: '/admin/internship/reports',
  INTERN_LEAVE_APPROVAL: '/admin/internship/leaves',
  INTERN_EXCEPTION_HANDLE: '/admin/internship/exceptions',
  INTERN_VISIT_RECTIFY: '/admin/internship/guidance'
}

const TODO_ALL = '/admin/approval/todos'
/** B8：教师课表页（本人可用「查看本人课表」；不深链工号，避免前端猜身份键） */
const MY_SCHEDULE = '/admin/academic-affairs/schedule/teacher'

/** 通用汇总磁贴：任何角色都适用（含 B5 临近截止；数据均为本人可见范围） */
const SUMMARY_CUES = [
  { key: 'pending', title: '待我处理', source: 'summary.pending', accent: 'primary', to: TODO_ALL },
  { key: 'overdue', title: '已逾期', source: 'summary.overdue', accent: 'risk', to: TODO_ALL },
  { key: 'nearDeadline', title: '24小时内到期', source: 'summary.nearDeadline', accent: 'warning', to: TODO_ALL },
  { key: 'doneToday', title: '今日已完成', source: 'summary.doneToday', accent: 'success', to: TODO_ALL }
]

function typeCue(key, title, accent) {
  return { key, title, source: `todoType.${key}`, accent, to: TODO_TYPE_ROUTES[key] || TODO_ALL }
}

/** B2/B4：来自 /stats/workbench，数字按当前身份数据范围收敛 */
function statsCue(key, title, accent, to) {
  return { key, title, source: `stats.${key}`, accent, to }
}

function pendingHeadline(labelWhenEmpty) {
  return (d) => {
    if (d.summary.overdue > 0) return `有 ${d.summary.overdue} 项已逾期，建议先处理`
    if (d.summary.nearDeadline > 0) return `有 ${d.summary.nearDeadline} 项将在 24 小时内到期`
    if (d.summary.pending > 0) return `今天有 ${d.summary.pending} 项待你处理`
    return labelWhenEmpty
  }
}

/** 辅导员范围关键指标（B2 待我审批 + B4 学生/预警/迎新） */
const COUNSELOR_STATS_CUES = [
  statsCue('pendingApproval', '待我审批', 'primary', TODO_ALL),
  statsCue('studentTotal', '我的学生', 'primary', '/admin/campus-service/classes'),
  statsCue('academicWarning', '学业预警在办', 'warning', '/admin/academic-affairs/warnings'),
  statsCue('orientationPending', '迎新待报到', 'primary', '/admin/orientation/students')
]

export const RECIPES = {
  // ── T4 辅导员：待办数据在本系统中最完整（请假/违纪/资助/困难认定/风险五类真实写入）──
  COUNSELOR: {
    label: '辅导员工作台',
    headline: pendingHeadline('今日无待办，一切正常'),
    summaryCues: SUMMARY_CUES,
    statsCues: COUNSELOR_STATS_CUES,
    typeCues: [
      typeCue('LEAVE_APPROVAL', '待批请假', 'primary'),
      typeCue('RISK_HANDLE', '风险待处置', 'risk'),
      typeCue('DISCIPLINE_APPROVAL', '违纪待处理', 'warning'),
      typeCue('AID_APPROVAL', '困难认定待审', 'primary'),
      typeCue('FUNDING_APPROVAL', '资助待审', 'primary'),
      typeCue('LEAVE_OVERDUE', '逾期未销假', 'risk')
    ],
    quickLinks: [
      { label: '我的班级', to: '/admin/campus-service/classes' },
      { label: '谈心谈话', to: '/admin/student-affairs/talk' },
      { label: '风险台账', to: '/admin/student-affairs/risk' }
    ]
  },

  // ── T1 任课教师：成绩/课表/调停课入口真实；成绩待办尚未写 UnifiedTodo，故无分类假磁贴 ──
  ACADEMIC_TEACHER: {
    label: '任课教师工作台',
    headline: pendingHeadline('今日无待办，可去录入成绩或查看课表'),
    summaryCues: SUMMARY_CUES,
    statsCues: [],
    typeCues: [],
    quickLinks: [
      { label: '成绩录入', to: '/admin/academic-affairs/grade-entry' },
      { label: '我的课表', to: MY_SCHEDULE },
      { label: '发起调停课', to: '/admin/academic-affairs/schedule-change/apply' }
    ]
  },

  // ── T2 教务老师：异动/调停课/学业预警待办真实写入；课表为查询入口（B8）──
  ACADEMIC_ADMIN: {
    label: '教务工作台',
    headline: pendingHeadline('今日无待办，一切正常'),
    summaryCues: SUMMARY_CUES,
    statsCues: [
      statsCue('pendingApproval', '待我审批', 'primary', TODO_ALL),
      statsCue('academicWarning', '学业预警在办', 'warning', '/admin/academic-affairs/warnings'),
      statsCue('studentTotal', '范围内学生', 'primary', '/admin/academic-affairs/roster')
    ],
    typeCues: [
      typeCue('AA_STATUS_APPROVAL', '学籍异动待审', 'warning'),
      typeCue('AA_SCHEDULE_CHANGE_APPROVAL', '调停课待审', 'primary'),
      typeCue('ACAD_WARNING_HANDLE', '学业预警待处置', 'risk')
    ],
    quickLinks: [
      { label: '异动审批', to: TODO_TYPE_ROUTES.AA_STATUS_APPROVAL },
      { label: '调停课审批', to: TODO_TYPE_ROUTES.AA_SCHEDULE_CHANGE_APPROVAL },
      { label: '我的课表', to: MY_SCHEDULE },
      { label: '学业预警', to: TODO_TYPE_ROUTES.ACAD_WARNING_HANDLE }
    ]
  },

  // ── T7 毕设导师：开题/成果/选题变更写入 UnifiedTodo（P5）──
  GD_MENTOR: {
    label: '毕设导师工作台',
    headline: pendingHeadline('今日无待办，可查看指导学生进度'),
    summaryCues: SUMMARY_CUES,
    statsCues: [statsCue('pendingApproval', '待我审批', 'primary', TODO_ALL)],
    typeCues: [
      typeCue('GD_PROPOSAL_REVIEW', '开题待批阅', 'primary'),
      typeCue('GD_FINAL_REVIEW', '成果待批阅', 'warning'),
      typeCue('GD_TOPIC_CHANGE_REVIEW', '选题变更待审', 'primary')
    ],
    quickLinks: [
      { label: '我指导的学生', to: '/admin/graduation/students' },
      { label: '开题材料', to: '/admin/graduation/proposals' },
      { label: '成果提交', to: '/admin/graduation/finals' }
    ]
  },

  // ── T10 实习导师：周报/请假/异常/巡访整改写入 UnifiedTodo（P5）──
  INTERN_MENTOR: {
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

  // ── 兜底：不臆造角色专属卡片，只给通用待办与全部待办入口 ──
  DEFAULT: {
    label: '我的工作台',
    headline: pendingHeadline('今日无待办，一切正常'),
    summaryCues: SUMMARY_CUES,
    statsCues: [statsCue('pendingApproval', '待我审批', 'primary', TODO_ALL)],
    typeCues: [],
    quickLinks: [{ label: '全部待办', to: TODO_ALL }]
  }
}

/** 以后端 /todos/summary.role 为准；未登记角色一律 DEFAULT，不前端猜测业务配方。 */
export function resolveRecipe(roleCode) {
  return RECIPES[(roleCode || '').toUpperCase()] || RECIPES.DEFAULT
}
