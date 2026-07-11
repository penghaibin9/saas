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

/** 已实现叶子（带真实 path） */
function I(label, path) {
  return { label, path, status: 'implemented', disabled: false, badge: '' }
}
/** 待施工叶子（可批量），自动 disabled + 待施工 badge，无 path 不注册路由 */
function P(...labels) {
  return labels.map((label) => ({ label, status: 'planned', disabled: true, badge: '待施工' }))
}
/** 待补强叶子（有旧页面但能力较浅，可点击进旧页面） */
// eslint-disable-next-line no-unused-vars
function PA(label, path) {
  return { label, path, status: 'partial', disabled: false, badge: '待补强' }
}
/** 未开通叶子（模块未授权，管理员可见「未开通」，普通角色隐藏） */
// eslint-disable-next-line no-unused-vars
function UN(label) {
  return { label, status: 'unauthorized', disabled: true, badge: '未开通' }
}
/** 隐藏叶子（真实页面但不进正常菜单/搜索：详情工作区、页内入口页；仅用于侧栏归属高亮） */
function H(label, path) {
  return { label, path, status: 'implemented', disabled: false, badge: '', hidden: true }
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
    mod('sa-dashboard', '学工看板', null, P(
      '学工总览', '今日待办', '辅导员待办', '学生风险概览', '请假审批概览', '奖助进度概览',
      '宿舍异常概览', '心理关注概览', '违纪处分概览', '学工数据趋势', '重点学生提醒', '待归档材料提醒'
    )),
    mod('sa-profile', '学生画像', '/admin/student', [
      I('学生主档', '/admin/student/list'),
      ...P('基础信息'),
      I('学籍状态摘要', '/admin/student/status'),
      ...P('班级信息', '家庭与联系人', '家校联系记录', '奖助信息摘要', '请假记录摘要',
        '宿舍信息摘要', '处分记录摘要', '心理关注摘要'),
      I('风险标签', '/admin/student/risk-tags'),
      ...P('成长档案', '材料归档'),
      I('信息更正审核', '/admin/student/corrections'),
      ...P('数据变更日志'),
      I('身份核验（现有）', '/admin/student/identity'),
      I('导入导出（现有）', '/admin/student/import-export')
    ]),
    mod('sa-classes', '班级管理', null, [
      I('班级列表', '/admin/campus-service/classes'),
      // 班级画像/学生名单/班级材料/班干部 = 班级列表点入的画像独立页 Tab（param 路由，无独立菜单）
      ...P('班级详情', '班级学生', '辅导员绑定', '班主任绑定', '班干部管理', '班级通讯录',
        '班级风险概览', '班级请假统计', '班级宿舍统计', '班级奖助统计', '班级活动统计', '班级档案')
    ]),
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
    mod('sa-leave', '请假销假', null, [
      ...P('请假看板', '请假申请', '续假申请'),
      I('请假审批', '/admin/campus-service/leave'),
      I('续假审批', '/admin/campus-service/leave-extensions'),
      I('销假管理', '/admin/campus-service/leave-extensions'),
      ...P('归寝核验', '长假审批', '外出备案', '请假异常', '超期未销假', '请假规则配置'),
      I('请假台账', '/admin/campus-service/leave-ledger'),
      I('请假统计', '/admin/campus-service/leave-stats'),
      ...P('请假归档')
    ]),
    mod('sa-difficulty', '困难认定', null, P(
      '认定批次', '学生申请', '材料上传', '材料审核', '辅导员初审', '班级民主评议', '学院审核',
      '学校复核', '公示管理', '异议处理', '认定结果', '困难等级调整', '认定台账', '认定统计', '材料归档'
    )),
    mod('sa-aid', '奖助勤贷补', null, [
      ...P('奖助看板', '奖学金管理'),
      I('助学金管理（现有·奖助资助）', '/admin/campus-service/grants'),
      ...P('国家奖学金', '国家励志奖学金', '校级奖学金', '勤工助学岗位', '勤工报名审核', '助学贷款',
        '学费减免', '临时困难补助', '绿色通道', '名单公示', '发放台账', '异议处理', '奖助统计', '奖助归档')
    ]),
    mod('sa-discipline', '违纪处分', null, [
      I('违纪登记（现有）', '/admin/campus-service/discipline'),
      ...P('调查取证', '处分审批', '处分决定', '处分送达', '处分公示', '处分台账', '处分解除申请',
        '处分解除审核', '学生申诉', '复核处理', '处分统计', '处分归档')
    ]),
    mod('sa-mental', '心理健康', null, P(
      '心理看板', '心理测评', '测评结果', '重点关注学生', '咨询预约', '咨询记录', '危机预警',
      '危机干预', '转介记录', '回访记录', '心理活动', '心理档案', '心理权限审计', '心理统计'
    )),
    mod('sa-risk', '风险预警', null, P(
      '风险看板', '风险学生', '学业风险摘要', '请假异常风险', '夜不归宿风险', '心理关注风险',
      '违纪风险', '经济困难风险', '实习异常风险', '多维风险合并', '风险处置', '风险跟进',
      '风险关闭', '风险规则配置', '风险统计'
    )),
    mod('sa-talks', '谈心谈话', null, P(
      '谈话计划', '谈话记录', '重点学生谈话', '风险学生谈话', '家校联动谈话', '谈话跟进',
      '待回访学生', '批量导入谈话', '谈话统计', '谈话归档'
    )),
    mod('sa-home-school', '家校联系', null, P(
      '家长信息', '联系人维护', '联系记录', '家校通知', '通知回执', '紧急联系',
      '重点学生家校沟通', '家长授权记录', '家校联系统计', '家校材料归档'
    )),
    mod('sa-dorm', '宿舍管理', null, [
      ...P('宿舍看板', '楼栋管理', '房间管理', '床位管理'),
      I('入住管理（现有·宿舍服务）', '/admin/campus-service/dormitory'),
      ...P('退宿管理', '调宿申请', '调宿审批', '宿舍检查', '夜不归宿', '公寓纪律', '宿舍维修',
        '文明寝室', '宿舍异常', '宿舍统计', '宿舍归档')
    ]),
    mod('sa-activities', '学生活动', null, P(
      '活动看板', '活动发布', '活动报名', '报名审核', '活动签到', '活动请假',
      '活动材料', '活动评价', '活动积分', '活动统计', '活动归档'
    )),
    mod('sa-second-class', '第二课堂', null, P(
      '第二课堂看板', '项目库', '项目发布', '学生报名', '签到认定', '积分规则', '积分审核',
      '积分台账', '学生积分查询', '积分申诉', '证书生成', '第二课堂统计', '第二课堂归档'
    )),
    mod('sa-clubs', '社团与学生组织', null, P(
      '社团列表', '社团成员', '社团活动', '社团审核', '社团换届', '学生会组织',
      '学生干部', '组织考核', '经费记录', '社团统计', '社团归档'
    )),
    mod('sa-party', '党团建设', null, P(
      '团员管理', '团组织管理', '主题团日', '推优入党', '入党积极分子', '党团活动',
      '思政活动', '党团统计', '党团归档'
    )),
    mod('sa-counselor-eval', '辅导员考评', null, [
      I('考评看板', '/admin/campus-service/counselor-assessment'),
      ...P('工作量统计', '谈话记录统计', '宿舍走访统计', '风险处置统计', '请假审批统计',
        '班级建设统计', '学生满意度', '学院评分', '考评结果', '考评归档')
    ]),
    mod('sa-archive', '学工归档', null, P(
      '归档看板', '学生个人归档', '班级归档', '奖助归档', '处分归档', '心理归档', '请假归档',
      '宿舍归档', '活动归档', '归档缺失提醒', '批量归档', '归档导出', '归档审计'
    )),
    mod('sa-stats', '学工统计', null, P(
      '学工总览', '学生结构统计', '请假统计', '奖助统计', '困难学生统计', '宿舍统计', '心理关注统计',
      '违纪处分统计', '活动统计', '第二课堂统计', '风险学生统计', '辅导员工作统计', '学院对比分析', '导出报表'
    )),
    /* 现有「在校服务」中无对应新二级的页面，保留可访问（旧路由不 404） */
    mod('sa-legacy-service', '在校服务（现有·过渡）', '/admin/campus-service', [
      I('服务工作台', '/admin/campus-service'),
      I('学生服务', '/admin/campus-service/students'),
      I('服务工单', '/admin/campus-service/work-orders')
    ])
  ]),

  /* ═══════════ 一级③：教务中心 ═══════════ */
  grp('academic-affairs', '教务中心', 'academicAffairs', [
    mod('aa-dashboard', '教务看板', '/admin/academic', [
      I('教务总览（学业过程中心）', '/admin/academic'),
      ...P('今日教学运行', '今日课程', '调停课提醒', '成绩提交进度', '考试安排提醒',
        '学籍异动提醒', '学业预警提醒', '毕业资格预警', '教学资源占用', '教务待办', '教务数据趋势')
    ]),
    mod('aa-terms', '学年学期', null, P('学年管理', '学期管理', '当前学期设置', '学期周次', '教学周配置', '学期状态', '学期切换记录', '学期归档')),
    mod('aa-calendar', '校历节次', null, P('校历管理', '节假日配置', '补课日配置', '作息时间', '节次管理', '上课时间段', '教学周日历', '校历发布', '校历归档')),
    mod('aa-student-status', '学籍管理', null, [
      ...P('学籍档案', '学籍状态'),
      I('在籍学生（现有·学业学生）', '/admin/academic/students'),
      ...P('休学学生', '复学学生', '退学学生', '转专业学生', '保留学籍', '学籍信息更正',
        '学籍异动记录', '学籍导入导出', '学籍统计', '学籍归档')
    ]),
    mod('aa-registration', '注册管理', null, P('入学注册', '学年注册', '学期注册', '注册资格核验', '未注册学生', '暂缓注册', '注册异常', '注册统计', '注册归档')),
    mod('aa-status-change', '学籍异动', null, P('异动申请', '休学申请', '复学申请', '退学申请', '转专业申请', '转班申请', '保留学籍申请', '异动审批', '异动生效', '异动台账', '异动统计', '异动归档')),
    mod('aa-orgs', '学院专业班级', null, P('学院管理', '专业管理', '年级管理', '行政班管理', '教学班管理', '专业方向', '班级学生', '班级调整', '组织结构同步', '组织统计')),
    mod('aa-training', '培养方案', null, P('方案列表', '方案制定', '方案版本', '课程模块', '学分要求', '实践环节', '毕业要求', '方案审核', '方案发布', '方案变更', '方案归档')),
    mod('aa-courses', '课程库', null, P('课程列表', '新增课程', '课程分类', '课程性质', '学分学时', '课程大纲', '考核方式', '课程负责人', '课程材料', '课程停用', '课程归档')),
    mod('aa-teaching-plan', '教学计划', null, P('年级教学计划', '专业教学计划', '学期教学计划', '课程开设计划', '实践教学计划', '计划审核', '计划发布', '计划变更', '计划执行进度', '计划归档')),
    mod('aa-teaching-tasks', '教学任务', null, P('教学任务生成', '教学任务列表', '任课教师分配', '教学班生成', '合班拆班', '教学任务确认', '教师任务确认', '教学任务调整', '教学任务统计', '教学任务归档')),
    mod('aa-scheduling', '排课管理', null, P('排课批次', '排课规则', '排课约束', '教师可用时间', '教室可用时间', '课程排课', '自动排课预留', '人工排课', '排课冲突检测', '排课结果', '排课调整', '排课发布', '排课归档')),
    mod('aa-schedule', '课表管理', null, P('班级课表', '教师课表', '学生课表', '教室课表', '教学班课表', '周课表', '学期课表', '课表发布', '课表调整记录', '课表导出')),
    mod('aa-schedule-change', '调停课', null, P('调课申请', '停课申请', '补课申请', '调停课审批', '调停课通知', '调停课台账', '调停课冲突检测', '调停课统计', '调停课归档')),
    mod('aa-course-selection', '选课管理', null, P('选课批次', '可选课程', '选课规则', '学生选课', '退课管理', '补选管理', '选课名单', '人数控制', '冲突检测', '选课结果', '选课统计', '选课归档')),
    mod('aa-exam', '考务管理', null, P('考试批次', '考试课程', '考试安排', '考场安排', '座位安排', '监考安排', '巡考安排', '准考证', '考场异常', '考务通知', '考务统计', '考务归档')),
    mod('aa-makeup', '补考重修缓考免修', null, [
      ...P('补考名单', '补考报名', '补考安排', '重修报名', '重修班管理', '缓考申请', '缓考审批', '免修申请', '免修审批'),
      I('补考重修成绩（现有）', '/admin/academic/makeup-retake'),
      ...P('统计分析', '材料归档')
    ]),
    mod('aa-grades', '成绩管理', null, [
      ...P('成绩录入', '成绩暂存', '成绩提交', '成绩审核', '成绩发布'),
      I('成绩查询（现有·课程成绩）', '/admin/academic/grades'),
      I('学分修读（现有）', '/admin/academic/credits'),
      ...P('成绩单', '成绩导入', '成绩导出', '成绩异常', '成绩统计', '成绩归档')
    ]),
    mod('aa-grade-review', '成绩审核发布更正', null, P('待审核成绩', '审核通过', '审核退回', '成绩发布', '成绩更正申请', '成绩更正审核', '成绩复核', '成绩更正记录', '成绩操作审计', '成绩发布归档')),
    mod('aa-warning', '学业预警', null, [
      ...P('预警看板', '学分预警', '挂科预警', '绩点预警', '补考重修预警', '毕业风险预警', '预警规则'),
      I('预警学生（现有）', '/admin/academic/warnings'),
      ...P('预警通知', '预警处置', '预警跟进', '预警统计')
    ]),
    mod('aa-graduation-qual', '毕业资格审核', null, P('审核批次', '毕业学生名单', '学分达成审核', '课程达成审核', '实践环节审核', '毕设状态联动', '实习状态联动', '欠费状态联动', '处分状态联动', '毕业资格预审', '毕业资格终审', '不通过原因', '审核结果', '审核归档')),
    mod('aa-textbooks', '教材管理', null, P('教材目录', '教材选用', '教材征订', '教材审核', '教材发放', '教材费用', '教材库存', '教材统计', '教材归档')),
    mod('aa-resources', '教学资源', null, P('教室资源', '实训室资源', '设备资源', '教室预约', '实训室预约', '资源占用', '资源冲突', '资源维修', '资源统计')),
    mod('aa-evaluation', '教学评价', null, P('评教批次', '学生评教', '教师自评', '同行评价', '督导评价', '评价结果', '评价申诉', '评价统计', '评价归档')),
    mod('aa-quality', '教学质量', null, P('督导听课', '巡课记录', '教学检查', '教学事故', '质量整改', '整改跟进', '质量报告', '质量统计', '质量归档')),
    mod('aa-archive', '教务归档', null, P('学籍归档', '注册归档', '异动归档', '培养方案归档', '教学任务归档', '课表归档', '考务归档', '成绩归档', '毕业资格归档', '归档缺失提醒', '批量归档', '归档导出')),
    mod('aa-stats', '教务统计', null, P('教务总览', '学籍统计', '注册统计', '课程统计', '教学任务统计', '课表统计', '调停课统计', '选课统计', '考务统计', '成绩统计', '学业预警统计', '毕业资格统计', '教师工作量统计', '教学资源统计', '导出报表'))
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

  /* ═══════════ 一级⑤：岗位实习中心（固定12个二级模块）═══════════
   * 收口规则（2026-07-10 信息架构收口）：
   * 1) 三级只挂真实、独立、高频的工作队列；同一页面的状态/类型/方式/流程环节一律页内 Tab 或筛选，不再平铺菜单；
   * 2) 详情页、依赖对象 ID 的页面、低频设置页不进正常菜单（H 隐藏叶子仅保留归属高亮，入口在页内）；
   * 3) 每个二级模块本身可点击，落到该模块业务主页；
   * 4) 旧 ?panel= 菜单地址仍是真实路由，刷新/书签不受影响。 */
  grp('internship', '岗位实习中心', 'internship', [
    // 今日工作：总览·待办·风险提醒为同一聚合页的区块，只保留一个入口
    mod('in-workbench', '今日工作', '/admin/internship', []),
    // 实习批次设置：批次列表即模块主页；阶段/打卡/周报/指导/评价/成绩规则在批次详情与编辑抽屉维护
    mod('in-batch-rules', '实习批次设置', '/admin/internship/batches', []),
    mod('in-students', '学生实习管理', '/admin/internship/students', [
      I('学生名单', '/admin/internship/students?panel=roster'),
      I('资格认定', '/admin/internship/students?panel=eligibility'),
      H('实习保险核验', '/admin/internship/insurance')
    ]),
    mod('in-enterprise-position', '企业岗位库', '/admin/internship/enterprises', [
      I('企业管理', '/admin/internship/enterprises'),
      I('岗位管理', '/admin/internship/positions')
    ]),
    mod('in-match-assign', '岗位与导师分配', '/admin/internship/match', [
      I('岗位与导师分配', '/admin/internship/match'),
      I('调岗退岗台账', '/admin/internship/changes')
    ]),
    mod('in-apply-agreement', '申请与协议办理', '/admin/internship/agreements', [
      I('申请审核', '/admin/internship/agreements?panel=student-apply'),
      I('协议办理', '/admin/internship/agreements?panel=issue'),
      H('协议模板', '/admin/internship/agreement-templates')
    ]),
    mod('in-attendance-leave', '打卡请假处理', '/admin/internship/attendance', [
      I('打卡台账', '/admin/internship/attendance'),
      I('异常处理', '/admin/internship/exceptions'),
      I('请假审批', '/admin/internship/leaves')
    ]),
    mod('in-weekly-task', '周报任务批阅', '/admin/internship/reports', [
      I('报告批阅', '/admin/internship/reports'),
      I('任务与计划', '/admin/internship/plans'),
      H('过程报告批阅', '/admin/internship/process-reports')
    ]),
    mod('in-guidance-visit', '指导巡访管理', '/admin/internship/guidance', [
      I('指导记录', '/admin/internship/guidance?panel=guidance'),
      I('巡访管理', '/admin/internship/guidance?panel=visit'),
      I('整改跟进', '/admin/internship/guidance?panel=rectify'),
      H('指导计划', '/admin/internship/guidance-plan')
    ]),
    mod('in-risk', '风险异常处置', '/admin/internship/risks', [
      I('风险看板', '/admin/internship/risks'),
      I('风险处置', '/admin/internship/risk-disposal')
    ]),
    mod('in-eval-score', '评价成绩审核', '/admin/internship/enterprise-evals', [
      I('评价管理', '/admin/internship/enterprise-evals'),
      I('综合成绩', '/admin/internship/scores'),
      H('学生自评与教师评价', '/admin/internship/student-evals')
    ]),
    // 归档与统计：就业跟进属就业中心，本轮不在实习菜单挂跨中心入口（搜索仍可达 /admin/employment）
    mod('in-employment-archive-stats', '归档与统计', '/admin/internship/archive', [
      I('实习归档', '/admin/internship/archive'),
      I('实习统计', '/admin/internship/stats')
    ])
  ]),

  /* ═══════════ 一级⑥：系统管理 ═══════════ */
  grp('system', '系统管理', 'systemAdmin', [
    mod('sys-dashboard', '管理看板', '/admin/system', []),
    mod('sys-users', '用户账号', '/admin/system/users', []),
    mod('sys-roles', '角色权限', '/admin/system/roles', []),
    mod('sys-menus', '菜单权限', '/admin/system/menus', []),
    mod('sys-buttons', '按钮权限', null, P('按钮权限配置', '按钮权限分配', '按钮权限审计')),
    mod('sys-scopes', '数据范围', '/admin/system/scopes', []),
    mod('sys-org', '组织结构', '/admin/system/org', []),
    mod('sys-school-params', '学校参数', null, P('学校基本参数', '业务开关', '编号规则', '字段配置')),
    mod('sys-brand', '系统与品牌', '/admin/system/config', []),
    mod('sys-workflow', '流程配置', '/admin/workflow', [
      I('流程中心', '/admin/workflow'),
      I('流程模板', '/admin/workflow/processes'),
      I('审批任务', '/admin/workflow/tasks'),
      I('角色管理', '/admin/workflow/roles'),
      I('权限点管理', '/admin/workflow/permissions')
    ]),
    mod('sys-approval-tpl', '审批模板', null, P('审批模板列表', '审批节点配置', '通知模板')),
    mod('sys-logs', '日志中心', '/admin/system/logs', []),
    mod('sys-security-audit', '安全审计', null, P('安全审计', '敏感操作审计', '登录审计', '导出审计')),
    mod('sys-integrations', '第三方接口', null, P('接口配置', 'API 访问', 'Webhook', '同步任务')),
    mod('sys-tenant', '租户配置', null, P('租户信息', '模块授权', '套餐配置'))
  ])
]

/**
 * 平台运营（隐藏一级，仅平台超管可见；不属学校侧 6 个一级）。
 * 单列，避免混入学校导航；仅登记已实现页面，保持旧路由可访问。
 */
export const PLATFORM_PLAN = grp('platform', '平台运营', 'platform', [
  mod('plt-overview', '平台总控台', '/admin/platform/overview', []),
  mod('plt-tenants', '租户学校', '/admin/platform/tenants', []),
  mod('plt-packages', '套餐管理', '/admin/platform/packages', []),
  mod('plt-orders', '订单开通', '/admin/platform/orders', []),
  mod('plt-audit', '全平台审计', '/admin/platform/audit', [])
], { platformOnly: true })

/**
 * 按角色可见性过滤规划树。
 * @param {object} opts.includePlanned 管理员/开发者视角=true（可见 planned），普通业务角色=false（隐藏 planned）
 * @returns {Array} 过滤后的规划树（planned 节点在 includePlanned=false 时剔除）
 */
const _navPlanVisibleCache = new Map()
export function getVisibleNavPlan({ includePlanned = false } = {}) {
  const cacheKey = includePlanned ? '1' : '0'
  if (_navPlanVisibleCache.has(cacheKey)) return _navPlanVisibleCache.get(cacheKey)
  // 普通业务角色：只见 implemented / partial；管理员/开发者视角：additionally 见 planned / unauthorized
  // hidden 叶子：任何视角都不进菜单（如旧兼容入口），仅保留路由/高亮
  const keepLeaf = (leaf) =>
    !leaf.hidden && (includePlanned || leaf.status === 'implemented' || leaf.status === 'partial')
  const keepMod = (mod2) =>
    includePlanned || mod2.status === 'implemented' || mod2.status === 'partial' || mod2.children.some(keepLeaf)
  const result = NAV_PLAN.map((group) => ({
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
  return ref
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
  for (const group of NAV_PLAN) {
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
          hidden: !!leaf.hidden
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
export function searchNavPlan(query) {
  const q = (query || '').trim().toLowerCase()
  if (!q) return []
  if (_navSearchCache.has(q)) return _navSearchCache.get(q)
  const out = []
  for (const row of FLAT_NAV_INDEX) {
    if (row.hidden) continue  // 隐藏的兼容入口不进搜索
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
  _navSearchCache.set(q, out)
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
