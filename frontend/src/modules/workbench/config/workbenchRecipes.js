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
 *   'message.unread'  → GET /admin/messages/count
 * /stats/workbench 已在 P3 按数据范围收敛；T4 样板仍以 summary/todoType 为主，
 * 避免与待办磁贴重复。校级配方（P4/T12）可再接入该接口的学生/预警等字段。
 *
 * 当前仅落地 T4 辅导员 + DEFAULT 兜底；T1/T2/T7/T10 等属 P4，禁止在此堆未验证假磁贴。
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
  AA_SCHEDULE_CHANGE_APPROVAL: '/admin/academic-affairs/schedule-change/approval'
}

const TODO_ALL = '/admin/approval/todos'

/** 通用汇总磁贴：任何角色都适用（数据均为本人可见范围） */
const SUMMARY_CUES = [
  { key: 'pending', title: '待我处理', source: 'summary.pending', accent: 'primary', to: TODO_ALL },
  { key: 'overdue', title: '已逾期', source: 'summary.overdue', accent: 'risk', to: TODO_ALL },
  { key: 'nearDeadline', title: '24小时内到期', source: 'summary.nearDeadline', accent: 'warning', to: TODO_ALL },
  { key: 'doneToday', title: '今日已完成', source: 'summary.doneToday', accent: 'success', to: TODO_ALL }
]

function typeCue(key, title, accent) {
  return { key, title, source: `todoType.${key}`, accent, to: TODO_TYPE_ROUTES[key] || TODO_ALL }
}

export const RECIPES = {
  // ── T4 辅导员：待办数据在本系统中最完整（请假/违纪/资助/困难认定/风险五类真实写入）──
  COUNSELOR: {
    label: '辅导员工作台',
    headline: (d) => {
      if (d.summary.overdue > 0) return `有 ${d.summary.overdue} 项已逾期，建议先处理`
      if (d.summary.pending > 0) return `今天有 ${d.summary.pending} 项待你处理`
      return '今日无待办，一切正常'
    },
    summaryCues: SUMMARY_CUES,
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

  // ── 兜底：不臆造角色专属卡片，只给通用待办与全部待办入口 ──
  DEFAULT: {
    label: '我的工作台',
    headline: (d) => (d.summary.pending > 0
      ? `今天有 ${d.summary.pending} 项待你处理`
      : '今日无待办，一切正常'),
    summaryCues: SUMMARY_CUES,
    typeCues: [],
    quickLinks: [{ label: '全部待办', to: TODO_ALL }]
  }
}

/** 以后端 /todos/summary.role 为准；未登记角色一律 DEFAULT，不前端猜测业务配方。 */
export function resolveRecipe(roleCode) {
  return RECIPES[(roleCode || '').toUpperCase()] || RECIPES.DEFAULT
}
