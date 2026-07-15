import { SYSTEM_MANAGEMENT_CATALOG } from '../modules/system/systemManagementCatalog.js'
import { PLATFORM_MANAGEMENT_CATALOG } from '../modules/platform/platformManagementCatalog.js'

/**
 * 菜单规划总纲（PC-NAV-PLAN）——「完整三级目录规划版」唯一事实源。
 *
 * 用途：承载 6 个一级模块下的完整二级 / 三级菜单「规划结构」，区分：
 *   - implemented：已实现页面，带现有真实 path，可点击（disabled=false）。
 *   - planned    ：待施工，无 path、不注册路由、不建组件、不可点（disabled=true, badge=待施工）。
 *
 * 铁律（对齐 CLAUDE.md §8/§9/§17）：
 *   1) 本文件只描述「菜单规划结构」，不注册任何业务路由、不创建任何组件、不写假数据；
 *   2) implemented 节点的 path 必须是已存在的真实路由，planned 节点无 path；
 *   3) 普通业务角色默认隐藏 planned（getVisibleNavPlan includePlanned=false）；
 *      管理员 / 开发者视角可见 planned（includePlanned=true）；
 *   4) 顶部搜索命中 planned 只提示「待施工」，不跳转（searchNavPlan 返回 disabled 标记）。
 *
 * 一级导航固定 6 个：工作台 / 学工中心 / 教务中心 / 毕业设计中心 / 岗位实习中心 / 系统管理。
 * 数字迎新固定归属：学工中心 > 数字迎新（不作一级）。
 */

/** 已实现叶子（带真实 path）。第 3+ 参数用于角色菜单投影：
 *  permissionKey=页面/能力权限码（getVisibleNavPlan 按当前身份权限集过滤；无 key 的叶子后向兼容=默认可见）；
 *  entryType=入口类型（WORKBENCH/TASK_QUEUE/CONFIG_VIEW/ANALYTICS_VIEW/DETAIL/ACTION/CROSS_MODULE/CAPABILITY_ONLY）；
 *  opts=其余元数据（badgeKey/dataScopeRequired 等）。 */
function I(label, path, permissionKey, entryType, opts) {
  return { label, path, status: 'implemented', disabled: false, badge: '',
    ...(permissionKey ? { permissionKey } : {}), ...(entryType ? { entryType } : {}), ...(opts || {}) }
}
/** 待施工叶子（可批量），自动 disabled + 待施工 badge，无 path 不注册路由 */
function P(...labels) {
  return labels.map((label) => ({ label, status: 'planned', disabled: true, badge: '待施工' }))
}
/** 未开通叶子（模块未授权，管理员可见「未开通」，普通角色隐藏） */
// eslint-disable-next-line no-unused-vars
function UN(label) {
  return { label, status: 'unauthorized', disabled: true, badge: '未开通' }
}
/** 隐藏叶子（真实页面但不进正常菜单/搜索：详情工作区、页内入口页；仅用于侧栏归属高亮）。
 *  第 3+ 参数同 I()：permissionKey/entryType/opts。详情/动作型能力用本函数登记——保留能力目录但不进日常侧栏。 */
function H(label, path, permissionKey, entryType, opts) {
  return { label, path, status: 'implemented', disabled: false, badge: '', hidden: true,
    ...(permissionKey ? { permissionKey } : {}), ...(entryType ? { entryType } : {}), ...(opts || {}) }
}
/** 二级模块：有 path=已实现入口，无 path=待施工入口 */
function mod(key, label, path, children) {
  const s = path
    ? { path, status: 'implemented', disabled: false, badge: '' }
    : { status: 'planned', disabled: true, badge: '待施工' }
  return { key, label, ...s, children: children || [] }
}
/** 一级模块 */
function grp(key, label, moduleKey, children, extra) {
  return { key, label, moduleKey, children, ...(extra || {}) }
}

export const NAV_PLAN = [
  /* ═══════════ 一级①：工作台 ═══════════ */
  grp('workbench', '工作台', 'workbench', [
    mod('wb-home', '我的工作台', '/', []),
    mod('wb-todo', '我的待办', '/admin/approval/todos', []),
    mod('wb-approval', '审批中心', '/admin/approval', [
      I('待办看板', '/admin/approval'),
      I('我的待办', '/admin/approval/todos'),
      I('已办 · 抄送', '/admin/approval/done'),
      I('退回记录', '/admin/approval/returned'),
      I('审批模板', '/admin/approval/templates')
    ]),
    mod('wb-messages', '消息通知', null, P('通知中心', '公告', '待办提醒', '消息设置')),
    mod('wb-dashboard', '领导驾驶舱', '/admin/data-center', [
      I('数据驾驶舱', '/admin/data-center'),
      I('生命周期总览', '/admin/data-center/lifecycle'),
      I('排行分析', '/admin/data-center/rankings'),
      I('风险预警', '/admin/data-center/risk'),
      I('专题报表', '/admin/data-center/reports')
    ]),
    mod('wb-recent', '最近访问', null, P('最近访问'))
  ]),

  /* ═══════════ 一级②：学工中心 ═══════════ */
  grp('student-affairs', '学工中心', 'studentAffairs', [
    /* 本组 1:1 对齐 docs/00-项目入口与总控/施工图/施工图-02-学工中心.html（14 个二级 + 数字迎新独立成二级 + 在校服务过渡尾）。
       状态以代码真实路由为准：施工图上标「待施工」但代码已建的（请假 4/4、班级 4/4），此处按已实现标 I。 */
    // 施工图卡·学工工作台（B包第5步·待施工）
    mod('sa-workbench', '学工工作台', null, [
      I('学工总览', '/admin/student-affairs/dashboard'),
      I('辅导员工作台', '/admin/student-affairs/workbench'),
      I('辅导员考评（指标/评分/申诉）', '/admin/student-affairs/counselor-eval')
    ]),
    // 施工图卡·学生画像（已有底座·6 三级已实现）
    mod('sa-profile', '学生画像', '/admin/student', [
      I('学生列表（学生主档）', '/admin/student/list'),
      I('学籍状态摘要', '/admin/student/status'),
      I('风险标签', '/admin/student/risk-tags'),
      I('信息更正审核', '/admin/student/corrections'),
      I('身份核验（现有）', '/admin/student/identity'),
      I('导入导出（现有）', '/admin/student/import-export')
    ]),
    // 施工图卡·班级与辅导员（B包第2步·代码已建 4/4，施工图标注偏旧）
    mod('sa-classes', '班级与辅导员', null, [
      I('班级列表', '/admin/campus-service/classes'),
      // 班级画像/材料 = 班级列表点入的独立画像页（学生/材料/班干部 Tab）
      I('班级画像', '/admin/campus-service/classes'),
      I('班级材料', '/admin/campus-service/classes'),
      I('辅导员考评', '/admin/campus-service/counselor-assessment')
    ]),
    // 数字迎新：学工中心独立二级（甲方明确）·19 三级已实现
    mod('sa-orientation', '数字迎新', '/admin/orientation', [
      I('迎新看板', '/admin/orientation'),
      I('迎新批次', '/admin/orientation/batches'),
      I('新生数据', '/admin/orientation/data'),
      I('新生信息核验', '/admin/orientation/verify'),
      I('报到资格', '/admin/orientation/qualification'),
      I('报到流程配置', '/admin/orientation/flow-config'),
      I('新生报到', '/admin/orientation/students'),
      I('报到进度', '/admin/orientation/progress'),
      I('缴费状态', '/admin/orientation/payment'),
      I('绿色通道', '/admin/orientation/green-channels'),
      I('材料审核', '/admin/orientation/materials'),
      I('宿舍预分配', '/admin/orientation/dorm-preassign'),
      I('宿舍入住', '/admin/orientation/dorm'),
      I('现场报到点', '/admin/orientation/checkin-points'),
      I('异常学生', '/admin/orientation/exceptions'),
      I('未报到学生', '/admin/orientation/no-show'),
      I('迎新通知', '/admin/orientation/notices'),
      I('迎新统计', '/admin/orientation/statistics'),
      I('迎新归档', '/admin/orientation/archive')
    ]),
    // 施工图卡·请假销假（B包第1步·代码已建 4/4，施工图标注偏旧）
    mod('sa-leave', '请假销假', null, [
      I('请假审批', '/admin/campus-service/leave'),
      I('销假与续假', '/admin/campus-service/leave-extensions'),
      I('请假台账', '/admin/campus-service/leave-ledger'),
      I('请假统计', '/admin/campus-service/leave-stats')
    ]),
    // 施工图卡·宿舍与公寓（2026-07-12 前端6页接通 /student-affairs/dorm/*；宿管 DORM_BUILDING 范围）
    mod('sa-dorm', '宿舍与公寓', null, [
      I('房源管理', '/admin/student-affairs/dorm/resource'),
      I('入住管理', '/admin/student-affairs/dorm/checkin'),
      I('调宿与退宿', '/admin/student-affairs/dorm/transfer'),
      I('宿舍检查', '/admin/student-affairs/dorm/check'),
      I('宿舍异常（含夜不归宿）', '/admin/student-affairs/dorm/exception'),
      I('宿舍统计', '/admin/student-affairs/dorm/stats')
    ]),
    // 施工图卡·风险预警与处置（B包第4步·待施工）
    mod('sa-risk', '风险预警与处置', null, [
      I('风险预警（看板/学生/处置）', '/admin/student-affairs/risk')
    ]),
    // 施工图卡·困难认定（C包第6步·2026-07-13 夜间接通 /student-affairs/aid/*：批次管理/工作台/困难库）
    mod('sa-difficulty', '困难认定', null, [
      I('认定批次', '/admin/student-affairs/aid/batches'),
      I('认定申请与审核（工作台）', '/admin/student-affairs/aid'),
      I('公示待办', '/admin/student-affairs/aid/publicity'),
      I('认定台账', '/admin/student-affairs/aid/ledger'),
      I('困难学生库', '/admin/student-affairs/aid/difficult-students'),
      I('认定统计', '/admin/student-affairs/aid/stats'),
      I('异议复核', '/admin/student-affairs/aid/objections')
    ]),
    // 施工图卡·奖助勤贷补（C包第7步·2026-07-13 夜间接通 /student-affairs/funding/*：项目管理/申请评审工作台）
    mod('sa-aid', '奖助勤贷补', null, [
      I('资助项目', '/admin/student-affairs/funding/projects'),
      I('资助批次', '/admin/student-affairs/funding/batches'),
      I('申请评审（工作台）', '/admin/student-affairs/funding'),
      I('公示待办', '/admin/student-affairs/funding/publicity'),
      I('发放台账', '/admin/student-affairs/funding/disbursements'),
      I('资助统计', '/admin/student-affairs/funding/stats'),
      I('助学金管理（现有·奖助资助）', '/admin/campus-service/grants'),
      I('勤工助学', '/admin/student-affairs/funding/work-study'),
      I('助学贷款', '/admin/student-affairs/funding/loans'),
      I('减免与临时补助', '/admin/student-affairs/funding/fee-reductions')
    ]),
    // 施工图卡·违纪处分（C包第8步·2026-07-13 夜间接通 /student-affairs/discipline/*：工作台+台账对账）
    mod('sa-discipline', '违纪处分', null, [
      I('处分工作台（登记/审批/生效/解除）', '/admin/student-affairs/discipline'),
      I('送达与申诉复核', '/admin/student-affairs/discipline/appeals'),
      I('违纪台账（含投影对账）', '/admin/student-affairs/discipline/ledger'),
      I('处分统计', '/admin/student-affairs/discipline/stats'),
      I('违纪登记（现有）', '/admin/campus-service/discipline')
    ]),
    // 施工图卡·谈心家校（C包第9步·2026-07-13 夜间接通 /student-affairs/talks|family/*：工作台+统计+家校）
    mod('sa-talks', '谈心家校', null, [
      I('谈心谈话（计划/记录/跟进）', '/admin/student-affairs/talk'),
      I('谈话台账', '/admin/student-affairs/talk/ledger'),
      I('谈话统计', '/admin/student-affairs/talk/stats'),
      I('家校联系', '/admin/student-affairs/family'),
      I('重点学生跟进', '/admin/student-affairs/talk/key-follow'),
      I('家校回执', '/admin/student-affairs/family/receipts')
    ]),
    // 施工图卡·心理关注（D包第10步·强敏感红线·2026-07-12 前端5页接通 /student-affairs/mental/*）
    mod('sa-mental', '心理关注', null, [
      I('心理关注名单', '/admin/student-affairs/mental'),
      I('心理预警摘要', '/admin/student-affairs/mental/summary'),
      I('谈话转介与回访', '/admin/student-affairs/mental/referrals'),
      I('危机升级', '/admin/student-affairs/mental/crisis'),
      I('心理统计', '/admin/student-affairs/mental/stats')
    ]),
    // 施工图卡·活动二课与社团（D包·2026-07-14 波次1 接通 /student-affairs/activity*：活动闭环+二课积分）
    mod('sa-activities', '活动二课与社团', null, [
      I('学生活动（发布/报名/签到/确认）', '/admin/student-affairs/activity'),
      I('志愿服务时长', '/admin/student-affairs/activity/volunteer'),
      I('第二课堂积分', '/admin/student-affairs/activity/second-class'),
      I('第二课堂积分申诉', '/admin/student-affairs/activity/credit-appeals'),
      I('活动统计', '/admin/student-affairs/activity/stats'),
      I('社团管理', '/admin/student-affairs/activity/clubs'),
      I('学生干部与组织', '/admin/student-affairs/activity/organizations'),
      I('党团建设', '/admin/student-affairs/activity/party-league')
    ]),
    // 施工图卡·统计与档案（D包第12步·待施工）
    // 施工图卡·统计与档案（D包·2026-07-14 接通已建视图：学工统计 StudentAffairsStatsView / 学工归档 ArchiveManageView）
    mod('sa-archive-stats', '统计与档案', null, [
      I('学工统计', '/admin/student-affairs/stats'),
      I('统计驾驶舱', '/admin/student-affairs/stats/cockpit'),
      I('学工归档', '/admin/student-affairs/archive'),
      I('学生档案包', '/admin/student-affairs/archive/packages')
    ])
    /* 2026-07-12 甲方拍板：删除「在校服务（现有·过渡）」二级——它与新14二级重复冲突（请假/奖助/违纪/宿舍/班级
       已各自成正经二级、指向 /admin/campus-service/* 实现页照常用）。campus-service 旧路由与服务工作台/学生服务/
       服务工单页仍在（不 404），仅从菜单撤出；如需保留「服务工单」等能力再单列二级。 */
  ]),

  /* ═══════════ 一级③：教务中心 ═══════════ */
  grp('academic-affairs', '教务中心', 'academicAffairs', [
    mod('aa-dashboard', '教务看板', '/admin/academic-affairs', [
      I('教务看板（教务中心）', '/admin/academic-affairs'),
      I('学业过程总览（现有）', '/admin/academic'),
      // 2026-07-15 P4：六卡提醒点亮（零新表只读聚合 GET /academic-affairs/dashboard/reminders）。
      // ?panel= 深链接滚动定位到教务看板对应分栏（AaDashboardView PANEL_ANCHORS，同岗位实习看板模式）。
      I('成绩提交进度', '/admin/academic-affairs?panel=gradeProgress', 'academicAffairs.dashboard.view', 'TASK_QUEUE'),
      I('考试安排提醒', '/admin/academic-affairs?panel=examReminders', 'academicAffairs.dashboard.view', 'TASK_QUEUE'),
      I('学籍异动提醒', '/admin/academic-affairs?panel=statusChangeReminders', 'academicAffairs.dashboard.view', 'TASK_QUEUE'),
      I('学业预警提醒', '/admin/academic-affairs?panel=warningReminders', 'academicAffairs.dashboard.view', 'TASK_QUEUE'),
      I('毕业资格预警', '/admin/academic-affairs?panel=graduationWarnings', 'academicAffairs.dashboard.view', 'TASK_QUEUE'),
      I('教务待办', '/admin/academic-affairs?panel=todos', 'academicAffairs.dashboard.view', 'TASK_QUEUE'),
      // 2026-07-16 第三轮续工：五卡点亮（零新表只读聚合，并入同一 GET /academic-affairs/dashboard/reminders）。
      // 今日课程/教学资源占用口径依赖「当前学期+当前已发布课表批次」，无当前学期/未发布课表时面板内 note 说明原因。
      I('今日教学运行', '/admin/academic-affairs?panel=todayTeaching', 'academicAffairs.dashboard.view', 'TASK_QUEUE'),
      I('今日课程', '/admin/academic-affairs?panel=todayCourses', 'academicAffairs.dashboard.view', 'TASK_QUEUE'),
      I('调停课提醒', '/admin/academic-affairs?panel=scheduleChangeReminders', 'academicAffairs.dashboard.view', 'TASK_QUEUE'),
      I('教学资源占用', '/admin/academic-affairs?panel=resourceOccupancy', 'academicAffairs.dashboard.view', 'TASK_QUEUE'),
      I('教务数据趋势', '/admin/academic-affairs?panel=dataTrends', 'academicAffairs.dashboard.view', 'ANALYTICS_VIEW')
    ]),
    mod('aa-terms', '学年学期', '/admin/academic-affairs/terms', [
      I('学期管理', '/admin/academic-affairs/terms'),
      I('学年管理', '/admin/academic-affairs/terms/years', 'academicAffairs.term.view'),
      I('当前学期设置', '/admin/academic-affairs/terms/current', 'academicAffairs.term.view'),
      I('学期周次', '/admin/academic-affairs/terms/weeks', 'academicAffairs.term.view'),
      I('教学周配置', '/admin/academic-affairs/terms/teaching-weeks', 'academicAffairs.term.manage'),
      I('学期状态', '/admin/academic-affairs/terms/status', 'academicAffairs.term.manage'),
      I('学期切换记录', '/admin/academic-affairs/terms/switch-log', 'academicAffairs.term.view'),
      I('学期归档', '/admin/academic-affairs/terms/archive-status', 'academicAffairs.term.view')
    ]),
    mod('aa-calendar', '校历节次', '/admin/academic-affairs/calendar', [
      I('校历管理', '/admin/academic-affairs/calendar'),
      I('作息时间', '/admin/academic-affairs/time-slots'),
      // 2026-07-15 Tier1 R2：节假日/补课日=按 eventType 过滤同一批 t_aa_calendar_event（AaCalendarView 页签）；
      // 节次管理=复用「作息时间」页（t_aa_time_slot 全 CRUD）；上课时间段=新表 t_aa_class_time_band；
      // 教学周日历=派生只读聚合；校历发布/归档=复用学期状态机，仅教务处/学校管理员（后端角色白名单强制）。
      I('节假日配置', '/admin/academic-affairs/calendar?tab=holiday', 'academicAffairs.calendar.view'),
      I('补课日配置', '/admin/academic-affairs/calendar?tab=makeup', 'academicAffairs.calendar.view'),
      I('节次管理', '/admin/academic-affairs/time-slots', 'academicAffairs.timeslot.manage'),
      I('上课时间段', '/admin/academic-affairs/time-slots?tab=bands', 'academicAffairs.classTimeBand.view'),
      I('教学周日历', '/admin/academic-affairs/calendar?tab=weekCalendar', 'academicAffairs.calendar.view'),
      I('校历发布', '/admin/academic-affairs/calendar?tab=publish', 'academicAffairs.calendarPublish.manage'),
      I('校历归档', '/admin/academic-affairs/calendar?tab=archive', 'academicAffairs.calendarArchive.manage')
    ]),
    mod('aa-student-status', '学籍管理', '/admin/academic-affairs/roster', [
      I('学籍名册', '/admin/academic-affairs/roster'),
      H('学籍档案', '/admin/academic-affairs/roster', 'academicAffairs.roster.view', 'DETAIL'),
      I('学籍状态', '/admin/academic-affairs/roster/status', 'academicAffairs.roster.view'),
      I('学籍异动记录', '/admin/academic-affairs/roster/changes', 'academicAffairs.statusChange.view'),
      I('学籍导入导出', '/admin/academic-affairs/roster/import-export', 'academicAffairs.roster.import'),
      // 2026-07-16 Tier1 R3 续工：休学/退学/保留学籍=学籍名册按 student_status 过滤的分类视图
      // （AaRosterListView 新支持 ?status= 深链预填，不重复造页）；复学/转专业因终态回落 REGISTERED、
      // 无法用 student_status 区分，改从「学籍异动」流水按 changeType 取结果视图（AaRosterChangeResultListView，
      // 只读+链接学籍档案，不提供发起入口，不与学籍异动模块的申请/审批功能重复）；学籍信息更正=全新生产级
      // 功能（学号/姓名/性别/证件号/年级，单步审核同步主档，明确排除学籍状态/院系专业班级）；学籍统计/
      // 学籍归档=复用「教务统计」「教务归档」既有页面的轻量入口（?scope=roster/?entry=studentStatus 仅用于
      // 侧栏 leafKey 去重，不改变目标页行为，见 navPlan 唯一 leafKey 规则与 aa-archive/aa-stats 同类先例）。
      I('休学学生', '/admin/academic-affairs/roster?status=SUSPENDED', 'academicAffairs.roster.view'),
      I('复学学生', '/admin/academic-affairs/roster/resumed-students', 'academicAffairs.statusChange.view'),
      I('退学学生', '/admin/academic-affairs/roster?status=WITHDRAWN', 'academicAffairs.roster.view'),
      I('转专业学生', '/admin/academic-affairs/roster/transferred-major-students', 'academicAffairs.statusChange.view'),
      I('保留学籍', '/admin/academic-affairs/roster?status=RETAINED', 'academicAffairs.roster.view'),
      I('学籍信息更正', '/admin/academic-affairs/roster/corrections', 'academicAffairs.roster.correction.view'),
      // 注意：navRefMatches 比较候选 query 时用原始字符串（不重新排序），故这里必须已按 key 字母序书写
      // （scope < tab），否则真实点击该叶子时 $route.fullPath 排序后与候选串不等，导致高亮失效。
      I('学籍统计', '/admin/academic-affairs/stats?scope=roster&tab=statusChange', 'academicAffairs.stats.view'),
      I('学籍归档', '/admin/academic-affairs/archive?entry=studentStatus', 'academicAffairs.archive.view')
    ]),
    mod('aa-registration', '注册管理', '/admin/academic-affairs/registration', [
      I('注册批次', '/admin/academic-affairs/registration'),
      I('入学注册', '/admin/academic-affairs/registration?type=ENROLL', 'academicAffairs.registration.view'),
      I('学年注册', '/admin/academic-affairs/registration?type=ANNUAL', 'academicAffairs.registration.view'),
      // 2026-07-16 续工三级卡：学期注册=第三种 register_type（SEMESTER），与入学/学年共用同一批次引擎/页面，
      // 仅类型与菜单入口独立（后端 create_registration_batch 已放开校验，见 academic_affairs_service.py）。
      I('学期注册', '/admin/academic-affairs/registration?type=SEMESTER', 'academicAffairs.registration.view'),
      I('注册资格核验', '/admin/academic-affairs/registration/workbench?tab=eligibility', 'academicAffairs.registration.eligibility.view'),
      I('未注册学生', '/admin/academic-affairs/registration/workbench?tab=unregistered', 'academicAffairs.registration.unregistered.view'),
      I('暂缓注册', '/admin/academic-affairs/registration/workbench?tab=deferral', 'academicAffairs.registration.deferral.view'),
      I('注册异常', '/admin/academic-affairs/registration/workbench?tab=exception', 'academicAffairs.registration.exception.view'),
      // 注册统计=复用「教务统计」页 tab=registration（同页同接口，见下方 aa-stats 模块同一叶子）；
      // 注册归档=新增 OPEN→CLOSED→ARCHIVED 批次只读台账+导出（workbench 第 5 个 Tab，关闭/归档动作在「注册批次」列表执行）。
      I('注册统计', '/admin/academic-affairs/stats?tab=registration', 'academicAffairs.stats.view'),
      I('注册归档', '/admin/academic-affairs/registration/workbench?tab=archive', 'academicAffairs.registration.archive.view')
    ]),
    mod('aa-status-change', '学籍异动', '/admin/academic-affairs/status-changes', [
      I('异动台账', '/admin/academic-affairs/status-changes'),
      I('发起异动', '/admin/academic-affairs/status-changes/new'),
      I('休学申请', '/admin/academic-affairs/status-changes/suspend', 'academicAffairs.statusChange.apply'),
      I('复学申请', '/admin/academic-affairs/status-changes/resume', 'academicAffairs.statusChange.apply'),
      I('退学申请', '/admin/academic-affairs/status-changes/withdraw', 'academicAffairs.statusChange.apply'),
      I('转专业申请', '/admin/academic-affairs/status-changes/transfer-major', 'academicAffairs.statusChange.apply'),
      I('异动审批', '/admin/academic-affairs/status-changes/approval', 'academicAffairs.statusChange.collegeReview'),
      I('异动生效', '/admin/academic-affairs/status-changes/effective', 'academicAffairs.statusChange.view'),
      I('异动统计', '/admin/academic-affairs/status-changes/stats', 'academicAffairs.statusChange.view'),
      // 2026-07-16 学籍异动三级模块续工（第三轮补缺）：转班/保留学籍/异动归档三叶子翻 implemented。
      // 转班=新异动类型 TRANSFER_CLASS（同专业换班，区别于跨专业 TRANSFER_MAJOR），全栈新建。
      // 保留学籍申请=按既有 RETAIN(留级) 类型补建分类入口（沿用「留级(RETAIN)不设分类入口，走通用页」
      // 之前的缺口）；冻结的学籍状态机(SM-02,14态)无独立「保留学籍」状态，RETAIN 是唯一匹配的既有状态，
      // 页内已如实标注：如学校实际所指是参军/创业/病休等区别于留级的独立保留学籍政策，需另行业务确认，
      // 待用户决定，未冒充已完成。异动归档=复用异动台账/统计只读端点组合的在途监控视图，不新增后端接口。
      I('转班申请', '/admin/academic-affairs/status-changes/transfer-class', 'academicAffairs.statusChange.apply'),
      I('保留学籍申请', '/admin/academic-affairs/status-changes/retain', 'academicAffairs.statusChange.apply'),
      I('异动归档', '/admin/academic-affairs/status-changes/archive', 'academicAffairs.statusChange.view')
    ]),
    mod('aa-orgs', '学院专业班级', '/admin/academic-affairs/orgs', [
      I('学院管理', '/admin/academic-affairs/orgs?tab=college', 'academicAffairs.org.view'),
      I('专业管理', '/admin/academic-affairs/orgs?tab=major', 'academicAffairs.org.view'),
      I('年级管理', '/admin/academic-affairs/orgs?tab=grade', 'academicAffairs.org.view'),
      I('行政班管理', '/admin/academic-affairs/orgs?tab=class', 'academicAffairs.org.view'),
      I('教学班管理', '/admin/academic-affairs/orgs?tab=teaching', 'academicAffairs.org.view'),
      I('组织结构同步', '/admin/academic-affairs/orgs?tab=tree', 'academicAffairs.org.view'),
      I('组织统计', '/admin/academic-affairs/orgs?tab=stats', 'academicAffairs.org.view'),
      // Tier1 续工（2026-07-15）：专业方向（总开关默认关闭）/ 班级学生（只读增强）/ 班级调整（批量组织调整）
      I('专业方向', '/admin/academic-affairs/orgs?tab=direction', 'academicAffairs.org.view'),
      I('班级学生', '/admin/academic-affairs/orgs?tab=students', 'academicAffairs.org.view'),
      I('班级调整', '/admin/academic-affairs/orgs?tab=adjust', 'academicAffairs.org.view')
    ]),
    mod('aa-training', '培养方案', '/admin/academic-affairs/programs', [
      I('方案列表', '/admin/academic-affairs/programs'),
      // Tier1 续工（2026-07-15）：以下 7 项接入统一控制台 /programs/console?tab=xxx（DataTable+Drawer，深编辑仍回既有 /programs/:id 编制器）
      I('方案制定', '/admin/academic-affairs/programs/console?tab=authoring', 'academicAffairs.program.view'),
      I('方案版本', '/admin/academic-affairs/programs/console?tab=versions', 'academicAffairs.program.view'),
      I('课程模块', '/admin/academic-affairs/programs/console?tab=courseModules', 'academicAffairs.program.view'),
      I('学分要求', '/admin/academic-affairs/programs/console?tab=creditRequirements', 'academicAffairs.program.view'),
      ...P('实践环节'),
      I('毕业要求', '/admin/academic-affairs/programs/console?tab=graduationRequirements', 'academicAffairs.program.view'),
      I('方案审核', '/admin/academic-affairs/programs/console?tab=review', 'academicAffairs.program.view'),
      I('方案发布', '/admin/academic-affairs/programs/console?tab=publish', 'academicAffairs.program.view'),
      ...P('方案变更', '方案归档')
    ]),
    mod('aa-courses', '课程库', '/admin/academic-affairs/courses', [
      I('课程列表', '/admin/academic-affairs/courses'),
      // Tier1 续工（2026-07-15）：以下 5 项接入统一控制台 /courses/console?tab=xxx（DataTable+Drawer，深编辑/两级审核仍回既有 /courses/:id）
      I('新增课程', '/admin/academic-affairs/courses/new', 'academicAffairs.course.manage'),
      I('课程分类', '/admin/academic-affairs/courses/console?tab=category', 'academicAffairs.course.view'),
      I('课程性质', '/admin/academic-affairs/courses/console?tab=nature', 'academicAffairs.course.view'),
      I('学分学时', '/admin/academic-affairs/courses/console?tab=credit', 'academicAffairs.course.view'),
      ...P('课程大纲', '考核方式'),
      I('课程负责人', '/admin/academic-affairs/courses/console?tab=owner', 'academicAffairs.course.view'),
      ...P('课程材料'),
      I('课程停用', '/admin/academic-affairs/courses/console?tab=disable', 'academicAffairs.course.view'),
      ...P('课程归档')
    ]),
    // 教学计划：按手册 P6 冻结决定 + 用户 2026-07-14 拍板「收编」——不建独立域，叶子指向既有等价功能页
    // 年级/专业教学计划=培养方案(AaProgramBinding方案-年级绑定)；学期教学计划/课程开设计划=教学任务批次(AaTeachingTaskBatch学期开课计划)；计划归档=教务归档
    mod('aa-teaching-plan', '教学计划', '/admin/academic-affairs/programs', [
      I('年级/专业教学计划（培养方案）', '/admin/academic-affairs/programs', 'academicAffairs.program.view'),
      I('学期教学计划/课程开设计划（教学任务）', '/admin/academic-affairs/teaching-tasks', 'academicAffairs.teachingTask.view'),
      I('计划归档（教务归档）', '/admin/academic-affairs/archive', 'academicAffairs.archive.view'),
      ...P('实践教学计划', '计划审核', '计划发布', '计划变更', '计划执行进度')
    ]),
    mod('aa-teaching-tasks', '教学任务', '/admin/academic-affairs/teaching-tasks', [
      I('教学任务批次', '/admin/academic-affairs/teaching-tasks'),
      I('教学任务生成', '/admin/academic-affairs/teaching-tasks?open=generate', 'academicAffairs.teachingTask.generate'),
      I('任课教师分配', '/admin/academic-affairs/teaching-tasks/assign', 'academicAffairs.teachingTask.assign'),
      ...P('教学班生成'),
      I('合班拆班', '/admin/academic-affairs/teaching-tasks/merge-split', 'academicAffairs.teachingTask.merge'),
      I('教学任务确认', '/admin/academic-affairs/teaching-tasks/confirm', 'academicAffairs.teachingTask.confirm'),
      I('教师任务确认', '/admin/academic-affairs/teaching-tasks/teacher-confirm', 'academicAffairs.teachingTask.teacherConfirm'),
      ...P('教学任务调整'),
      I('教学任务统计', '/admin/academic-affairs/teaching-tasks/stats', 'academicAffairs.teachingTask.stats'),
      ...P('教学任务归档')
    ]),
    mod('aa-scheduling', '排课管理', '/admin/academic-affairs/scheduling', [
      I('排课规则', '/admin/academic-affairs/scheduling?tab=rules', 'academicAffairs.schedule.view'),
      I('教师可用时间', '/admin/academic-affairs/scheduling?tab=availability', 'academicAffairs.schedule.view'),
      I('冲突报告', '/admin/academic-affairs/scheduling?tab=conflict', 'academicAffairs.schedule.view'),
      I('人工排课工作台（课表维护）', '/admin/academic-affairs/schedule', 'academicAffairs.schedule.view'),
      I('排课约束', '/admin/academic-affairs/scheduling?tab=constraint', 'academicAffairs.schedule.view'),
      I('教室可用时间', '/admin/academic-affairs/scheduling?tab=room', 'academicAffairs.schedule.view'),
      I('自动排课预留', '/admin/academic-affairs/scheduling?tab=import', 'academicAffairs.schedule.import'),
      I('排课结果', '/admin/academic-affairs/scheduling?tab=result', 'academicAffairs.schedule.view'),
      I('排课调整', '/admin/academic-affairs/scheduling?tab=adjust', 'academicAffairs.schedule.edit'),
      I('排课归档', '/admin/academic-affairs/schedule?panel=archive', 'academicAffairs.schedule.archive')
    ]),
    mod('aa-schedule', '课表管理', '/admin/academic-affairs/schedule', [
      I('课表批次 / 排课', '/admin/academic-affairs/schedule'),
      I('班级课表', '/admin/academic-affairs/schedule/class', 'academicAffairs.schedule.view'),
      I('教师课表', '/admin/academic-affairs/schedule/teacher', 'academicAffairs.schedule.view'),
      ...P('学生课表'),
      I('教室课表', '/admin/academic-affairs/schedule/room', 'academicAffairs.classroom.view'),
      ...P('教学班课表', '周课表', '学期课表'),
      I('课表发布', '/admin/academic-affairs/schedule/publish', 'academicAffairs.schedule.view'),
      ...P('课表调整记录'),
      I('课表导出', '/admin/academic-affairs/schedule/export', 'academicAffairs.schedule.export')
    ]),
    mod('aa-schedule-change', '调停课', '/admin/academic-affairs/schedule-change', [
      I('调停课台账', '/admin/academic-affairs/schedule-change', 'academicAffairs.scheduleChange.view'),
      I('发起调停课（调课/停课/补课）', '/admin/academic-affairs/schedule-change/apply', 'academicAffairs.scheduleChange.apply'),
      I('调停课审批', '/admin/academic-affairs/schedule-change/approval', 'academicAffairs.scheduleChange.collegeReview'),
      ...P('调停课通知'),
      // 冲突检测无独立页面：能力已嵌入「发起调停课」表单内（提交前预检区），叶子指向宿主表单
      I('调停课冲突检测', '/admin/academic-affairs/schedule-change/apply', 'academicAffairs.scheduleChange.apply'),
      I('调停课统计', '/admin/academic-affairs/schedule-change/stats', 'academicAffairs.scheduleChange.view'),
      I('调停课归档', '/admin/academic-affairs/schedule-change/archive', 'academicAffairs.scheduleChange.view')
    ]),
    mod('aa-course-selection', '选课管理', '/admin/academic-affairs/selection', [
      I('选课批次控制台（批次/课程/名单/统计）', '/admin/academic-affairs/selection', 'academicAffairs.selection.view'),
      I('我的选课（学生自助）', '/admin/academic-affairs/my-selection', 'academicAffairs.selection.enroll'),
      I('选课规则', '/admin/academic-affairs/selection?tab=rule', 'academicAffairs.selection.rule.manage'),
      I('补选管理', '/admin/academic-affairs/selection?tab=reselect', 'academicAffairs.selection.view'),
      I('冲突检测', '/admin/academic-affairs/selection?tab=conflict', 'academicAffairs.selection.view'),
      I('选课结果（并入学生课表，见课表三视图）', '/admin/academic-affairs/schedule', 'academicAffairs.schedule.view'),
      I('选课归档', '/admin/academic-affairs/selection/archive', 'academicAffairs.selection.manage')
    ]),
    mod('aa-exam', '考务管理', '/admin/academic-affairs/exam', [
      I('考务控制台（批次/课程/考场/座位/监考/巡考/异常/统计）', '/admin/academic-affairs/exam', 'academicAffairs.exam.view'),
      I('座位表/准考证/门贴打印', '/admin/academic-affairs/exam/print/seating', 'academicAffairs.exam.view'),
      I('缓考审批（并入控制台/学生小程序申请）', '/admin/academic-affairs/exam?tab=defer', 'academicAffairs.deferredExam.review'),
      I('考务归档', '/admin/academic-affairs/exam?tab=archive', 'academicAffairs.exam.view')
    ]),
    mod('aa-makeup', '补考重修缓考免修', '/admin/academic-affairs/makeup', [
      I('补考批次', '/admin/academic-affairs/makeup?tab=makeup', 'academicAffairs.makeup.view'),
      I('重修审批', '/admin/academic-affairs/makeup?tab=retake', 'academicAffairs.makeup.view'),
      I('免修审批', '/admin/academic-affairs/makeup?tab=exemption', 'academicAffairs.makeup.view'),
      I('缓考合流', '/admin/academic-affairs/makeup?tab=deferred', 'academicAffairs.makeup.view'),
      I('重修免修申请（学生自助）', '/admin/academic-affairs/my-makeup', 'academicAffairs.retake.apply'),
      I('统计分析', '/admin/academic-affairs/makeup/stats', 'academicAffairs.makeup.view', 'ANALYTICS_VIEW'),
      I('材料归档', '/admin/academic-affairs/exemption/archive', 'academicAffairs.makeup.archive')
    ]),
    mod('aa-grades', '成绩管理', '/admin/academic-affairs/grade-overview', [
      I('成绩总览', '/admin/academic-affairs/grade-overview'),
      I('成绩录入（含暂存/提交）', '/admin/academic-affairs/grade-entry'),
      I('挂科清单', '/admin/academic-affairs/grade-fail'),
      I('学生成绩单', '/admin/academic-affairs/transcript'),
      I('成绩导入', '/admin/academic-affairs/grade-entry?action=import', 'academicAffairs.grade.input'),
      I('成绩导出', '/admin/academic-affairs/transcript?action=export', 'academicAffairs.grade.export'),
      I('成绩统计', '/admin/academic-affairs/stats?tab=grade', 'academicAffairs.stats.view'),
      ...P('成绩异常')
    ]),
    mod('aa-grade-review', '成绩审核发布更正', '/admin/academic-affairs/grade-college-review', [
      I('学院审核（待审核/通过/退回）', '/admin/academic-affairs/grade-college-review'),
      I('教务发布（发布/退回/归档）', '/admin/academic-affairs/grade-publish'),
      I('成绩更正申请与审核', '/admin/academic-affairs/grade-change'),
      ...P('成绩复核', '成绩操作审计')
    ]),
    mod('aa-warning', '学业预警', '/admin/academic-affairs/warnings', [
      I('预警扫描与列表', '/admin/academic-affairs/warnings'),
      I('预警看板', '/admin/academic-affairs/warnings/console?tab=dashboard', 'academicAffairs.warning.view'),
      I('学分预警', '/admin/academic-affairs/warnings/console?tab=credit', 'academicAffairs.warning.view'),
      I('挂科预警', '/admin/academic-affairs/warnings/console?tab=fail', 'academicAffairs.warning.view'),
      I('绩点预警', '/admin/academic-affairs/warnings/console?tab=gpa', 'academicAffairs.warning.view'),
      I('补考重修预警', '/admin/academic-affairs/warnings/console?tab=retake', 'academicAffairs.warning.view'),
      I('毕业风险预警', '/admin/academic-affairs/warnings/console?tab=graduation', 'academicAffairs.warning.view'),
      I('预警规则', '/admin/academic-affairs/warnings/console?tab=rules', 'academicAffairs.warning.rule.manage'),
      I('预警跟进', '/admin/academic-affairs/warnings/console?tab=followup', 'academicAffairs.warning.handle'),
      I('预警统计', '/admin/academic-affairs/warnings/console?tab=stats', 'academicAffairs.warning.view'),
      ...P('预警通知')
    ]),
    mod('aa-graduation-qual', '毕业资格审核', '/admin/academic-affairs/graduation', [
      I('毕业资格预审', '/admin/academic-affairs/graduation'),
      I('审核批次', '/admin/academic-affairs/graduation?tab=batches', 'academicAffairs.graduation.view'),
      ...P('毕业学生名单'),
      I('学分达成审核', '/admin/academic-affairs/graduation/audit-console?tab=credit', 'academicAffairs.graduation.view'),
      I('课程达成审核', '/admin/academic-affairs/graduation/audit-console?tab=course', 'academicAffairs.graduation.view'),
      I('实践环节审核', '/admin/academic-affairs/graduation/audit-console?tab=practice', 'academicAffairs.graduation.view'),
      I('毕设状态联动', '/admin/academic-affairs/graduation/audit-console?tab=thesis', 'academicAffairs.graduation.view'),
      I('实习状态联动', '/admin/academic-affairs/graduation/audit-console?tab=internship', 'academicAffairs.graduation.view'),
      ...P('欠费状态联动'),
      I('处分状态联动', '/admin/academic-affairs/graduation/audit-console?tab=discipline', 'academicAffairs.graduation.view'),
      I('毕业资格终审', '/admin/academic-affairs/graduation/audit-console?tab=final', 'academicAffairs.graduation.final'),
      ...P('不通过原因'),
      I('审核结果', '/admin/academic-affairs/graduation/audit-console?tab=results', 'academicAffairs.graduation.view'),
      I('审核归档', '/admin/academic-affairs/graduation/audit-console?tab=archive', 'academicAffairs.graduation.manage')
    ]),
    mod('aa-textbooks', '教材管理', '/admin/academic-affairs/textbooks', [
      I('教材目录', '/admin/academic-affairs/textbooks?tab=catalog', 'academicAffairs.textbook.view'),
      I('教材选用', '/admin/academic-affairs/textbooks?tab=selection', 'academicAffairs.textbook.view'),
      I('审核备案', '/admin/academic-affairs/textbooks?tab=review', 'academicAffairs.textbook.view'),
      I('征订到货', '/admin/academic-affairs/textbooks?tab=order', 'academicAffairs.textbook.view'),
      I('费用台账', '/admin/academic-affairs/textbooks?tab=fee', 'academicAffairs.textbook.view'),
      I('教材库存', '/admin/academic-affairs/textbooks?tab=stock', 'academicAffairs.textbook.view'),
      I('教材统计', '/admin/academic-affairs/textbooks?tab=stats', 'academicAffairs.textbook.view')
    ]),
    mod('aa-resources', '教学资源', '/admin/academic-affairs/classrooms', [
      I('教室资源', '/admin/academic-affairs/classrooms', 'academicAffairs.classroom.view'),
      I('教室预约', '/admin/academic-affairs/classroom-bookings', 'academicAffairs.classroom.view'),
      ...P('实训室资源', '设备资源', '实训室预约', '资源占用', '资源冲突', '资源维修', '资源统计')
    ]),
    mod('aa-evaluation', '教学评价', '/admin/academic-affairs/evaluation', [
      I('评教批次（结果分级）', '/admin/academic-affairs/evaluation?tab=batches', 'academicAffairs.evaluation.view'),
      I('申诉审核', '/admin/academic-affairs/evaluation?tab=appeals', 'academicAffairs.evaluation.view'),
      I('学生评教(小程序)', '/admin/academic-affairs/evaluation?tab=studentEval', 'academicAffairs.evaluation.view'),
      I('教师自评', '/admin/academic-affairs/evaluation?tab=selfEval', 'academicAffairs.evaluation.selfEval.submit'),
      I('同行评价', '/admin/academic-affairs/evaluation?tab=peerEval', 'academicAffairs.evaluation.peerEval.submit'),
      I('督导评价', '/admin/academic-affairs/evaluation?tab=supervisorEval', 'academicAffairs.evaluation.supervisorEval.submit'),
      I('评价统计', '/admin/academic-affairs/evaluation?tab=evalStats', 'academicAffairs.evaluation.view'),
      I('评价归档', '/admin/academic-affairs/evaluation?tab=archive', 'academicAffairs.evaluation.view')
    ]),
    mod('aa-quality', '教学质量', '/admin/academic-affairs/quality', [
      I('运行质量看板 + 质量报告导出', '/admin/academic-affairs/quality', 'academicAffairs.quality.dashboard.view'),
      ...P('督导听课', '巡课记录', '教学检查', '教学事故', '质量整改', '整改跟进', '质量归档')
    ]),
    mod('aa-archive', '教务归档', '/admin/academic-affairs/archive', [
      I('归档批次 + 9数据域完整性检查 + 学期封存', '/admin/academic-affairs/archive', 'academicAffairs.archive.view'),
      /* 2026-07-15 Tier1 续工（10/11/12 三级卡）：归档缺失提醒=独立预检看板；批量归档=与上一叶子同一批次
       * 工作台真实页面（10/11/12 三级卡口径下"批量归档"即该工作台的正式命名），本行加 ?entry= 区分 leafKey
       * 高亮/点击（§9.4 唯一 leafKey 规则），不改上一叶子；归档导出=独立下载面板。 */
      I('归档缺失提醒', '/admin/academic-affairs/archive/precheck', 'academicAffairs.archive.view'),
      I('批量归档', '/admin/academic-affairs/archive?entry=batch', 'academicAffairs.archive.view'),
      I('归档导出', '/admin/academic-affairs/archive/export', 'academicAffairs.archive.export')
    ]),
    mod('aa-stats', '教务统计', '/admin/academic-affairs/stats', [
      I('教务总览（11 项指标 · 多维筛选 · 下钻 · 导出）', '/admin/academic-affairs/stats', 'academicAffairs.stats.view'),
      I('学籍统计', '/admin/academic-affairs/stats?tab=statusChange', 'academicAffairs.stats.view'),
      I('注册统计', '/admin/academic-affairs/stats?tab=registration', 'academicAffairs.stats.view'),
      I('课程统计', '/admin/academic-affairs/stats?tab=course', 'academicAffairs.stats.view'),
      I('教学任务统计', '/admin/academic-affairs/stats?tab=teachingTask', 'academicAffairs.stats.view'),
      I('课表统计', '/admin/academic-affairs/stats?tab=schedule', 'academicAffairs.stats.view'),
      ...P('调停课统计', '选课统计', '考务统计'),
      I('成绩统计', '/admin/academic-affairs/stats?tab=grade', 'academicAffairs.stats.view'),
      I('学业预警统计', '/admin/academic-affairs/stats?tab=warning', 'academicAffairs.stats.view'),
      I('毕业资格统计', '/admin/academic-affairs/stats?tab=graduation', 'academicAffairs.stats.view'),
      I('教师工作量统计', '/admin/academic-affairs/stats?tab=workload', 'academicAffairs.stats.view'),
      ...P('教学资源统计'),
      I('导出报表', '/admin/academic-affairs/stats?tab=export', 'academicAffairs.stats.export')
    ])
  ]),

  /* ═══════════ 一级④：毕业设计中心（key 对齐 adminMenu 的 graduation，供 rail 高亮联动）═══════════
   * 2026-07-09 按三家成熟商业系统对标重新分组（详见 docs/施工记录/毕业设计中心-导航重构对标记录.md）。
   * 2026-07-10 二级模块任务化与三级去重收口：
   *   1) 三级只保留「真实独立的工作队列 / 工作区 / 配置页」；同一页面的状态筛选、动作按钮、
   *      统计跳转不再挂菜单——能力全部保留在页面内（视图页签 / 筛选 / 工具栏按钮），
   *      旧 ?panel= 深链继续可用（各页面 $route.query.panel 均已处理，路由未删）；
   *   2) 叶子标签只用老师能理解的业务名称，不再出现施工口径与内部编码；
   *   3) 每个二级模块 path 均为真实默认落点（列表 / 工作区），不依赖 ID、无空壳。 */
  grp('graduation', '毕业设计中心', 'graduationDesign', [
    mod('gd-dashboard', '毕设工作台', '/admin/graduation', [
      I('毕设总览', '/admin/graduation'),
      I('毕设统计报表', '/admin/graduation/stats-report')
    ]),
    // 毕设批次：新建/导出为页面按钮，进行中/已归档为状态筛选，不再挂菜单（?panel=create/export/running/archived 深链仍可用）
    mod('gd-batches', '毕设批次', '/admin/graduation/batches?panel=list', [
      I('批次列表', '/admin/graduation/batches?panel=list'),
      I('阶段时间轴配置', '/admin/graduation/batches?panel=stages'),
      I('规则配置', '/admin/graduation/batches?panel=rules'),
      I('材料模板', '/admin/graduation/templates?type=MATERIAL')
    ]),
    // 毕设学生：风险/导师/分组/材料/答辩组/毕业资格/归档等视图改为页内视图页签（?panel= 深链仍可用）；
    // 学生风险并入「预警 · 归档 · 统计」、学生导师并入「导师管理与分配」，不再重复挂菜单。
    mod('gd-students', '毕设学生', '/admin/graduation/students', [
      I('学生名单', '/admin/graduation/students?panel=roster'),
      I('学生进度', '/admin/graduation/students?panel=progress'),
      I('未选题学生', '/admin/graduation/students?panel=topic'),
      I('毕设资格认定', '/admin/graduation/students?panel=eligibility')
    ]),
    // 题目库：来源（教师/企业/学生自拟）与维护视图（分类/容量/要求/附件/历史/归档）改为页内视图页签。
    mod('gd-topic-lib', '题目库', '/admin/graduation/topic-lib', [
      I('题目列表', '/admin/graduation/topic-lib?panel=list'),
      I('待审核题目', '/admin/graduation/topic-lib?panel=pending')
    ]),
    // 选题管理：教师确认/退选重选＝「学生志愿与确认」同一工作区的动作；选题归档＝轮次状态；统计并入统计报表。
    mod('gd-topics', '选题管理', '/admin/graduation/topics', [
      I('学生选题结果', '/admin/graduation/topics'),
      I('选题轮次', '/admin/graduation/topic-rounds?panel=rounds'),
      I('学生志愿与确认', '/admin/graduation/topic-rounds?panel=choices'),
      I('匹配结果', '/admin/graduation/topic-rounds?panel=match'),
      I('容量冲突复核', '/admin/graduation/topic-rounds?panel=conflicts'),
      I('题目调整申请', '/admin/graduation/topic-changes')
    ]),
    // 导师管理与分配：容量/评价/批量分配/归档均为名单与分配页签内的列与动作，不再重复挂菜单。
    mod('gd-mentors', '导师管理与分配', '/admin/graduation/mentors?panel=list', [
      I('导师名单', '/admin/graduation/mentors?panel=list'),
      I('学生分配', '/admin/graduation/mentors?panel=assign'),
      I('分配冲突检测', '/admin/graduation/mentors/conflicts')
    ]),
    mod('gd-process', '过程指导', '/admin/graduation/process?panel=taskbook', [
      I('任务书', '/admin/graduation/process?panel=taskbook'),
      I('指导记录', '/admin/graduation/process?panel=guidance'),
      I('中期检查', '/admin/graduation/process?panel=midterm'),
      I('任务书模板', '/admin/graduation/templates?type=TASKBOOK')
    ]),
    // 开题审核：附件/开题答辩/整改跟踪均在批阅详情页内完成；统计并入统计报表。
    mod('gd-proposal', '开题审核', '/admin/graduation/proposals', [
      I('开题报告批阅', '/admin/graduation/proposals'),
      I('开题模板', '/admin/graduation/templates?type=PROPOSAL')
    ]),
    mod('gd-final-review', '成果检查', '/admin/graduation/finals', [
      I('成果提交与批阅', '/admin/graduation/finals'),
      I('查重记录', '/admin/graduation/defense-grade?panel=plagiarism'),
      I('教师评阅', '/admin/graduation/defense-grade?panel=review'),
      I('成果互查整改', '/admin/graduation/more?panel=peer')
    ]),
    // 答辩成绩：答辩分组/答辩通知＝答辩安排页内动作；归档统一走「预警 · 归档 · 统计」。
    mod('gd-defense', '答辩成绩', '/admin/graduation/defense', [
      I('答辩安排', '/admin/graduation/defense'),
      I('答辩评分', '/admin/graduation/defense-grade?panel=defense'),
      I('成绩评定', '/admin/graduation/defense-grade?panel=grade'),
      I('答辩专家库', '/admin/graduation/more?panel=experts'),
      I('成绩更正申诉', '/admin/graduation/more?panel=appeals')
    ]),
    mod('gd-risk-archive', '预警 · 归档 · 统计', '/admin/graduation/risk-archive?panel=risk', [
      I('问题预警', '/admin/graduation/risk-archive?panel=risk'),
      I('毕设材料归档', '/admin/graduation/risk-archive?panel=archive'),
      I('毕设统计', '/admin/graduation/risk-archive?panel=stats')
    ])
  ]),

  /* ═══════════ 一级⑤：岗位实习中心（12个二级）═══════════
   * 2026-07-12 甲方拍板「菜单全展开」：本组 1:1 对齐 施工图-05-岗位实习中心（12二级×99三级）。
   * 已实现=I(真实路由)，待补强=PA(灰橙「待补强」，可点进现有页/所属工作区)。
   * 多个三级指向同一页面（状态/类型/流程变体）由 §9.4 唯一 leafKey 高亮/点击支持；?panel= 为真实路由。
   * 二级 key 不变（供 rail/adminMenu 兼容），仅 label 改为施工图名。 */
  grp('internship', '岗位实习中心', 'internship', [
    mod('in-workbench', '实习工作台', '/admin/internship', [
      I('实习总览', '/admin/internship', 'internship.dashboard.view', 'WORKBENCH'),
      I('当前批次进度', '/admin/internship?panel=batch-progress', 'internship.dashboard.view', 'WORKBENCH'),
      I('我的待办', '/admin/internship?panel=todos', 'internship.dashboard.view', 'TASK_QUEUE'),
      I('风险提醒', '/admin/internship/risks', 'internship.risk.view', 'TASK_QUEUE'),
      I('数据趋势', '/admin/internship/stats?dimension=trend', 'internship.stats.view', 'ANALYTICS_VIEW')
    ]),
    mod('in-batch-rules', '批次与规则', '/admin/internship/batches', [
      I('批次列表', '/admin/internship/batches?panel=list', 'internship.batch.view', 'WORKBENCH'),
      H('批次详情', '/admin/internship/batches?panel=list', 'internship.batch.view', 'DETAIL'),
      I('阶段配置', '/admin/internship/batches?panel=timeline', 'internship.batch.stage.manage', 'CONFIG_VIEW'),
      I('打卡规则', '/admin/internship/batches?panel=rules&rule=checkin', 'internship.batch.rule.checkin.manage', 'CONFIG_VIEW'),
      I('周报规则', '/admin/internship/batches?panel=rules&rule=report', 'internship.batch.rule.report.manage', 'CONFIG_VIEW'),
      I('指导规则', '/admin/internship/batches?panel=rules&rule=guidance', 'internship.batch.rule.guidance.manage', 'CONFIG_VIEW'),
      I('评价规则', '/admin/internship/batches?panel=rules&rule=evaluation', 'internship.batch.rule.evaluation.manage', 'CONFIG_VIEW'),
      I('成绩规则', '/admin/internship/batches?panel=rules&rule=score', 'internship.batch.rule.score.manage', 'CONFIG_VIEW')
    ]),
    mod('in-students', '实习学生', '/admin/internship/students', [
      I('实习名单', '/admin/internship/students?panel=roster', 'internship.student.view', 'WORKBENCH'),
      I('实习资格认定', '/admin/internship/students?panel=eligibility', 'internship.student.eligibility.review', 'TASK_QUEUE'),
      I('学生实习状态', '/admin/internship/students?panel=status', 'internship.student.view', 'WORKBENCH'),
      H('学生实习详情', '/admin/internship/students?panel=roster', 'internship.student.view', 'DETAIL'),
      I('学生材料', '/admin/internship/archive?panel=materials', 'internship.student.material.view', 'WORKBENCH'),
      I('实习保险核验', '/admin/internship/insurance', 'internship.insurance.verify', 'TASK_QUEUE')
    ]),
    mod('in-enterprise-position', '企业与岗位', '/admin/internship/enterprises', [
      I('企业列表', '/admin/internship/enterprises?panel=list', 'internship.enterprise.view', 'WORKBENCH'),
      H('企业详情', '/admin/internship/enterprises?panel=detail', 'internship.enterprise.view', 'DETAIL'),
      I('企业联系人', '/admin/internship/enterprises?panel=contacts', 'internship.enterprise.contact.view', 'WORKBENCH'),
      I('企业导师', '/admin/internship/enterprises?panel=mentor', 'internship.enterprise.mentor.view', 'WORKBENCH'),
      I('企业资质审核', '/admin/internship/enterprises?panel=qualification', 'internship.enterprise.review', 'TASK_QUEUE'),
      I('企业黑名单', '/admin/internship/enterprises?panel=blacklist', 'internship.enterprise.blacklist.manage', 'TASK_QUEUE'),
      I('岗位列表', '/admin/internship/positions?panel=list', 'internship.position.view', 'WORKBENCH'),
      H('岗位详情', '/admin/internship/positions?panel=detail', 'internship.position.view', 'DETAIL'),
      I('岗位发布', '/admin/internship/positions?panel=publish', 'internship.position.publish', 'TASK_QUEUE'),
      I('岗位专业匹配', '/admin/internship/positions?panel=requirement', 'internship.position.match.view', 'CONFIG_VIEW')
    ]),
    mod('in-match-assign', '匹配与分配', '/admin/internship/match', [
      I('学生意向', '/admin/internship/match?panel=intention', 'internship.match.intention.view', 'WORKBENCH'),
      I('岗位推荐', '/admin/internship/match?panel=recommend', 'internship.match.recommend.view', 'ANALYTICS_VIEW'),
      I('手动匹配', '/admin/internship/match?panel=manual', 'internship.match.manual', 'TASK_QUEUE'),
      I('批量匹配', '/admin/internship/match?panel=batch', 'internship.match.batch', 'TASK_QUEUE'),
      I('匹配冲突', '/admin/internship/match?panel=conflict', 'internship.match.conflict.view', 'TASK_QUEUE'),
      I('匹配结果', '/admin/internship/match?panel=results', 'internship.match.result.view', 'WORKBENCH'),
      I('指导老师分配', '/admin/internship/students?panel=mentor', 'internship.match.advisor.assign', 'TASK_QUEUE'),
      I('调岗退岗', '/admin/internship/changes?panel=pending', 'internship.change.review', 'TASK_QUEUE'),
      I('分配日志', '/admin/internship/assignment-logs', 'internship.match.log.view', 'ANALYTICS_VIEW')
    ]),
    mod('in-apply-agreement', '申请与协议', '/admin/internship/agreements', [
      I('学生申请', '/admin/internship/applications?status=PENDING_REVIEW', 'internship.application.review', 'TASK_QUEUE'),
      I('自主实习申请', '/admin/internship/applications?status=PENDING_REVIEW&type=SELF_ARRANGED', 'internship.application.review', 'TASK_QUEUE'),
      I('岗位申请', '/admin/internship/applications?status=PENDING_REVIEW&type=POSITION', 'internship.application.review', 'TASK_QUEUE'),
      I('审核台账', '/admin/internship/applications?status=ALL', 'internship.application.view', 'ANALYTICS_VIEW'),
      I('协议模板', '/admin/internship/agreement-templates', 'internship.agreement.template.manage', 'CONFIG_VIEW'),
      I('协议发起', '/admin/internship/agreements?panel=issue', 'internship.agreement.issue', 'TASK_QUEUE'),
      I('三方确认', '/admin/internship/agreements?panel=confirm', 'internship.agreement.school_confirm', 'TASK_QUEUE'),
      I('协议变更', '/admin/internship/agreements?panel=change', 'internship.agreement.change', 'TASK_QUEUE'),
      I('协议归档', '/admin/internship/agreements?panel=archive', 'internship.agreement.archive', 'TASK_QUEUE')
    ]),
    mod('in-attendance-leave', '打卡与请假', '/admin/internship/attendance', [
      I('打卡记录', '/admin/internship/attendance?panel=checkins', 'internship.attendance.view', 'WORKBENCH'),
      I('补卡申请台账', '/admin/internship/attendance?panel=makeup-apply', 'internship.makeup.view', 'WORKBENCH'),
      I('补卡审批', '/admin/internship/attendance?panel=makeup-review', 'internship.makeup.review', 'TASK_QUEUE'),
      I('缺卡异常', '/admin/internship/attendance?panel=exceptions', 'internship.attendance.exception.handle', 'TASK_QUEUE'),
      I('连续未打卡', '/admin/internship/exceptions?status=PENDING_HANDLE', 'internship.attendance.exception.handle', 'TASK_QUEUE'),
      I('请假台账', '/admin/internship/leaves?panel=all', 'internship.leave.view', 'WORKBENCH'),
      I('请假审批', '/admin/internship/leaves?panel=pending', 'internship.leave.review', 'TASK_QUEUE'),
      I('销假管理', '/admin/internship/leaves?panel=approved', 'internship.leave.resume', 'TASK_QUEUE'),
      I('超期未归', '/admin/internship/risks?panel=leave-overdue', 'internship.risk.view', 'TASK_QUEUE')
    ]),
    mod('in-weekly-task', '周报与任务', '/admin/internship/reports', [
      I('实习计划', '/admin/internship/plans', 'internship.plan.view', 'CONFIG_VIEW'),
      I('实习任务', '/admin/internship/plans?panel=tasks', 'internship.task.view', 'WORKBENCH'),
      I('日报台账', '/admin/internship/reports?type=daily&panel=all', 'internship.report.view', 'WORKBENCH'),
      I('周报台账', '/admin/internship/reports?panel=all', 'internship.report.view', 'WORKBENCH'),
      I('月报台账', '/admin/internship/reports?type=monthly&panel=all', 'internship.report.view', 'WORKBENCH'),
      I('周报批阅', '/admin/internship/reports?panel=review', 'internship.report.review', 'TASK_QUEUE'),
      I('周报退回', '/admin/internship/reports?panel=returned', 'internship.report.review', 'TASK_QUEUE'),
      H('周报问题', '/admin/internship/reports?panel=issues', 'internship.report.issue.handle', 'TASK_QUEUE')
    ]),
    mod('in-guidance-visit', '指导与巡访', '/admin/internship/guidance', [
      I('指导计划', '/admin/internship/guidance-plan', 'internship.guidance.plan.manage', 'CONFIG_VIEW'),
      I('指导记录', '/admin/internship/guidance?panel=guidance', 'internship.guidance.record.create', 'WORKBENCH'),
      I('企业沟通', '/admin/internship/guidance?panel=communication', 'internship.communication.view', 'WORKBENCH'),
      I('指导不足预警', '/admin/internship/guidance-plan?insufficient=1', 'internship.guidance.insufficient.view', 'TASK_QUEUE'),
      I('巡访计划', '/admin/internship/guidance?panel=visit&view=plan', 'internship.visit.plan.manage', 'CONFIG_VIEW'),
      I('巡访记录', '/admin/internship/guidance?panel=visit&view=record', 'internship.visit.record.create', 'WORKBENCH'),
      I('巡访问题', '/admin/internship/guidance?panel=visit&view=issue', 'internship.visit.issue.handle', 'TASK_QUEUE'),
      I('整改跟进', '/admin/internship/guidance?panel=rectify', 'internship.visit.rectify.handle', 'TASK_QUEUE')
    ]),
    mod('in-risk', '风险处置', '/admin/internship/risks', [
      I('风险看板', '/admin/internship/risks?panel=board', 'internship.risk.view', 'WORKBENCH'),
      I('未落实岗位', '/admin/internship/risks?panel=no-position', 'internship.risk.view', 'TASK_QUEUE'),
      I('长期未打卡', '/admin/internship/risks?panel=no-checkin', 'internship.risk.view', 'TASK_QUEUE'),
      I('周报逾期', '/admin/internship/risks?panel=report-overdue', 'internship.risk.view', 'TASK_QUEUE'),
      I('离岗异常', '/admin/internship/risks?panel=off-post', 'internship.risk.view', 'TASK_QUEUE'),
      I('企业投诉', '/admin/internship/risk-disposal?caseType=complaint', 'internship.complaint.intake', 'TASK_QUEUE'),
      I('安全风险', '/admin/internship/risk-disposal?panel=safety', 'internship.risk.handle', 'TASK_QUEUE'),
      I('实习中断', '/admin/internship/risk-disposal?panel=interrupt', 'internship.risk.handle', 'TASK_QUEUE'),
      I('风险处置', '/admin/internship/risk-disposal?stage=pending', 'internship.risk.handle', 'TASK_QUEUE'),
      I('风险跟进', '/admin/internship/risk-disposal?stage=processing', 'internship.risk.handle', 'TASK_QUEUE'),
      I('风险关闭', '/admin/internship/risk-disposal?stage=closed', 'internship.risk.close', 'TASK_QUEUE')
    ]),
    mod('in-eval-score', '评价与成绩', '/admin/internship/enterprise-evals', [
      I('企业评价', '/admin/internship/enterprise-evals', 'internship.eval.enterprise.view', 'WORKBENCH'),
      I('学生自评台账', '/admin/internship/student-evals?view=self', 'internship.eval.self.view', 'WORKBENCH'),
      I('学生对企业评价', '/admin/internship/student-evals?view=enterprise', 'internship.eval.enterprise_by_student.view', 'ANALYTICS_VIEW'),
      I('学生对岗位评价', '/admin/internship/student-evals?view=position', 'internship.eval.position_by_student.view', 'ANALYTICS_VIEW'),
      I('指导老师评价', '/admin/internship/student-evals?view=advisor', 'internship.eval.advisor.manage', 'TASK_QUEUE'),
      I('综合成绩', '/admin/internship/scores?stage=overview', 'internship.score.view', 'WORKBENCH'),
      I('成绩审核', '/admin/internship/scores?stage=review', 'internship.score.review', 'TASK_QUEUE'),
      I('成绩发布', '/admin/internship/scores?stage=publish', 'internship.score.publish', 'TASK_QUEUE'),
      I('成绩复核', '/admin/internship/scores?stage=recheck', 'internship.score.recheck', 'TASK_QUEUE')
    ]),
    mod('in-employment-archive-stats', '就业转化与归档统计', '/admin/internship/archive', [
      I('就业跟进', '/admin/employment?panel=follow-up', 'internship.employment.view', 'CROSS_MODULE'),
      I('未就业帮扶', '/admin/employment?panel=assistance', 'internship.employment.view', 'CROSS_MODULE'),
      I('实习归档', '/admin/internship/archive?panel=records', 'internship.archive.manage', 'WORKBENCH'),
      H('实习档案包', '/admin/internship/archive?panel=packages', 'internship.archive.package.generate', 'ACTION'),
      I('实习统计', '/admin/internship/stats?dimension=overview', 'internship.stats.view', 'ANALYTICS_VIEW'),
      I('企业统计', '/admin/internship/stats?dimension=enterprise', 'internship.stats.enterprise.view', 'ANALYTICS_VIEW'),
      I('岗位统计', '/admin/internship/stats?dimension=position', 'internship.stats.position.view', 'ANALYTICS_VIEW'),
      I('学生成绩统计', '/admin/internship/stats?dimension=score', 'internship.stats.score.view', 'ANALYTICS_VIEW')
    ])
  ]),

  /* ═══════════ 一级⑥：系统管理 ═══════════
     学校级仅保留 8 组 / 26 个三级能力。平台租户、套餐、全局菜单及权限点目录
     一律留在 PLATFORM_PLAN，避免学校管理员越权和两套角色权限重复维护。 */
  grp('system', '系统管理', 'systemAdmin', SYSTEM_MANAGEMENT_CATALOG.map((group) =>
    mod(group.key, group.label, group.items[0].path, group.items.map((item) =>
      I(item.label, item.path, item.permissionKey, 'CONFIG_VIEW', {
        systemCapabilityKey: item.key,
        systemCapabilityGroup: group.key,
        description: item.description
      })
    ))
  ))
]

/**
 * 平台运营（隐藏一级，仅平台超管可见；不属学校侧 6 个一级）。
 * 单列，避免混入学校导航；仅登记已实现页面，保持旧路由可访问。
 */
export const PLATFORM_PLAN = grp('platform', '平台运营', 'platform', PLATFORM_MANAGEMENT_CATALOG.map((group) =>
  mod(group.key, group.label, group.items[0].path, group.items.map((item) =>
    I(item.label, item.path, item.permissionKey, 'CONFIG_VIEW', {
      platformCapabilityKey: item.key,
      platformCapabilityGroup: group.key,
      description: item.description
    })
  ))
), { platformOnly: true })

/* 平台运营不混入学校侧 NAV_PLAN 导出，但 BasePortalLayout 需要它完成平台二、三级导航投影。 */
const NAV_PLAN_WITH_PLATFORM = [...NAV_PLAN, PLATFORM_PLAN]

/* ── 规划占位页路径分配（CLAUDE.md §42，2026-07-11 甲方拍板）──────────────
 * planned 且无 path 的三级叶子，统一分配公共占位页路由：
 *   /admin/planned/<一级groupKey>/<二级modKey>/<叶子序号>
 * 叶子保持 disabled=true（侧栏仍描灰、badge 仍「待施工」），点击行为由
 * BasePortalLayout.onPlanLeaf 判定：planned+有 path → 进占位页；「未开通」→ 仍 toast。
 * 占位页只展示 navPlan + 施工图规划信息，无假按钮、无假数据、无业务 API（§42）。 */
for (const group of NAV_PLAN) {
  for (const m of group.children) {
    m.children.forEach((leaf, i) => {
      if (leaf.status === 'planned' && !leaf.path) {
        leaf.path = `/admin/planned/${group.key}/${m.key}/${i}`
      }
    })
  }
}

/**
 * 按角色可见性过滤规划树。
 * @param {object} opts.includePlanned 管理员/开发者视角=true（可见 planned），普通业务角色=false（隐藏 planned）
 * @returns {Array} 过滤后的规划树（planned 节点在 includePlanned=false 时剔除）
 */
/** 权限码模式匹配（与后端 permissions._match 同构：`*` 全放行 / `a.b.*` 前缀 / `*.view` 后缀）。
 *  角色只作默认模板，最终以 permissionKey 是否命中当前身份权限集为准（对齐 07 整改方案 §6.3）。 */
export function matchPermission(patterns, code) {
  if (!Array.isArray(patterns) || !code) return false
  for (const p of patterns) {
    if (p === '*' || p === code) return true
    if (p.endsWith('.*') && (code === p.slice(0, -2) || code.startsWith(p.slice(0, -1)))) return true
    if (p.startsWith('*.') && code.endsWith(p.slice(1))) return true
  }
  return false
}

const _navPlanVisibleCache = new Map()
/**
 * 按角色可见性过滤规划树。
 * @param {boolean} opts.includePlanned 管理员/开发者(planner)视角=true（见 planned + 完整能力目录，不做权限投影）；普通业务角色=false
 * @param {string[]|null} opts.permissionPatterns 当前身份权限码模式集（来自后端 current-context）；日常视角据此投影，未命中 permissionKey 的叶子隐藏
 * @param {string} opts.ctxKey 身份缓存签名（tenantId+contextId+permissionVersion），避免跨身份/跨租户缓存污染
 */
export function getVisibleNavPlan({ includePlanned = false, permissionPatterns = null, ctxKey = '' } = {}) {
  const cacheKey = `${includePlanned ? '1' : '0'}|${ctxKey}`
  if (_navPlanVisibleCache.has(cacheKey)) return _navPlanVisibleCache.get(cacheKey)
  // 日常业务视角：按当前身份权限集投影，叶子声明 permissionKey 未命中即隐藏；
  // planner/能力地图视角：展示完整能力目录，不做权限投影（仅对被授权的实施管理员开放，由调用方把关）。
  // hidden 叶子：任何视角都不进菜单（详情/动作/旧兼容入口），仅保留路由与高亮。
  const applyPerm = !includePlanned && Array.isArray(permissionPatterns)
  const keepLeaf = (leaf) => {
    if (leaf.hidden) return false
    if (!(includePlanned || leaf.status === 'implemented' || leaf.status === 'partial')) return false
    if (applyPerm && leaf.permissionKey && !matchPermission(permissionPatterns, leaf.permissionKey)) return false
    return true
  }
  const keepMod = (mod2) => {
    if (mod2.children.length === 0) return includePlanned || mod2.status === 'implemented' || mod2.status === 'partial'
    if (mod2.children.some(keepLeaf)) return true
    return includePlanned && (mod2.status === 'implemented' || mod2.status === 'partial')
  }
  const result = NAV_PLAN_WITH_PLATFORM.map((group) => ({
    ...group,
    children: group.children
      .filter(keepMod)
      .map((mod2) => ({ ...mod2, children: mod2.children.filter(keepLeaf) }))
  })).filter((group) => group.children.length > 0)
  _navPlanVisibleCache.set(cacheKey, result)
  return result
}

/**
 * 拆分 navPlan path（可含 ?query）。
 */
export function splitNavRef(ref) {
  if (!ref) return { path: '', query: '' }
  const q = ref.indexOf('?')
  if (q === -1) return { path: ref, query: '' }
  return { path: ref.slice(0, q), query: ref.slice(q + 1) }
}

/** 同一组 query 参数在 router 序列化时顺序可能变化；排序后再比较，避免菜单高亮和重复点击误判。 */
function normalizeNavQuery(query) {
  if (!query) return ''
  return query
    .split('&')
    .filter(Boolean)
    .map((item) => {
      const eq = item.indexOf('=')
      return eq === -1 ? [item, ''] : [item.slice(0, eq), item.slice(eq + 1)]
    })
    .sort(([aKey, aValue], [bKey, bValue]) => aKey.localeCompare(bKey) || aValue.localeCompare(bValue))
    .map(([key, value]) => (value === '' ? key : `${key}=${value}`))
    .join('&')
}

/** 列表页无 panel 参数时的默认三级高亮 */
const DEFAULT_PANEL_BY_PATH = {
  '/admin/internship/students': 'roster',
  '/admin/internship/batches': 'list',
  '/admin/internship/enterprises': 'list',
  '/admin/internship/positions': 'list',
  '/admin/internship/match': 'intention',
  '/admin/internship/guidance': 'guidance',
  '/admin/graduation/students': 'roster',
  '/admin/graduation/batches': 'list',
  '/admin/graduation/topic-lib': 'list',
  '/admin/graduation/topic-rounds': 'rounds',
  '/admin/graduation/mentors': 'list',
  '/admin/graduation/process': 'taskbook',
  '/admin/graduation/defense-grade': 'plagiarism',
  '/admin/graduation/risk-archive': 'risk'}

export function normalizeNavRef(fullPath) {
  const ref = (fullPath || '').split('#')[0]
  const { path, query } = splitNavRef(ref)
  const fallback = DEFAULT_PANEL_BY_PATH[path]
  if (fallback && !query) return `${path}?panel=${fallback}`
  const normalizedQuery = normalizeNavQuery(query)
  return normalizedQuery ? `${path}?${normalizedQuery}` : path
}

/** 完整 URL 是否精确命中菜单 ref（含 query；列表页默认 panel 等价），禁止前缀误判 */
export function navRefExactMatch(currentRef, candidateRef) {
  if (!candidateRef) return false
  return normalizeNavRef(currentRef) === normalizeNavRef(candidateRef)
}

/** 当前路由是否命中某菜单 ref（path + query） */
export function navRefMatches(currentRef, candidateRef) {
  const cur = splitNavRef(normalizeNavRef(currentRef))
  const cand = splitNavRef(candidateRef)
  if (cand.path === '/') return cur.path === '/'
  if (cand.query) return cur.path === cand.path && cur.query === cand.query
  const { path: curPath } = cur
  return curPath === cand.path || curPath.startsWith(`${cand.path}/`)
}

/**
 * NAV_PLAN 拍平索引（模块加载时只构建一次）。
 * findActiveInPlan / searchNavPlan 原来都是「每次调用都重新嵌套遍历整棵树」，
 * 随着规划的模块越来越多，每次路由切换 / 每次按键搜索都要重新扫一遍全树，会越用越慢。
 * 这里预先拍平成一个扁平数组，两个函数只做单层遍历，匹配逻辑与原实现逐字对齐、不改变任何结果。
 */
const FLAT_NAV_INDEX = (() => {
  const rows = []
  for (const group of NAV_PLAN_WITH_PLATFORM) {
    for (const mod2 of group.children) {
      rows.push({
        groupKey: group.key,
        groupLabel: group.label,
        modKey: mod2.key,
        modLabel: mod2.label,
        label: mod2.label,
        path: mod2.path || null,
        status: mod2.status,
        disabled: mod2.disabled,
        badge: mod2.badge,
        isLeaf: false,
        hidden: false
      })
      mod2.children.forEach((leaf, i) => {
        rows.push({
          groupKey: group.key,
          groupLabel: group.label,
          modKey: mod2.key,
          modLabel: mod2.label,
          leafKey: `${mod2.key}:${i}`,
          label: leaf.label,
          path: leaf.path || null,
          status: leaf.status,
          disabled: leaf.disabled,
          badge: leaf.badge,
          isLeaf: true,
          hidden: !!leaf.hidden,
          permissionKey: leaf.permissionKey || null
        })
      })
    }
  }
  return rows
})()

/**
 * 依当前路由在规划树中定位所属 一级/二级/三级（用于侧栏高亮）。
 * @param {string} path 路由 path
 * @param {string} [fullPath] 含 query 的完整路径（三级菜单带 ?panel= 时必须）
 * @returns {{groupKey:string, modKey:string, leafKey:string}}
 */
export function findActiveInPlan(path, fullPath = '') {
  if (!path) return { groupKey: '', modKey: '', leafKey: '' }
  const ref = normalizeNavRef(fullPath || path)
  let best = { groupKey: '', modKey: '', leafKey: '', score: -1 }
  for (const row of FLAT_NAV_INDEX) {
    if (!row.path) continue
    let score = -1
    if (navRefMatches(ref, row.path)) {
      const cand = splitNavRef(row.path)
      const cur = splitNavRef(ref)
      const prefixOnly = !cand.query && cur.path !== cand.path && cur.path.startsWith(`${cand.path}/`)
      if (prefixOnly) {
        // 父路径（如 /admin/internship）不可抢占子路由高亮
        score = cand.path.length - 500
      } else {
        score = row.path.length + (cand.query ? 1000 : 0)
      }
    } else {
      const { path: cp, query: cq } = splitNavRef(row.path)
      if (!cq && (cp === '/' ? path === '/' : path === cp || path.startsWith(`${cp}/`))) {
        score = cp.length
      }
    }
    if (score > best.score) {
      best = { groupKey: row.groupKey, modKey: row.modKey, leafKey: row.isLeaf ? row.label : '', score }
    }
  }
  return { groupKey: best.groupKey, modKey: best.modKey, leafKey: best.leafKey }
}

/**
 * 搜索规划菜单：命中 planned 时 disabled=true（前端只提示「待施工」，不跳转）。
 * @param {string} query
 * @returns {Array} [{ label, path, status, disabled, badge, trail }]
 */
const _navSearchCache = new Map()
export function searchNavPlan(query, permissionPatterns = null) {
  const q = (query || '').trim().toLowerCase()
  if (!q) return []
  const applyPerm = Array.isArray(permissionPatterns)
  // 缓存键含权限签名：不同身份的搜索结果不得互相污染（禁止无权限页面被搜索命中并跳转）。
  const cacheKey = applyPerm ? `${q}|${permissionPatterns.slice().sort().join(',')}` : q
  if (_navSearchCache.has(cacheKey)) return _navSearchCache.get(cacheKey)
  const out = []
  for (const row of FLAT_NAV_INDEX) {
    if (row.hidden) continue  // 隐藏的兼容入口不进搜索
    if (applyPerm && row.permissionKey && !matchPermission(permissionPatterns, row.permissionKey)) continue  // 无权限页面不进搜索
    if (!row.label.toLowerCase().includes(q)) continue
    out.push({
      label: row.label,
      path: row.path,
      status: row.status,
      disabled: row.disabled,
      badge: row.badge,
      trail: row.isLeaf ? `${row.groupLabel} / ${row.modLabel} / ${row.label}` : `${row.groupLabel} / ${row.label}`
    })
    if (out.length >= 20) break  // 与原 slice(0, 20) 结果一致（同一遍历顺序），提前终止避免扫完全表
  }
  if (_navSearchCache.size > 64) _navSearchCache.clear()
  _navSearchCache.set(cacheKey, out)
  return out
}

/** 统计：各一级下 implemented / planned 数量（供校验报告与开发进度看板用） */
export function navPlanStats() {
  return NAV_PLAN.map((group) => {
    let impl = 0
    let planned = 0
    for (const mod2 of group.children) {
      const nodes = [mod2, ...mod2.children]
      for (const nd of nodes) {
        if (nd.status === 'implemented') impl++
        else planned++
      }
    }
    return { key: group.key, label: group.label, implemented: impl, planned, total: impl + planned }
  })
}

export default NAV_PLAN
