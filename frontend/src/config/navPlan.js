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
    mod('sa-dashboard', '学工看板', '/admin/student-affairs/dashboard', [
      I('学工总览', '/admin/student-affairs/dashboard'),
      I('今日待办', '/admin/student-affairs/dashboard'),
      I('辅导员待办', '/admin/student-affairs/dashboard'),
      I('学生风险概览', '/admin/student-affairs/dashboard'),
      I('请假审批概览', '/admin/student-affairs/dashboard'),
      ...P('奖助进度概览'),
      I('宿舍异常概览', '/admin/student-affairs/dashboard'),
      ...P('心理关注概览', '违纪处分概览', '学工数据趋势'),
      I('重点学生提醒', '/admin/student-affairs/dashboard'),
      ...P('待归档材料提醒')
    ]),
    mod('sa-profile', '学生画像', '/admin/student-affairs/profile', [
      I('学生主档摘要', '/admin/student-affairs/profile'),
      I('基础信息', '/admin/student-affairs/profile'),
      I('学籍状态摘要', '/admin/student-affairs/profile'),
      I('班级信息', '/admin/student-affairs/profile'),
      I('家庭与联系人摘要', '/admin/student-affairs/profile'),
      ...P('家校联系记录', '奖助信息摘要'),
      I('请假记录摘要', '/admin/student-affairs/profile'),
      I('宿舍信息摘要', '/admin/student-affairs/profile'),
      I('处分摘要', '/admin/student-affairs/profile'),
      I('心理关注摘要', '/admin/student-affairs/profile'),
      I('风险标签', '/admin/student-affairs/profile'),
      I('成长时间线', '/admin/student-affairs/profile'),
      ...P('材料归档'),
      I('信息更正审核（现有学生中心）', '/admin/student/corrections'),
      I('数据变更日志入口', '/admin/student-affairs/profile'),
      I('身份核验（现有）', '/admin/student/identity'),
      I('导入导出（现有）', '/admin/student/import-export')
    ]),
    mod('sa-classes', '班级管理', null, P(
      '班级列表', '班级详情', '班级学生', '辅导员绑定', '班主任绑定', '班干部管理', '班级通讯录',
      '班级风险概览', '班级请假统计', '班级宿舍统计', '班级奖助统计', '班级活动统计', '班级档案'
    )),
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
      ...P('请假看板', '请假申请'),
      I('请假审批', '/admin/campus-service/leave'),
      ...P('续假申请', '续假审批', '销假管理', '归寝核验', '长假审批', '外出备案',
        '请假异常', '超期未销假', '请假规则配置', '请假台账', '请假统计', '请假归档')
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
    mod('sa-counselor-eval', '辅导员考评', null, P(
      '考评看板', '工作量统计', '谈话记录统计', '宿舍走访统计', '风险处置统计', '请假审批统计',
      '班级建设统计', '学生满意度', '学院评分', '考评结果', '考评归档'
    )),
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
   * 2026-07-09 按三家成熟商业系统对标重新分组（详见 docs/施工记录/毕业设计中心-导航重构对标记录.md）：
   * 同方知网(CNKI)大学生毕业论文管理系统 / 强智科技教学微服务平台 / 维普毕业论文管理系统，
   * 三家均按"选题→过程指导→成果检查→答辩成绩→归档"阶段分组二级菜单，不按数据实体逐个拆二级模块。
   * 本轮把 2026-07-08 夜间新增模块里"同一页面被拆成多个二级菜单"的部分合并回页面实际的 tab 结构；
   * 已验收的题目库/选题管理/毕设批次/毕设学生保持不变，不在本轮合并范围内。 */
  grp('graduation', '毕业设计中心', 'graduationDesign', [
    mod('gd-dashboard', '毕设看板', '/admin/graduation', [
      I('毕设总览（管理看板，含阶段进度条/待办/风险提示，已实现）', '/admin/graduation'),
      I('跨模块统计报表（导师/指导/中期/评阅/成绩/归档等 9 域统计中心）', '/admin/graduation/stats-report')
    ]),
    // 毕设批次为单页多视图：各三级带 ?panel= 指向同一页的不同视图/动作，页面按 panel 响应
    // （新建→开抽屉、阶段/规则→详情默认落到对应 tab、进行中/已归档→按状态筛选、导出→下载台账）。
    // 每个三级是不同 ref，点击都能导航、都有反应，避免多叶子同 path「点了没反应」。（对齐实习批次写法）
    mod('gd-batches', '毕设批次', '/admin/graduation/batches?panel=list', [
      I('批次列表（新建/编辑/启停/作废）', '/admin/graduation/batches?panel=list'),
      I('新建批次', '/admin/graduation/batches?panel=create'),
      I('阶段时间轴配置', '/admin/graduation/batches?panel=stages'),
      I('规则配置（查重/答辩/成绩权重）', '/admin/graduation/batches?panel=rules'),
      I('进行中批次', '/admin/graduation/batches?panel=running'),
      I('已归档批次', '/admin/graduation/batches?panel=archived'),
      I('毕设批次台账导出', '/admin/graduation/batches?panel=export'),
      I('材料模板（模板中心·材料类）', '/admin/graduation/templates?type=MATERIAL')
    ]),
    mod('gd-students', '毕设学生', '/admin/graduation/students', [
      I('学生名单（建档/导入导出）', '/admin/graduation/students?panel=roster'),
      I('学生进度（节点筛选）', '/admin/graduation/students?panel=progress'),
      I('学生风险', '/admin/graduation/students?panel=risk'),
      I('学生导师（已选题）', '/admin/graduation/students?panel=mentor'),
      I('未选题学生（分配选题）', '/admin/graduation/students?panel=topic'),
      I('学生资格', '/admin/graduation/students?panel=eligibility'),
      I('学生分组', '/admin/graduation/students?panel=grouping'),
      I('学生材料', '/admin/graduation/students?panel=materials'),
      I('学生答辩组', '/admin/graduation/students?panel=defense'),
      I('学生毕业资格联动', '/admin/graduation/students?panel=grad-qual'),
      I('学生归档（roster 归档状态字段，区别于下方"预警与归档"的材料清单核验）', '/admin/graduation/students?panel=archive')
    ]),
    mod('gd-topic-lib', '题目库', '/admin/graduation/topic-lib', [
      I('题目列表', '/admin/graduation/topic-lib?panel=list'),
      I('教师申报题目', '/admin/graduation/topic-lib?panel=teacher-apply'),
      I('企业题目', '/admin/graduation/topic-lib?panel=enterprise'),
      I('学生自拟题目', '/admin/graduation/topic-lib?panel=student-proposed'),
      I('待审核题目', '/admin/graduation/topic-lib?panel=pending'),
      I('题目分类', '/admin/graduation/topic-lib?panel=category'),
      I('题目容量', '/admin/graduation/topic-lib?panel=capacity'),
      I('题目要求', '/admin/graduation/topic-lib?panel=requirements'),
      I('题目附件', '/admin/graduation/topic-lib?panel=attachments'),
      I('题目历史', '/admin/graduation/topic-lib?panel=history'),
      I('题目归档', '/admin/graduation/topic-lib?panel=archive')
    ]),
    mod('gd-topics', '选题管理', '/admin/graduation/topics', [
      I('选题轮次', '/admin/graduation/topic-rounds?panel=rounds'),
      I('学生志愿', '/admin/graduation/topic-rounds?panel=choices'),
      I('匹配结果', '/admin/graduation/topic-rounds?panel=match'),
      I('学生选题（选题管理）', '/admin/graduation/topics'),
      I('教师确认（志愿一对一确认/驳回）', '/admin/graduation/topic-rounds?panel=choices'),
      I('题目调整（选题变更申请审核）', '/admin/graduation/topic-changes'),
      // 已删除的旧占位项及原因：选题开放＝选题轮次页内"开放轮次"按钮（已实现，非独立页面）；
      // 题目审核＝题目库"待审核题目"面板重复；选题结果＝本组"匹配结果"重复。均非真实缺口。
      I('退选重选（学生撤回志愿后重填，管理端可代退）', '/admin/graduation/topic-rounds?panel=choices'),
      I('容量冲突人工复核（过热题目+竞争学生确认/驳回）', '/admin/graduation/topic-rounds?panel=conflicts'),
      I('选题统计报表（志愿分布/参与/过热题目）', '/admin/graduation/topic-rounds?panel=conflicts'),
      I('选题归档（已关闭/已匹配轮次归档）', '/admin/graduation/topic-rounds?panel=rounds')
    ]),
    // 导师管理 + 导师分配：原为 2 个二级模块，均指向同一页 GraduationMentorListView.vue 的不同 panel，
    // 已合并为 1 个二级模块 + 2 个三级页签（对齐 CNKI/强智"导师"作为选题任务书阶段的一个子域，不单列多个二级）。
    mod('gd-mentors', '导师管理与分配', '/admin/graduation/mentors?panel=list', [
      I('导师名单（申报/审核/编辑/导入导出）', '/admin/graduation/mentors?panel=list'),
      I('导师容量与工作量', '/admin/graduation/mentors?panel=list'),
      I('未分配导师学生（发起分配）', '/admin/graduation/mentors?panel=assign'),
      I('分配调整记录（调导师/取消分配）', '/admin/graduation/mentors?panel=assign'),
      I('导师评价（评分0-100+等级+意见，含历史）', '/admin/graduation/mentors?panel=list'),
      I('批量分配（一键把未分配学生分给已认证导师）', '/admin/graduation/mentors?panel=assign'),
      I('分配冲突自动检测（超容量/进阶段无导师/导师非认证）', '/admin/graduation/mentors?panel=list'),
      I('导师归档批量（批量归档已停用/驳回导师）', '/admin/graduation/mentors?panel=list')
    ]),
    // 任务书 + 指导过程 + 中期检查：原为 3 个二级模块，均指向同一页 GraduationProcessView.vue 的不同 panel，
    // 已合并为 1 个二级模块 + 3 个三级页签（对齐三家系统"过程指导"统一分组，含指导记录+中期检查+整改跟踪）。
    mod('gd-process', '过程指导', '/admin/graduation/process?panel=taskbook', [
      I('任务书下达/确认/变更', '/admin/graduation/process?panel=taskbook'),
      I('指导记录（时间线/新增/撤销）', '/admin/graduation/process?panel=guidance'),
      I('中期检查（三档结论/整改跟踪）', '/admin/graduation/process?panel=midterm'),
      I('任务书模板（模板中心·任务书类）', '/admin/graduation/templates?type=TASKBOOK'),
      I('指导频次统计报表（统计中心）', '/admin/graduation/stats-report'),
      I('中期统计报表（统计中心）', '/admin/graduation/stats-report'),
      I('过程归档（并入中央·预警归档统计）', '/admin/graduation/risk-archive?panel=archive')
    ]),
    mod('gd-proposal', '开题材料', '/admin/graduation/proposals', [
      I('开题报告列表与批阅（提交/导师审核通过或驳回，点击进入详情页操作，已实现）', '/admin/graduation/proposals'),
      I('开题模板（模板中心·开题类）', '/admin/graduation/templates?type=PROPOSAL'),
      I('开题附件（详情页附件清单）', '/admin/graduation/proposals'),
      I('开题答辩（现场答辩·详情页录入 PASS/FAIL）', '/admin/graduation/proposals'),
      I('开题整改跟踪（已驳回页签→学生重交）', '/admin/graduation/proposals'),
      I('开题统计（统计中心）', '/admin/graduation/stats-report'),
      I('开题归档（并入中央·预警归档统计）', '/admin/graduation/risk-archive?panel=archive')
    ]),
    // 成果提交 + 查重记录 + 教师评阅：对齐三家系统"成果检查"统一分组（提交/查重/评阅同阶段）。
    // 查重与评阅共用 GraduationDefenseGradeView.vue 的 panel；成果提交沿用既有独立页面。
    mod('gd-final-review', '成果检查', '/admin/graduation/finals', [
      I('论文提交（现有·成果提交）', '/admin/graduation/finals'),
      I('查重记录（发起/回填/复查）', '/admin/graduation/defense-grade?panel=plagiarism'),
      I('教师评阅（分配/提交/退回，SoD 校验）', '/admin/graduation/defense-grade?panel=review'),
      I('版本记录（成果初稿/定稿版本）', '/admin/graduation/finals'),
      I('互查整改（学生互评+被评整改）', '/admin/graduation/more?panel=peer'),
      I('查重报告归档（并入中央·预警归档统计）', '/admin/graduation/risk-archive?panel=archive'),
      I('评阅统计报表（统计中心）', '/admin/graduation/stats-report'),
      I('成果归档（并入中央·预警归档统计）', '/admin/graduation/risk-archive?panel=archive')
    ]),
    // 答辩安排 + 答辩评分 + 成绩评定：对齐三家系统"答辩成绩"统一分组。
    // 答辩评分与成绩评定共用 GraduationDefenseGradeView.vue 的 panel；答辩安排沿用既有独立页面。
    mod('gd-defense', '答辩成绩', '/admin/graduation/defense', [
      I('答辩批次（现有·答辩安排）', '/admin/graduation/defense'),
      I('答辩评分（评委录入/缺席/确认/二次答辩）', '/admin/graduation/defense-grade?panel=defense'),
      I('成绩评定（核算/复核/发布/撤回）', '/admin/graduation/defense-grade?panel=grade'),
      I('答辩分组（现有·答辩安排分组/学生分配）', '/admin/graduation/defense'),
      I('答辩专家（评委库+回避）', '/admin/graduation/more?panel=experts'),
      I('答辩通知（对已发布答辩组学生通知，留痕）', '/admin/graduation/defense'),
      I('成绩更正申诉（学生申诉→复核）', '/admin/graduation/more?panel=appeals'),
      I('答辩与成绩归档（并入中央·预警归档统计）', '/admin/graduation/risk-archive?panel=archive')
    ]),
    // 问题预警 + 毕设归档 + 毕设统计：对齐三家系统"归档与统计"收尾阶段，三者共用 GraduationRiskArchiveView.vue。
    mod('gd-risk-archive', '预警 · 归档 · 统计', '/admin/graduation/risk-archive?panel=risk', [
      I('问题预警（GD-R01/R04/R06/R07/R08/R09/R13 扫描+受理+处理+关闭）', '/admin/graduation/risk-archive?panel=risk'),
      I('学生归档包（自动核验清单/提交/核验/驳回/导出台账）', '/admin/graduation/risk-archive?panel=archive'),
      I('毕设总览统计（跨模块聚合）与学院/专业对比', '/admin/graduation/risk-archive?panel=stats'),
      I('剩余风险编码补齐（GD-R02/R03/R05/R10/R11 已接扫描）', '/admin/graduation/risk-archive?panel=risk'),
      I('批量归档一键操作（批量生成提交 / 一键核验备案）', '/admin/graduation/risk-archive?panel=archive'),
      I('开题/中期/查重/答辩细分报表（统计中心）', '/admin/graduation/stats-report')
    ])
  ]),

  /* ═══════════ 一级⑤：岗位实习中心 ═══════════ */
  grp('internship', '岗位实习中心', 'internship', [
    mod('in-dashboard', '实习看板', '/admin/internship', [
      I('实习总览（管理看板）', '/admin/internship'),
      ...P('当前批次进度', '实习学生概览', '企业岗位概览', '打卡异常概览', '周报提交概览',
        '教师指导概览', '风险学生概览', '就业落实概览', '待办事项', '数据趋势')
    ]),
    mod('in-batches', '实习批次', '/admin/internship/batches', [
      I('批次列表（新建/编辑/启停/归档/作废）', '/admin/internship/batches?panel=list'),
      I('批次时间轴（阶段配置，JSON 可编辑）', '/admin/internship/batches?panel=timeline'),
      I('打卡/周报/指导/评价/成绩规则配置（JSON 可编辑）', '/admin/internship/batches?panel=rules'),
      I('批次台账导出', '/admin/internship/batches?panel=export'),
      ...P('阶段配置可视化编辑器', '规则配置可视化编辑器')
    ]),
    mod('in-students', '实习学生', '/admin/internship/students', [
      I('实习名单（建档/导入导出）', '/admin/internship/students?panel=roster'),
      I('实习资格认定', '/admin/internship/students?panel=eligibility'),
      I('学生实习状态', '/admin/internship/students?panel=status'),
      I('实习去向', '/admin/internship/students?panel=destination'),
      I('学生岗位（从岗位库分配/调岗/退岗）', '/admin/internship/students?panel=position'),
      I('学生企业', '/admin/internship/students?panel=enterprise'),
      I('学生导师', '/admin/internship/students?panel=mentor'),
      ...P('学生打卡', '学生周报', '学生风险', '学生材料', '学生归档')
    ]),
    mod('in-enterprises', '企业库', '/admin/internship/enterprises', [
      I('企业列表', '/admin/internship/enterprises?panel=list'),
      I('企业详情', '/admin/internship/enterprises?panel=detail'),
      I('企业联系人', '/admin/internship/enterprises?panel=contacts'),
      I('企业导师', '/admin/internship/enterprises?panel=mentor'),
      I('企业资质审核', '/admin/internship/enterprises?panel=qualification'),
      I('企业黑名单', '/admin/internship/enterprises?panel=blacklist'),
      I('企业归档', '/admin/internship/enterprises?panel=archive'),
      PA('企业统计', '/admin/internship/enterprises?panel=stats'),
      PA('企业合作记录', '/admin/internship/enterprises?panel=cooperation'),
      PA('企业岗位', '/admin/internship/enterprises?panel=positions'),
      ...P('企业评价')
    ]),
    mod('in-positions', '岗位库', '/admin/internship/positions', [
      I('岗位列表', '/admin/internship/positions?panel=list'),
      I('岗位详情', '/admin/internship/positions?panel=detail'),
      I('岗位要求（专业/年级）', '/admin/internship/positions?panel=requirement'),
      I('岗位容量', '/admin/internship/positions?panel=capacity'),
      I('岗位发布（上架）', '/admin/internship/positions?panel=publish'),
      I('岗位下架', '/admin/internship/positions?panel=offline'),
      I('岗位风险提示', '/admin/internship/positions?panel=risk'),
      I('岗位归档', '/admin/internship/positions?panel=archive'),
      I('岗位统计', '/admin/internship/positions?panel=stats'),
      I('岗位专业匹配', '/admin/internship/match?panel=major')
    ]),
    mod('in-match', '岗位匹配', '/admin/internship/match', [
      I('学生意向', '/admin/internship/match?panel=intention'),
      I('岗位推荐', '/admin/internship/match?panel=recommend'),
      I('专业匹配', '/admin/internship/match?panel=major'),
      I('企业匹配', '/admin/internship/match?panel=enterprise'),
      I('手动匹配', '/admin/internship/match?panel=manual'),
      I('批量匹配', '/admin/internship/match?panel=batch'),
      I('匹配确认', '/admin/internship/match?panel=confirm'),
      I('匹配冲突', '/admin/internship/match?panel=conflict'),
      I('匹配结果', '/admin/internship/match?panel=results'),
      I('匹配统计', '/admin/internship/match?panel=stats')
    ]),
    mod('in-apply', '实习申请审核', null, P('学生申请', '自主实习申请', '岗位申请', '企业信息提交', '学生材料提交', '指导老师初审', '学院审核', '学校复核', '审核退回', '审核通过', '审核台账')),
    mod('in-assign', '岗位分配', null, P('分配规则', '指导老师分配', '企业岗位分配', '批量分配', '调岗申请', '调岗审批', '分配结果', '分配日志', '分配统计')),
    mod('in-agreement', '实习协议', '/admin/internship/agreement-templates', [
      I('协议模板库（新建/编辑/启停/归档/默认/适用范围/变量）', '/admin/internship/agreement-templates'),
      ...P('协议发起', '学生确认', '企业确认', '学校确认', '三方协议', '协议上传', '协议审核', '协议变更', '协议归档')
    ]),
    mod('in-plan', '实习计划任务', null, P('实习计划', '实习任务', '周期目标', '岗位任务书', '企业任务', '指导老师任务', '学生任务确认', '任务完成记录', '任务统计')),
    mod('in-attendance', '打卡管理', null, [
      ...P('打卡规则', '打卡记录', '定位打卡', '外勤打卡', '补卡申请', '补卡审批', '缺卡记录', '迟到早退', '连续未打卡'),
      I('打卡异常（现有）', '/admin/internship/exceptions'),
      ...P('打卡地图', '打卡统计', '打卡归档')
    ]),
    mod('in-leave', '请假异常', null, P('实习请假', '请假审批', '销假管理', '请假异常', '超期未归', '离岗异常', '企业反馈异常', '指导老师处理', '异常闭环', '异常统计')),
    mod('in-weekly', '周报日报', null, P('日报提交', '周报提交', '月报提交', '周报模板', '周报草稿', '周报逾期', '周报退回', '周报补交', '周报统计', '周报归档')),
    mod('in-weekly-review', '周报批阅', '/admin/internship/reports', [
      I('待批阅周报（现有·周报批阅）', '/admin/internship/reports'),
      ...P('已批阅周报', '批阅意见', '批量批阅', '退回修改', '优秀周报', '周报问题', '批阅统计', '批阅归档')
    ]),
    mod('in-guidance', '指导记录', null, P('指导计划', '指导记录', '电话指导', '线上指导', '现场指导', '企业沟通', '指导附件', '指导频次', '指导不足预警', '指导统计', '指导归档')),
    mod('in-visit', '巡访记录', null, P('巡访计划', '巡访安排', '巡访签到', '巡访记录', '企业访谈', '学生访谈', '巡访照片', '巡访问题', '整改跟进', '巡访统计', '巡访归档')),
    mod('in-risk', '风险学生', '/admin/internship/risks', [
      I('风险看板（现有·风险学生）', '/admin/internship/risks'),
      ...P('未落实岗位', '长期未打卡', '周报逾期', '离岗异常', '企业投诉', '安全风险', '实习中断', '就业风险', '风险处置', '风险跟进', '风险关闭', '风险统计')
    ]),
    mod('in-company-eval', '企业评价', null, P('企业导师评价', '企业评分', '企业意见', '岗位适配评价', '企业满意度', '企业问题反馈', '企业评价统计', '企业评价归档')),
    mod('in-student-eval', '学生评价', null, P('学生自评', '学生对企业评价', '学生对岗位评价', '学生对指导评价', '实习满意度', '学生反馈', '学生评价统计', '学生评价归档')),
    mod('in-grade', '实习成绩', null, P('成绩规则', '打卡成绩', '周报成绩', '企业评价成绩', '指导老师成绩', '综合成绩', '成绩审核', '成绩发布', '成绩复核', '成绩归档')),
    mod('in-employment', '就业跟进', '/admin/employment', [
      I('就业看板（就业服务）', '/admin/employment'),
      I('就业学生', '/admin/employment/students'),
      ...P('就业意向', '签约登记', '单位登记'),
      I('就业材料', '/admin/employment/materials'),
      I('就业审核 / 跟进记录', '/admin/employment/followups'),
      ...P('就业去向', '就业回访', '就业统计', '就业归档')
    ]),
    mod('in-unemployed', '未就业帮扶', '/admin/employment/unemployed', [
      I('未就业学生', '/admin/employment/unemployed'),
      ...P('帮扶计划', '帮扶记录', '岗位推荐', '简历指导', '面试指导', '就业困难学生', '帮扶跟进', '帮扶结果', '帮扶统计', '帮扶归档')
    ]),
    mod('in-archive', '实习归档', null, P('学生归档包', '企业归档', '岗位归档', '协议归档', '打卡归档', '周报归档', '指导记录归档', '巡访归档', '评价归档', '成绩归档', '就业归档', '缺失材料提醒', '批量归档', '归档导出')),
    mod('in-stats', '实习统计', null, P('实习总览', '实习落实率', '岗位匹配统计', '企业统计', '打卡统计', '周报统计', '指导统计', '巡访统计', '风险统计', '实习成绩统计', '就业落实统计', '未就业帮扶统计', '学院对比', '专业对比', '导出报表'))
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
export function getVisibleNavPlan({ includePlanned = false } = {}) {
  // 普通业务角色：只见 implemented / partial；管理员/开发者视角：additionally 见 planned / unauthorized
  // hidden 叶子：任何视角都不进菜单（如旧兼容入口），仅保留路由/高亮
  const keepLeaf = (leaf) =>
    !leaf.hidden && (includePlanned || leaf.status === 'implemented' || leaf.status === 'partial')
  const keepMod = (mod2) =>
    includePlanned || mod2.status === 'implemented' || mod2.status === 'partial' || mod2.children.some(keepLeaf)
  return NAV_PLAN.map((group) => ({
    ...group,
    children: group.children
      .filter(keepMod)
      .map((mod2) => ({ ...mod2, children: mod2.children.filter(keepLeaf) }))
  })).filter((group) => group.children.length > 0)
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
 * 依当前路由在规划树中定位所属 一级/二级/三级（用于侧栏高亮）。
 * @param {string} path 路由 path
 * @param {string} [fullPath] 含 query 的完整路径（三级菜单带 ?panel= 时必须）
 * @returns {{groupKey:string, modKey:string, leafKey:string}}
 */
export function findActiveInPlan(path, fullPath = '') {
  if (!path) return { groupKey: '', modKey: '', leafKey: '' }
  const ref = normalizeNavRef(fullPath || path)
  let best = { groupKey: '', modKey: '', leafKey: '', score: -1 }
  for (const group of NAV_PLAN) {
    for (const mod2 of group.children) {
      const cands = [{ key: mod2.key, path: mod2.path, isLeaf: false, label: '' }]
      mod2.children.forEach((leaf, i) => {
        if (leaf.path) cands.push({ key: `${mod2.key}:${i}`, path: leaf.path, isLeaf: true, label: leaf.label })
      })
      for (const c of cands) {
        if (!c.path) continue
        let score = -1
        if (navRefMatches(ref, c.path)) {
          score = c.path.length + (splitNavRef(c.path).query ? 1000 : 0)
        } else {
          const { path: cp, query: cq } = splitNavRef(c.path)
          if (!cq && (cp === '/' ? path === '/' : path === cp || path.startsWith(`${cp}/`))) {
            score = cp.length
          }
        }
        if (score > best.score) {
          best = { groupKey: group.key, modKey: mod2.key, leafKey: c.isLeaf ? c.label : '', score }
        }
      }
    }
  }
  return { groupKey: best.groupKey, modKey: best.modKey, leafKey: best.leafKey }
}

/**
 * 搜索规划菜单：命中 planned 时 disabled=true（前端只提示「待施工」，不跳转）。
 * @param {string} query
 * @returns {Array} [{ label, path, status, disabled, badge, trail }]
 */
export function searchNavPlan(query) {
  const q = (query || '').trim().toLowerCase()
  if (!q) return []
  const out = []
  for (const group of NAV_PLAN) {
    for (const mod2 of group.children) {
      const hitMod = mod2.label.toLowerCase().includes(q)
      if (hitMod) {
        out.push({
          label: mod2.label,
          path: mod2.path || null,
          status: mod2.status,
          disabled: mod2.disabled,
          badge: mod2.badge,
          trail: `${group.label} / ${mod2.label}`
        })
      }
      for (const leaf of mod2.children) {
        if (leaf.hidden) continue  // 隐藏的兼容入口不进搜索
        if (leaf.label.toLowerCase().includes(q)) {
          out.push({
            label: leaf.label,
            path: leaf.path || null,
            status: leaf.status,
            disabled: leaf.disabled,
            badge: leaf.badge,
            trail: `${group.label} / ${mod2.label} / ${leaf.label}`
          })
        }
      }
    }
  }
  return out.slice(0, 20)
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
