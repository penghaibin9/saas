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

  /* ═══════════ 一级③：教务中心 ═══════════
   * 2026-07-10 三级目录纠偏（详见 docs/施工记录/13B-教务中心PC前端三级目录重构记录.md）：
   * 1) 二级按真实教务业务对象/端到端流程/责任角色/状态机裁决（对标成熟商用教务系统通用
   *    模块划分并原创实现，不照抄任何第三方系统），不预设数量；
   * 2) 正式菜单（普通角色）只显示真实可用页面 = 现有学业过程中心 6 页承接，
   *    realFirst 真接口 + mock 兜底、公共组件/Excel/日期底座未接完 → 如实标 partial，不虚标 implemented；
   * 3) planned 仅作 DEV 施工地图（isPlannerView 已收紧到 DEV/平台侧），且只挂「独立工作区」，
   *    详情/Tab/状态筛选/流程节点/统计指标/归档材料一律不挂菜单；
   *    页面级完整长期树见 docs/modules/13B-教务中心页面树与路由设计.md（108 页规划）。 */
  grp('academic-affairs', '教务中心', 'academicAffairs', [
    /* ① 教务工作台：现有学业过程中心总览承接；角色化待办/今日运行为 13B 后续施工 */
    mod('aa-workbench', '教务工作台', '/admin/academic', [
      PA('教务总览（现有·学业过程中心）', '/admin/academic'),
      ...P('我的教务待办', '今日教学运行', '教学运行统计')
    ]),
    /* ② 教学基础数据：全链前置字典（学期/校历/节次/场地）；学院专业班级主责在系统管理·组织结构，此处不重复维护 */
    mod('aa-basics', '教学基础数据', null, P('学年学期', '校历与节次', '教室与场地')),
    /* ③ 专业与培养方案：SM-01/04；方案审核=流程节点进待办、方案课程配置=编制页 Tab，不挂菜单 */
    mod('aa-programs', '专业与培养方案', null, P('培养方案', '学期开课计划')),
    /* ④ 课程库：SM-05 课程字典单工作区；审核为页内 Tab、Excel 导入为页内动作，不拆叶 */
    mod('aa-courses', '课程库', null, []),
    /* ⑤ 教学任务与开课：SM-06；任务审核=流程节点、任务统计=统计页 */
    mod('aa-teaching-tasks', '教学任务与开课', null, P('教学任务批次', '教师任务确认', '教学班组建')),
    /* ⑥ 排课与课表：SM-07/08；班级/教师/教室课表=课表工作区维度 Tab、调停课审批=流程节点 */
    mod('aa-schedule', '排课与课表', null, P('排课工作台', '课表查看与发布', '调停课')),
    /* ⑦ 选课管理：SM-09；退补选=批次内动作、选课统计=统计页 */
    mod('aa-enrollment', '选课管理', null, P('选课批次', '选课监控与名单', '重修免修报名')),
    /* ⑧ 考务管理：SM-10；考场/座位编排=考试批次内步骤、缓考审批=流程节点 */
    mod('aa-exams', '考务管理', null, P('考试批次工作台', '监考安排', '缓考与补考安排', '等级考试')),
    /* ⑨ 成绩管理：SM-11 录入-审核-发布-更正职责分离；现有 3 页承接，成绩任务链为 13B 后续施工 */
    mod('aa-grades', '成绩管理', '/admin/academic/grades', [
      PA('成绩查询（现有·课程成绩）', '/admin/academic/grades'),
      PA('学分修读（现有）', '/admin/academic/credits'),
      PA('补考重修成绩（现有）', '/admin/academic/makeup-retake'),
      ...P('成绩任务（录入·审核·发布）', '成绩更正与复核')
    ]),
    /* ⑩ 学籍管理：SM-02/03/14；异动单一入口+状态机；毕业资格审核为年度批次工作区（职校单一学历口径并入学籍，不单列二级） */
    mod('aa-roll', '学籍管理', '/admin/academic/students', [
      PA('在籍学生（现有·学业学生）', '/admin/academic/students'),
      ...P('学籍注册', '学籍异动', '毕业资格审核')
    ]),
    /* ⑪ 学业预警：SM-13；现有处置闭环（分派/干预/升级/关闭真接口）；挂科/学分/缺课等=工作台类型筛选 */
    mod('aa-warning', '学业预警', '/admin/academic/warnings', [
      PA('预警工作台（现有·预警学生）', '/admin/academic/warnings'),
      ...P('预警规则配置')
    ]),
    /* ⑫ 教材管理：目录→选用→征订→发放→费用台账 */
    mod('aa-textbooks', '教材管理', null, P('教材目录', '征订与发放')),
    /* ⑬ 教学质量与评教：督导独立角色强权限边界（只看质量，不改成绩/学籍） */
    mod('aa-quality', '教学质量与评教', null, P('评教任务', '督导听课与巡查', '教学事故与整改')),
    /* ⑭ 教务统计与归档：8 维统计口径 + append-only 归档；各业务统计/归档一律进此，不逐模块挂菜单 */
    mod('aa-stats-archive', '教务统计与归档', null, P('教务统计分析', '归档中心'))
    /* 实践教学（岗位实习/毕业设计）不设教务二级：主责在对应中心，教务侧仅毕业资格审核
     * 读取其结论（external-link 供数），不冒充教务已完成能力。 */
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

  /* ═══════════ 一级⑤：岗位实习中心（固定12个二级目录）═══════════ */
  grp('internship', '岗位实习中心', 'internship', [
    mod('in-workbench', '实习工作台', '/admin/internship', [
      I('实习总览', '/admin/internship'),
      PA('当前批次进度', '/admin/internship'),
      PA('我的待办', '/admin/internship'),
      I('风险提醒', '/admin/internship/risks'),
      PA('数据趋势', '/admin/internship')
    ]),
    mod('in-batch-rules', '批次与规则', '/admin/internship/batches?panel=list', [
      I('批次列表', '/admin/internship/batches?panel=list'),
      I('批次详情', '/admin/internship/batches?panel=list'),
      I('阶段配置', '/admin/internship/batches?panel=timeline'),
      I('打卡规则', '/admin/internship/batches?panel=rules'),
      I('周报规则', '/admin/internship/batches?panel=rules'),
      I('指导规则', '/admin/internship/batches?panel=rules'),
      I('评价规则', '/admin/internship/batches?panel=rules'),
      I('成绩规则', '/admin/internship/batches?panel=rules')
    ]),
    mod('in-students', '实习学生', '/admin/internship/students?panel=roster', [
      I('实习名单', '/admin/internship/students?panel=roster'),
      I('实习资格认定', '/admin/internship/students?panel=eligibility'),
      I('学生实习状态', '/admin/internship/students?panel=status'),
      I('学生实习详情', '/admin/internship/students?panel=roster'),
      I('学生材料', '/admin/internship/students?panel=materials')
    ]),
    mod('in-enterprise-position', '企业与岗位', '/admin/internship/enterprises?panel=list', [
      I('企业列表', '/admin/internship/enterprises?panel=list'),
      I('企业详情', '/admin/internship/enterprises?panel=detail'),
      I('企业联系人', '/admin/internship/enterprises?panel=contacts'),
      I('企业导师', '/admin/internship/enterprises?panel=mentor'),
      I('企业资质审核', '/admin/internship/enterprises?panel=qualification'),
      PA('企业黑名单', '/admin/internship/enterprises?panel=blacklist'),
      I('岗位列表', '/admin/internship/positions?panel=list'),
      I('岗位详情', '/admin/internship/positions?panel=detail'),
      I('岗位发布', '/admin/internship/positions?panel=publish'),
      I('岗位专业匹配', '/admin/internship/match?panel=major')
    ]),
    mod('in-match-assign', '匹配与分配', '/admin/internship/match?panel=intention', [
      I('学生意向', '/admin/internship/match?panel=intention'),
      I('岗位推荐', '/admin/internship/match?panel=recommend'),
      I('手动匹配', '/admin/internship/match?panel=manual'),
      I('批量匹配', '/admin/internship/match?panel=batch'),
      I('匹配冲突', '/admin/internship/match?panel=conflict'),
      I('匹配结果', '/admin/internship/match?panel=results'),
      I('指导老师分配', '/admin/internship/students?panel=mentor'),
      I('调岗退岗', '/admin/internship/students?panel=position'),
      I('分配日志', '/admin/internship/match?panel=stats')
    ]),
    mod('in-apply-agreement', '申请与协议', '/admin/internship/agreements', [
      PA('学生申请', '/admin/internship/agreements'),
      PA('自主实习申请', '/admin/internship/agreements'),
      PA('岗位申请', '/admin/internship/agreements'),
      PA('审核台账', '/admin/internship/agreements'),
      I('协议模板', '/admin/internship/agreement-templates'),
      I('协议发起', '/admin/internship/agreements'),
      I('三方确认', '/admin/internship/agreements'),
      I('协议变更', '/admin/internship/agreements'),
      I('协议归档', '/admin/internship/agreements')
    ]),
    mod('in-attendance-leave', '打卡与请假', '/admin/internship/attendance', [
      I('打卡记录', '/admin/internship/attendance'),
      I('补卡申请', '/admin/internship/attendance'),
      I('补卡审批', '/admin/internship/attendance'),
      I('缺卡异常', '/admin/internship/exceptions'),
      I('连续未打卡', '/admin/internship/risks'),
      I('实习请假', '/admin/internship/leaves'),
      I('请假审批', '/admin/internship/leaves'),
      I('销假管理', '/admin/internship/leaves'),
      I('超期未归', '/admin/internship/risks')
    ]),
    mod('in-weekly-task', '周报与任务', '/admin/internship/reports', [
      PA('实习计划', '/admin/internship/reports'),
      PA('实习任务', '/admin/internship/reports'),
      PA('日报提交', '/admin/internship/reports'),
      I('周报提交', '/admin/internship/reports'),
      PA('月报提交', '/admin/internship/reports'),
      I('周报批阅', '/admin/internship/reports'),
      I('周报退回', '/admin/internship/reports'),
      PA('周报问题', '/admin/internship/reports')
    ]),
    mod('in-guidance-visit', '指导与巡访', '/admin/internship/guidance', [
      PA('指导计划', '/admin/internship/guidance'),
      I('指导记录', '/admin/internship/guidance'),
      I('企业沟通', '/admin/internship/guidance'),
      PA('指导不足预警', '/admin/internship/guidance'),
      PA('巡访计划', '/admin/internship/guidance'),
      I('巡访记录', '/admin/internship/guidance'),
      I('巡访问题', '/admin/internship/guidance'),
      I('整改跟进', '/admin/internship/guidance')
    ]),
    mod('in-risk', '风险处置', '/admin/internship/risk-disposal', [
      I('风险看板', '/admin/internship/risks'),
      I('未落实岗位', '/admin/internship/risks'),
      I('长期未打卡', '/admin/internship/risks'),
      I('周报逾期', '/admin/internship/risks'),
      I('离岗异常', '/admin/internship/risks'),
      I('企业投诉', '/admin/internship/risk-disposal'),
      I('安全风险', '/admin/internship/risk-disposal'),
      I('实习中断', '/admin/internship/risk-disposal'),
      I('风险处置', '/admin/internship/risk-disposal'),
      I('风险跟进', '/admin/internship/risk-disposal'),
      I('风险关闭', '/admin/internship/risk-disposal')
    ]),
    mod('in-eval-score', '评价与成绩', '/admin/internship/enterprise-evals', [
      I('企业评价', '/admin/internship/enterprise-evals'),
      I('学生自评', '/admin/internship/student-evals'),
      PA('学生对企业评价', '/admin/internship/student-evals'),
      PA('学生对岗位评价', '/admin/internship/student-evals'),
      I('指导老师评价', '/admin/internship/student-evals'),
      I('综合成绩', '/admin/internship/scores'),
      I('成绩审核', '/admin/internship/scores'),
      I('成绩发布', '/admin/internship/scores'),
      I('成绩复核', '/admin/internship/scores')
    ]),
    mod('in-employment-archive-stats', '就业转化与归档统计', '/admin/employment', [
      I('就业跟进', '/admin/employment'),
      I('未就业帮扶', '/admin/employment/unemployed'),
      PA('实习归档', '/admin/employment/materials'),
      PA('实习档案包', '/admin/employment/materials'),
      PA('实习统计', '/admin/employment'),
      PA('企业统计', '/admin/internship/enterprises?panel=stats'),
      I('岗位统计', '/admin/internship/positions?panel=stats'),
      PA('学生成绩统计', '/admin/internship/scores')
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
      score = row.path.length + (splitNavRef(row.path).query ? 1000 : 0)
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
