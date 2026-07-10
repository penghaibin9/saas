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

  /* ═══════════ 一级②：学工中心 ═══════════
   * 2026-07-10 PC 三级目录重构·最终纠偏版（详见 docs/施工记录/13A-学工中心PC前端三级目录重构记录.md
   * 与 docs/modules/13A-学工中心页面树与路由设计.md 附录B）。二级数量不预设，按
   * 「独立业务对象 + 流程 + 角色权限 + 工作队列 + 统计归档边界」判定，共 13 个学工业务二级 + 1 个承接二级。
   * 收敛铁律：
   *  1) 正式菜单只显示真实可用页面（implemented/partial）；planned 仅 DEV 施工地图可见，
   *     不给学校正式角色展示（BasePortalLayout.isPlannerView）；
   *  2) 状态放筛选、流程节点放流程、详情内容放 Tab、风险类型放筛选、统计放看板、归档材料放材料清单；
   *     （本轮下沉：心理权限说明→页面说明；班级学生→班级详情Tab；请假代录→请假列表主按钮；
   *      超期未销假→状态筛选+风险来源；风险规则配置→模块设置/平台规则中心；资助画像→学生/困难学生详情；
   *      辅导员负责范围→班级与辅导员工作区内部配置）
   *  3) 已实现旧页面全部保留原路由原入口（/admin/student/*、/admin/campus-service/*、/admin/orientation/*），
   *     本轮不动路由、不动权限（moduleCode/permissionKey 未变，前端隐藏不替代后端校验）；
   *  4) 承接口径三分开统计，不得合并宣传：学工自身 implemented（学生画像 8 路由）／
   *     在校服务承接（8 页，t_cs_* 现有能力）／数字迎新 external-link（19 页归数字迎新中心，
   *     学工侧仅保留 1 个跨中心入口，迎新代码与路由零改动）。 */
  grp('student-affairs', '学工中心', 'studentAffairs', [
    /* ① 学工工作台（B包）：真正的学工总览/辅导员工作台尚未施工，如实标 planned，
     * 不得由在校服务页面冒充（承接入口统一放「在校服务与迎新（承接）」二级） */
    mod('sa-dashboard', '学工工作台', null, P('学工总览', '辅导员工作台')),
    /* ② 学生画像（学工自身已实现底座）：6 个菜单页 + 学生360 详情（动态路由不挂菜单；
     * 基础/学籍/家庭/宿舍/请假/资助/奖惩/心理关注摘要/谈话/风险轨迹 = 360 页签与「学工摘要」聚合卡） */
    mod('sa-profile', '学生画像', '/admin/student', [
      I('学生列表（学生主档）', '/admin/student/list'),
      I('学籍状态摘要', '/admin/student/status'),
      I('风险标签', '/admin/student/risk-tags'),
      I('信息更正审核', '/admin/student/corrections'),
      I('身份核验（现有）', '/admin/student/identity'),
      I('导入导出（现有）', '/admin/student/import-export')
    ]),
    /* ③ 班级与辅导员（B包）：班级学生=班级详情Tab；辅导员/班主任绑定与负责范围=工作区内部配置；
     * 班级各维统计=班级画像指标；辅导员考评（独立考评周期流程）并入辅导员维度 */
    mod('sa-classes', '班级与辅导员', null, P(
      '班级列表', '班级画像', '班级材料', '辅导员考评'
    )),
    /* ④ 宿舍与公寓（B包）：楼栋/房间/床位=房源管理一页三级树；夜不归宿并入宿舍异常（13A 设计 11-7）；
     * 调宿审批=详情页动作；智能排宿/公寓纪律/文明寝室=能力池暂缓；宿舍维修单走服务工单承接 */
    mod('sa-dorm', '宿舍与公寓', null, [
      ...P('房源管理（楼栋/房间/床位）'),
      I('入住管理（现有·宿舍服务）', '/admin/campus-service/dormitory'),
      ...P('调宿与退宿', '宿舍检查', '宿舍异常（含夜不归宿）', '宿舍统计')
    ]),
    /* ⑤ 请假销假（B包·V1 旗舰闭环）：请假代录=请假列表主按钮；超期未销假=台账状态筛选+风险来源；
     * 长假审批=审批节点升级；归寝核验=销假环节；请假规则配置=模块设置（接平台规则中心，不挂菜单） */
    mod('sa-leave', '请假销假', null, [
      I('请假审批', '/admin/campus-service/leave'),
      ...P('销假与续假', '请假台账', '请假统计')
    ]),
    /* ⑥ 困难认定（C包）：输出困难等级与困难学生库，供奖助勤贷补下游引用；
     * 班评/初审/院审/校复核=认定审核同页分节点（13A 设计 06-5）；材料上传=申请详情；
     * 资助画像=学生360/困难学生详情内容，不单挂菜单 */
    mod('sa-difficulty', '困难认定', null, P(
      '认定批次', '认定申请', '认定审核', '公示与异议', '困难学生库', '认定统计'
    )),
    /* ⑦ 奖助勤贷补（C包·困难认定下游）：资格校验引用困难学生库/困难等级与处分状态；
     * 国家/励志/校级奖学金=奖学金管理项目类型；绿色通道复用迎新 t_green_channel（承接不重建） */
    mod('sa-aid', '奖助勤贷补', null, [
      ...P('奖学金管理'),
      I('助学金管理（现有·奖助资助）', '/admin/campus-service/grants'),
      ...P('勤工助学', '助学贷款', '减免与临时补助', '名单审核与公示', '发放台账', '资助统计')
    ]),
    /* ⑧ 违纪处分（C包）：调查取证=处分详情材料区；处分公示=决定与送达环节；
     * 解除申请/审核=处分解除同页；学生申诉/复核=申诉复核 */
    mod('sa-discipline', '违纪处分', null, [
      I('违纪登记（现有）', '/admin/campus-service/discipline'),
      ...P('处分审批', '处分决定与送达', '处分解除', '申诉复核', '违纪台账', '处分统计')
    ]),
    /* ⑨ 心理关注（D包·敏感红线）：普通角色只见「需关注」标记，明细越权 403+审计，导出不含心理明细；
     * 心理权限说明=页面内说明（不挂菜单）；心理测评=P3 接口位暂缓；心理档案（强权限）进统计与档案 */
    mod('sa-mental', '心理关注', null, P(
      '心理关注名单', '心理预警摘要', '谈话转介与回访', '危机升级', '心理统计'
    )),
    /* ⑩ 谈心家校（C包）：重点/风险学生谈话=计划与记录筛选；家校通知/回执/家长授权=能力池暂缓 */
    mod('sa-talks', '谈心家校', null, P(
      '谈话计划', '谈话记录', '重点学生跟进', '家校联系人', '家校联系记录', '谈心统计'
    )),
    /* ⑪ 活动二课与社团（D包）：发布/报名审核/签到=活动闭环页内动作；二课积分族收敛一个入口；
     * 社团/学生会/干部/党团各收敛一个入口 */
    mod('sa-activities', '活动二课与社团', null, P(
      '活动管理', '活动报名与签到', '第二课堂积分', '志愿服务', '社团管理', '学生干部与组织', '党团建设', '活动统计'
    )),
    /* ⑫ 风险预警与处置（B包）：风险单（NEW→分派→处置→升级→关闭/重开）+待处置队列；
     * 学业/请假/夜不归宿/心理/违纪/经济困难/实习异常七类风险=风险学生来源筛选；
     * 风险跟进/关闭=处置详情动作；风险规则配置=模块设置（接平台规则中心，不挂菜单） */
    mod('sa-risk', '风险预警与处置', null, P(
      '风险看板', '风险学生', '风险处置'
    )),
    /* ⑬ 统计与档案（D包）：归档批次（收集→补缺→完整性审核→ARCHIVED）+学生档案包+全局统计驾驶舱；
     * 各业务「××归档」叶子=归档批次材料清单；学院对比/校级汇总=学工统计下钻维度 */
    mod('sa-stats-archive', '统计与档案', null, P(
      '学工统计', '学工归档', '学生档案包'
    )),
    /* ⑭ 在校服务与迎新：现有系统承接入口（内部口径=承接/external-link，正式显示名不得出现开发语言），
     * 不冒充学工工作台、不计入学工完成能力。
     * 在校服务 3 页 = t_cs_* 现有能力（收编时机=13A 新页面上线同一提交，见重叠归属裁定）；
     * 数字迎新 19 页归数字迎新中心（代码/路由零改动），学工侧仅此 1 个跨中心入口——
     * path 指向 /admin/orientation，前缀匹配保证所有迎新旧路由的侧栏高亮不劣化 */
    mod('sa-bridge', '在校服务与迎新', '/admin/campus-service', [
      I('服务工作台', '/admin/campus-service'),
      I('学生服务', '/admin/campus-service/students'),
      I('服务工单', '/admin/campus-service/work-orders'),
      I('数字迎新数据', '/admin/orientation')
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
