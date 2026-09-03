/**
 * 学工中心 V6 工作区投影。
 *
 * 说明：
 * - 这是教师 PC 的二级工作区 / 三级页面投影，不替代 navPlan 的完整能力事实目录；
 * - 所有 path 均为仓库已有 route，permissionAny 仅用于前端可见性，后端仍是最终边界；
 * - 详情、兼容页、消息深链和对象下钻不直接铺满侧栏。
 */
const leaf = (id, label, path, permissionAny, kind = '页面') => ({
  id,
  label,
  path,
  permissionAny: Array.isArray(permissionAny) ? permissionAny : [permissionAny].filter(Boolean),
  kind
})

const group = (id, label, leaves) => ({ id, label, leaves })

const STUDENT_VIEW = ['student.profile.view', 'studentAffairs.student.view']
const STATUS_CHANGE_VIEW = [
  'academicAffairs.statusChange.view',
  'academicAffairs.statusChange.counselorReview',
  'academicAffairs.statusChange.collegeReview',
  'academicAffairs.statusChange.officeReview'
]
const CORRECTION_VIEW = [
  'academicAffairs.roster.correction.view',
  'academicAffairs.roster.correction.review'
]

export const STUDENT_AFFAIRS_WORKSPACE_META = Object.freeze({
  workspaceCount: 12,
  formalPageCount: 92,
  allNodeCount: 102
})

export const STUDENT_AFFAIRS_WORKSPACES = Object.freeze([
  {
    id: 'today',
    no: '01',
    title: '今日工作',
    subtitle: '今日队列、材料缺项与审计',
    wave: '第一波 · 高频主线',
    routePrefixes: ['/admin/student-affairs/dashboard', '/admin/student-affairs/material-operations'],
    groups: [
      group('today-current', '当前工作', [
        leaf('today-main', '角色化今日工作', '/admin/student-affairs/dashboard', 'studentAffairs.dashboard.view', '角色首页'),
        leaf('today-queues', '业务队列总览', '/admin/student-affairs/dashboard#work-queue', 'studentAffairs.dashboard.view', '内部投影')
      ]),
      group('today-support', '支撑动作', [
        leaf('today-audit', '最近处理与审计', '/admin/student-affairs/dashboard#audit', 'studentAffairs.dashboard.view', '内部页签')
      ])
    ]
  },
  {
    id: 'student',
    no: '02',
    title: '唯一学生360',
    subtitle: '学生、班级、身份与数据治理',
    wave: '第一波 · 高频主线',
    routePrefixes: [
      '/admin/student',
      '/admin/campus-service/classes',
      '/admin/student-affairs/profile',
      '/admin/student-affairs/counselor-assignments',
      '/admin/student-affairs/counselor-eval'
    ],
    groups: [
      group('student-object', '学生对象', [
        leaf('student-list', '学生主档列表', '/admin/student/list', STUDENT_VIEW, '主列表')
      ]),
      group('student-class', '班级与责任', [
        leaf('class-list', '班级列表', '/admin/campus-service/classes', 'campus.record.view', '工作区页签'),
        leaf('counselor-assign', '辅导员责任台账', '/admin/student-affairs/counselor-assignments', 'studentAffairs.class.view', '管理专属'),
        leaf('counselor-eval', '辅导员考评', '/admin/student-affairs/counselor-eval', 'studentAffairs.counselorEval.view', '管理专属')
      ]),
      group('student-governance', '数据治理', [
        leaf('student-status', '学籍异动台账', '/admin/student/status', STATUS_CHANGE_VIEW, '只读投影'),
        leaf('student-identity', '身份核验能力与记录', '/admin/student/identity', STUDENT_VIEW, '能力闸门'),
        leaf('student-corrections', '信息更正审核', '/admin/student/corrections', CORRECTION_VIEW, '连续审核'),
        leaf('student-risk-tags', '人工风险标签', '/admin/student/risk-tags', 'studentAffairs.risk.view', '内部支撑'),
        leaf('student-import', '学生导入分流', '/admin/student/import', STUDENT_VIEW, '搜索入口'),
        leaf('student-export', '学生数据导出', '/admin/student/import-export', 'student.export', '支撑页')
      ])
    ]
  },
  {
    id: 'risk',
    no: '03',
    title: '风险与重点学生',
    subtitle: '风险队列、快捷筛选与处置详情',
    wave: '第一波 · 高频主线',
    routePrefixes: ['/admin/student-affairs/risk'],
    groups: [
      group('risk-queue', '风险队列', [
        leaf('risk-list', '风险记录工作台', '/admin/student-affairs/risk', 'studentAffairs.risk.view', '主工作台'),
        leaf('risk-priority', '高危优先队列', '/admin/student-affairs/risk?priority=HIGH', 'studentAffairs.risk.view', '快捷队列'),
        leaf('risk-overdue', '超时待跟进', '/admin/student-affairs/risk?overdueOnly=true&ownerId=me', 'studentAffairs.risk.view', '快捷队列'),
        leaf('risk-unassigned', '未分派风险池', '/admin/student-affairs/risk?unassignedOnly=true', 'studentAffairs.risk.view', '快捷队列')
      ])
    ]
  },
  {
    id: 'talk',
    no: '04',
    title: '谈心家校与回访',
    subtitle: '谈话、家校、回执、台账与统计',
    wave: '第一波 · 高频主线',
    routePrefixes: ['/admin/student-affairs/talk', '/admin/student-affairs/family'],
    groups: [
      group('talk-follow', '谈话与回访', [
        leaf('talk-main', '谈心谈话工作台', '/admin/student-affairs/talk', 'studentAffairs.talk.view', '主工作台'),
        leaf('talk-key-follow', '重点学生跟进', '/admin/student-affairs/talk/key-follow', 'studentAffairs.talk.view', '辅助聚合')
      ]),
      group('talk-family', '家校协同', [
        leaf('family-contact', '家校联系', '/admin/student-affairs/family', 'studentAffairs.homeSchool.view', '内部流程'),
        leaf('family-receipts', '家校回执队列', '/admin/student-affairs/family/receipts', 'studentAffairs.homeSchool.view', '队列页签')
      ]),
      group('talk-ledger', '台账统计', [
        leaf('talk-ledger', '谈话台账', '/admin/student-affairs/talk/ledger', 'studentAffairs.talk.view', '历史台账'),
        leaf('talk-stats', '谈话统计', '/admin/student-affairs/talk/stats', 'studentAffairs.talk.view', '统计页签')
      ])
    ]
  },
  {
    id: 'leave',
    no: '05',
    title: '请假与返校',
    subtitle: '审批、续假、销假、返校与超期',
    wave: '第二波 · 业务闭环',
    routePrefixes: ['/admin/student-affairs/leave'],
    groups: [
      group('leave-current', '当前办理', [
        leaf('leave-approval', '请假审批工作台', '/admin/student-affairs/leave', 'studentAffairs.leave.view', '主工作台'),
        leaf('leave-followup', '销假、续假与逾期', '/admin/student-affairs/leave/followup', 'studentAffairs.leave.view', '生命周期')
      ]),
      group('leave-ledger', '台账统计', [
        leaf('leave-ledger', '请假台账', '/admin/student-affairs/leave/ledger', 'studentAffairs.leave.view', '历史台账'),
        leaf('leave-stats', '请假统计', '/admin/student-affairs/leave/stats', 'studentAffairs.leave.view', '管理统计')
      ])
    ]
  },
  {
    id: 'aid',
    no: '06',
    title: '困难与资助',
    subtitle: '困难认定、奖助评审、公示、发放与专项',
    wave: '第二波 · 业务闭环',
    routePrefixes: ['/admin/student-affairs/aid', '/admin/student-affairs/funding'],
    groups: [
      group('aid-review', '困难认定', [
        leaf('aid-review', '困难认定审核', '/admin/student-affairs/aid', 'studentAffairs.aid.view', '主工作台'),
        leaf('aid-batches', '认定批次', '/admin/student-affairs/aid/batches', 'studentAffairs.aid.view', '低频配置'),
        leaf('aid-library', '困难学生库', '/admin/student-affairs/aid/difficult-students', 'studentAffairs.aid.view', '事实库'),
        leaf('aid-publicity', '认定公示', '/admin/student-affairs/aid/publicity', 'studentAffairs.aid.view', '阶段页签'),
        leaf('aid-objections', '认定异议复核', '/admin/student-affairs/aid/objections', 'studentAffairs.aid.view', '阶段页签'),
        leaf('aid-ledger', '认定台账', '/admin/student-affairs/aid/ledger', 'studentAffairs.aid.view', '历史台账'),
        leaf('aid-stats', '认定统计', '/admin/student-affairs/aid/stats', 'studentAffairs.stats.view', '统计页签')
      ]),
      group('funding-review', '奖助评审', [
        leaf('funding-review', '奖助申请评审', '/admin/student-affairs/funding', 'studentAffairs.funding.view', '主工作台'),
        leaf('funding-projects', '资助项目', '/admin/student-affairs/funding/projects', 'studentAffairs.funding.view', '低频配置'),
        leaf('funding-batches', '资助批次', '/admin/student-affairs/funding/batches', 'studentAffairs.funding.view', '低频配置'),
        leaf('funding-publicity', '资助公示', '/admin/student-affairs/funding/publicity', 'studentAffairs.funding.view', '阶段页签'),
        leaf('funding-appeals', '资助公示申诉', '/admin/student-affairs/funding/appeals', 'studentAffairs.funding.view', '阶段页签')
      ]),
      group('funding-special', '发放与专项', [
        leaf('funding-disbursement', '资助发放', '/admin/student-affairs/funding/disbursements', 'studentAffairs.funding.view', '下游主流程'),
        leaf('funding-ledger', '资助台账', '/admin/student-affairs/funding/ledger', 'studentAffairs.funding.view', '历史台账'),
        leaf('funding-stats', '资助统计', '/admin/student-affairs/funding/stats', 'studentAffairs.stats.view', '统计页签'),
        leaf('work-study', '勤工助学', '/admin/student-affairs/funding/work-study', 'studentAffairs.funding.workstudy.manage', '专项流程'),
        leaf('student-loans', '助学贷款', '/admin/student-affairs/funding/loans', 'studentAffairs.funding.loan.manage', '专项流程'),
        leaf('fee-reduction', '减免与临时补助', '/admin/student-affairs/funding/fee-reductions', 'studentAffairs.funding.reduction.manage', '专项流程')
      ])
    ]
  },
  {
    id: 'discipline',
    no: '07',
    title: '违纪处分与教育',
    subtitle: '处分、送达、申诉、教育与解除',
    wave: '第二波 · 业务闭环',
    routePrefixes: ['/admin/student-affairs/discipline'],
    groups: [
      group('discipline-flow', '处分流程', [
        leaf('discipline-main', '处分工作台', '/admin/student-affairs/discipline', 'studentAffairs.discipline.view', '主工作台'),
        leaf('discipline-appeals', '送达与申诉', '/admin/student-affairs/discipline/appeals', 'studentAffairs.discipline.view', '阶段页签')
      ]),
      group('discipline-ledger', '台账统计', [
        leaf('discipline-ledger', '违纪处分台账', '/admin/student-affairs/discipline/ledger', 'studentAffairs.discipline.view', '历史台账'),
        leaf('discipline-stats', '处分统计', '/admin/student-affairs/discipline/stats', 'studentAffairs.stats.view', '统计页签')
      ])
    ]
  },
  {
    id: 'dorm',
    no: '08',
    title: '宿舍与公寓',
    subtitle: '楼栋、房间、床位、入住、检查与异常',
    wave: '第二波 · 业务闭环',
    routePrefixes: ['/admin/student-affairs/dormitory', '/admin/student-affairs/dorm'],
    groups: [
      group('dorm-overview', '总览', [
        leaf('dorm-overview', '宿舍首页', '/admin/student-affairs/dormitory', 'studentAffairs.dorm.view', '域首页')
      ]),
      group('dorm-resource', '资源与分配', [
        leaf('dorm-resource', '房源管理', '/admin/student-affairs/dorm/resource', 'studentAffairs.dorm.view', '资源下钻'),
        leaf('dorm-allocation', '住宿分配计划', '/admin/student-affairs/dorm/allocation', 'studentAffairs.dorm.view', '配置执行')
      ]),
      group('dorm-checkin', '入住与调整', [
        leaf('dorm-checkin', '入住与退宿', '/admin/student-affairs/dorm/checkin', 'studentAffairs.dorm.view', '办理工作台'),
        leaf('dorm-transfer', '调宿与退宿审批', '/admin/student-affairs/dorm/transfer', 'studentAffairs.dorm.view', '连续审批')
      ]),
      group('dorm-quality', '检查与异常', [
        leaf('dorm-check', '宿舍检查与整改', '/admin/student-affairs/dorm/check', 'studentAffairs.dorm.view', '质量闭环'),
        leaf('dorm-exception', '宿舍异常', '/admin/student-affairs/dorm/exception', 'studentAffairs.dorm.view', '优先队列'),
        leaf('dorm-stats', '宿舍统计', '/admin/student-affairs/dorm/stats', 'studentAffairs.dorm.view', '统计页签')
      ])
    ]
  },
  {
    id: 'growth',
    no: '09',
    title: '活动与成长',
    subtitle: '活动事实、第二课堂、志愿、组织与成长',
    wave: '第三波 · 成长与专项',
    routePrefixes: ['/admin/student-affairs/activity'],
    groups: [
      group('growth-operation', '活动运营', [
        leaf('growth-activity', '活动运营工作台', '/admin/student-affairs/activity', 'studentAffairs.activity.view', '主工作台')
      ]),
      group('growth-result', '成长成果', [
        leaf('growth-second-class', '第二课堂正式台账', '/admin/student-affairs/activity/second-class', 'studentAffairs.activity.view', '成果台账'),
        leaf('growth-credit-appeals', '第二课堂积分申诉', '/admin/student-affairs/activity/credit-appeals', 'studentAffairs.activity.view', '纠错队列'),
        leaf('growth-volunteer', '志愿服务认定', '/admin/student-affairs/activity/volunteer', 'studentAffairs.activity.view', '成果认定')
      ]),
      group('growth-org', '社团与组织', [
        leaf('growth-clubs', '社团管理', '/admin/student-affairs/activity/clubs', 'studentAffairs.club.view', '组织工作台'),
        leaf('growth-organizations', '学生干部与组织', '/admin/student-affairs/activity/organizations', 'studentAffairs.org.view', '组织工作台')
      ]),
      group('growth-special', '专项发展', [
        leaf('growth-party-league', '党团发展', '/admin/student-affairs/activity/party-league', 'studentAffairs.league.view', '专项工作台')
      ]),
      group('growth-stats', '统计支撑', [
        leaf('growth-stats', '活动与成长统计', '/admin/student-affairs/activity/stats', 'studentAffairs.stats.view', '聚合统计')
      ])
    ]
  },
  {
    id: 'orientation',
    no: '10',
    title: '数字迎新',
    subtitle: '按批次与六个阶段组织现有业务页面',
    wave: '第三波 · 成长与专项',
    routePrefixes: ['/admin/orientation'],
    groups: [
      group('orientation-overview', '总览', [
        leaf('orientation-dashboard', '数字迎新管理看板', '/admin/orientation', 'studentAffairs.orientation.view', '阶段总览')
      ]),
      group('orientation-stage-1', '阶段1 · 批次与规则', [
        leaf('orientation-batches', '迎新批次', '/admin/orientation/batches', 'studentAffairs.orientation.view', '配置工作台'),
        leaf('orientation-flow', '报到流程配置', '/admin/orientation/flow-config', 'studentAffairs.orientation.view', '流程配置'),
        leaf('orientation-points', '现场报到点', '/admin/orientation/checkin-points', 'studentAffairs.orientation.view', '现场配置')
      ]),
      group('orientation-stage-2', '阶段2 · 新生底账', [
        leaf('orientation-data', '录取新生底账', '/admin/orientation/data', 'studentAffairs.orientation.view', '只读底账'),
        leaf('orientation-verify', '新生信息核验', '/admin/orientation/verify', 'studentAffairs.orientation.view', '连续核验'),
        leaf('orientation-students', '新生报到学生列表', '/admin/orientation/students', 'studentAffairs.orientation.view', '主列表')
      ]),
      group('orientation-stage-3', '阶段3 · 报到资格', [
        leaf('orientation-qualification', '报到资格', '/admin/orientation/qualification', 'studentAffairs.orientation.view', '关键闸门')
      ]),
      group('orientation-stage-4', '阶段4 · 报到办理', [
        leaf('orientation-progress', '报到进度跟踪', '/admin/orientation/progress', 'studentAffairs.orientation.view', '办理队列'),
        leaf('orientation-payment', '缴费与绿色通道', '/admin/orientation/payment', 'studentAffairs.orientation.view', '办理工作台'),
        leaf('orientation-materials', '迎新材料审核', '/admin/orientation/materials', 'studentAffairs.orientation.view', '材料队列'),
        leaf('orientation-dorm-preassign', '宿舍预分配', '/admin/orientation/dorm-preassign', 'studentAffairs.orientation.view', '阶段办理'),
        leaf('orientation-dorm', '宿舍入住确认', '/admin/orientation/dorm', 'studentAffairs.orientation.view', '入住队列')
      ]),
      group('orientation-stage-5', '阶段5 · 异常闭环', [
        leaf('orientation-exceptions', '迎新异常学生', '/admin/orientation/exceptions', 'studentAffairs.orientation.view', '异常闭环'),
        leaf('orientation-no-show', '未报到学生', '/admin/orientation/no-show', 'studentAffairs.orientation.view', '专项队列')
      ]),
      group('orientation-support', '支撑能力', [
        leaf('orientation-notices', '迎新通知', '/admin/orientation/notices', 'studentAffairs.orientation.view', '通知支撑')
      ]),
      group('orientation-stage-6', '阶段6 · 统计归档', [
        leaf('orientation-stats', '迎新统计', '/admin/orientation/statistics', 'studentAffairs.orientation.view', '聚合统计'),
        leaf('orientation-archive', '迎新归档', '/admin/orientation/archive', 'studentAffairs.orientation.view', '归档工作台')
      ])
    ]
  },
  {
    id: 'mental',
    no: '11',
    title: '心理专项',
    subtitle: '必要摘要、逐生授权、转介、回访与危机升级',
    wave: '第三波 · 成长与专项',
    routePrefixes: ['/admin/student-affairs/mental'],
    groups: [
      group('mental-summary', '必要摘要', [
        leaf('mental-summary', '心理预警必要摘要', '/admin/student-affairs/mental/summary', 'studentAffairs.risk.view', '普通角色摘要')
      ]),
      group('mental-special', '专项处置', [
        leaf('mental-attention', '专项关注名单', '/admin/student-affairs/mental', 'studentAffairs.risk.psyDetail.view', '专项主工作台'),
        leaf('mental-referrals', '转介与回访', '/admin/student-affairs/mental/referrals', 'studentAffairs.risk.psyDetail.view', '专项闭环')
      ]),
      group('mental-crisis', '危机升级', [
        leaf('mental-crisis', '心理危机升级', '/admin/student-affairs/mental/crisis', 'studentAffairs.risk.psyDetail.view', '危机动作')
      ]),
      group('mental-stats', '统计支撑', [
        leaf('mental-stats', '心理专项聚合统计', '/admin/student-affairs/mental/stats', 'studentAffairs.stats.view', '专项统计')
      ])
    ]
  },
  {
    id: 'stats',
    no: '12',
    title: '统计与档案',
    subtitle: '统计健康、业务下钻与正式归档',
    wave: '第三波 · 成长与专项',
    routePrefixes: ['/admin/student-affairs/stats', '/admin/student-affairs/archive'],
    groups: [
      group('stats-cockpit', '统计驾驶', [
        leaf('stats-overview', '学工统计入口', '/admin/student-affairs/stats', 'studentAffairs.stats.view', '兼容包装'),
        leaf('stats-cockpit', '统计驾驶舱', '/admin/student-affairs/stats/cockpit', 'studentAffairs.stats.view', '管理驾驶舱'),
        leaf('stats-audit', '统计口径与审计', '/admin/student-affairs/stats/cockpit#audit', 'studentAffairs.stats.view', '内部页签')
      ]),
      group('stats-archive', '正式归档', [
        leaf('stats-archive', '学工归档批次', '/admin/student-affairs/archive', 'studentAffairs.archive.view', '归档工作台')
      ])
    ]
  }
])

export function countFormalPages(workspaces = STUDENT_AFFAIRS_WORKSPACES) {
  return workspaces.reduce(
    (total, workspace) => total + workspace.groups.reduce((sum, item) => sum + item.leaves.length, 0),
    0
  )
}
