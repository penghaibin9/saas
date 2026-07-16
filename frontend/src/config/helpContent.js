/**
 * 帮助中心内容源（PC-HELP-CENTER）。
 *
 * 定位：本文件是「帮助文档 + 业务流程图」的唯一数据源，供：
 *   ① 帮助中心页面 AdminHelpView.vue 渲染；
 *   ② 顶部「功能/帮助」搜索框索引（searchHelp）。
 *
 * 原则：
 *   - 内容均对应系统「真实存在」的模块与业务流程（依据 13A/13B 设计口径），非编造；
 *   - 无对应前端页面的深化功能不写入（不做假入口）；
 *   - 纯静态内容，不依赖后端。
 */
import { INTERNSHIP_HELP_CARDS } from '@/config/help/internshipHelpCards'
import { GRADUATION_HELP_CARDS } from '@/config/help/graduationHelpCards'
import { STUDENT_AFFAIRS_HELP_CARDS } from '@/config/help/studentAffairsHelpCards'

/** 功能帮助文档：对现有模块/高频操作的使用说明 */
export const HELP_DOCS = [
  {
    id: 'doc-workbench',
    title: '工作台与「我的常用」',
    module: '工作台',
    keywords: ['工作台', '我的常用', '收藏', '待办', '审批中心', '领导驾驶舱', '首页'],
    summary: '登录后默认进入工作台，集中处理每天的待办与常用入口。',
    points: [
      '工作台聚合：我的工作台、我的待办、审批中心、领导驾驶舱。',
      '任意模块卡片右上角点 ☆ 可固定到顶部「我的常用」，按登录人记忆、刷新不丢。',
      '再次点 ★ 可从「我的常用」移除；只会显示你当前有权限的模块。'
    ]
  },
  {
    id: 'doc-student-affairs',
    title: '学工中心：学生画像 / 数字迎新 / 在校服务',
    module: '学工中心',
    keywords: ['学工中心', '学生画像', '学生主档', '学籍', '身份核验', '风险标签'],
    summary: '学工中心负责学生事务：学生画像（主档/身份/风险）、数字迎新、在校服务。',
    points: [
      '学生画像：学生主档、学籍状态、身份核验、信息更正审核、风险标签、导入导出。',
      '进入学工中心后，中间栏顶部可在「学生画像 / 数字迎新 / 在校服务」间切换。',
      '不同角色的数据范围不同：辅导员只见本人管理的学生，学院老师只见本学院。'
    ]
  },
  {
    id: 'doc-orientation',
    title: '数字迎新：新生报到全流程',
    module: '学工中心 · 数字迎新',
    keywords: ['数字迎新', '迎新', '新生报到', '报到进度', '绿色通道', '缴费', '材料审核', '宿舍入住', '异常学生'],
    summary: '数字迎新覆盖新生从预报到到入住的全过程管理。',
    points: [
      '迎新看板总览报到进度；新生报到管理逐人报到状态。',
      '缴费/绿色通道处理学费缴纳与困难生绿色通道。',
      '材料审核、宿舍入住确认、异常学生逐项跟进。'
    ]
  },
  {
    id: 'doc-campus-leave',
    title: '在校服务：请假、奖助、宿舍、违纪',
    module: '学工中心 · 在校服务',
    keywords: ['在校服务', '请假', '销假', '请假审批', '奖助', '资助', '宿舍', '违纪', '处分', '服务工单'],
    summary: '在校服务集中处理学生日常事务与审批。',
    points: [
      '请假审批：学生发起，辅导员审批，超天数按流程上报学院。',
      '奖助资助、宿舍服务、违纪处分、服务工单分页处理。',
      '相关流程可在「业务流程图 · 请假审批流程」查看。'
    ]
  },
  {
    id: 'doc-academic',
    title: '教务中心：成绩、学分、补考重修、学业预警',
    module: '教务中心',
    keywords: ['教务中心', '学业过程', '成绩', '成绩录入', '学分', '补考', '重修', '学业预警', '课程'],
    summary: '教务中心管理学业过程：课程成绩、学分修读、补考重修、学业预警。',
    points: [
      '成绩录入按「平时+期末」比例加权计算总评。',
      '挂科自动触发学业预警，进入预警名单供跟进。',
      '学分修读、补考重修缓考免修分页管理。'
    ]
  },
  {
    id: 'doc-graduation',
    title: '毕业设计中心：选题到答辩',
    module: '毕业设计中心',
    keywords: ['毕业设计', '毕设', '选题', '开题', '成果提交', '查重', '答辩', '导师'],
    summary: '毕业设计中心管理毕设全过程。',
    points: [
      '选题管理、开题材料批阅、成果提交、答辩安排逐环节推进。',
      '毕设学生列表可查看每人进度与导师分配。',
      '完整环节见「业务流程图 · 毕业设计全流程」。'
    ]
  },
  {
    id: 'doc-internship',
    title: '岗位实习中心：打卡、周报、风险、就业',
    module: '岗位实习中心',
    keywords: ['岗位实习', '实习', '打卡', '打卡异常', '周报', '风险学生', '就业', '就业服务', '未就业帮扶', '企业岗位'],
    summary: '岗位实习中心管理实习过程与就业跟进。',
    points: [
      '实习学生、打卡异常、周报批阅、实习风险学生分页处理。',
      '就业服务包含就业学生、材料审核、未就业帮扶、企业与岗位资源。',
      '流程见「业务流程图 · 岗位实习流程」。'
    ]
  },
  {
    id: 'doc-system',
    title: '系统管理：用户、角色、菜单、数据范围',
    module: '系统管理',
    keywords: ['系统管理', '用户', '账号', '角色', '权限', '菜单', '数据范围', '组织', '品牌', '日志', '审计', '权限与流程'],
    summary: '系统管理承载底座配置：账号、角色权限、菜单、数据范围、组织、品牌、日志审计，以及权限与流程中心。',
    points: [
      '用户账号、角色权限、菜单权限、数据范围、组织结构、系统与品牌配置。',
      '权限与流程：流程模板、审批任务、角色与权限点管理。',
      '安全与审计：日志中心（高敏，部分角色不可见）。'
    ]
  },
  {
    id: 'doc-search',
    title: '顶部搜索：搜学生 与 搜功能',
    module: '通用',
    keywords: ['搜索', '搜学生', '搜功能', '快捷键', '学号', '姓名'],
    summary: '顶栏有两个搜索框，分别用于快速定位学生和功能页面。',
    points: [
      '左框「搜学生」：输入姓名或学号，结果按你的数据范围返回，点击进入学生360。',
      '右框「搜功能」：输入功能名（支持旧名如「数据中心」），可搜到功能页面、帮助文档、业务流程图。',
      '按 ⌘K / Ctrl+K 可快速聚焦功能搜索框。'
    ]
  },
  {
    id: 'doc-roles-scope',
    title: '角色与数据范围',
    module: '通用',
    keywords: ['角色', '数据范围', '权限', '辅导员', '教务', '学院', '可见'],
    summary: '不同角色看到的菜单与数据不同，由权限和数据范围共同决定。',
    points: [
      '顶栏「数据范围」胶囊显示你当前能看到的范围（如某学院）。',
      '辅导员只见本人管理学生；学院老师只见本学院；系统管理员见全校。',
      '菜单也随角色变化：无权限的模块不会出现在左侧导航与搜索结果中。'
    ]
  }
]

/** 业务流程图：核心业务的分步流程（依据 13A/13B 流程设计） */
export const HELP_FLOWS = [
  {
    id: 'flow-orientation',
    title: '数字迎新报到流程',
    keywords: ['迎新流程', '报到流程', '新生报到', '绿色通道', '宿舍入住'],
    summary: '新生从预报到到入住的标准流程。',
    steps: [
      { name: '预报到', who: '新生', detail: '小程序填报信息、确认到校时间' },
      { name: '缴费 / 绿色通道', who: '新生 / 财务', detail: '在线缴费；困难生走绿色通道缓缴' },
      { name: '材料审核', who: '迎新老师', detail: '核验录取通知书、身份材料' },
      { name: '现场报到', who: '迎新老师', detail: '扫码报到，更新报到状态' },
      { name: '宿舍入住', who: '宿管 / 辅导员', detail: '分配并确认入住' },
      { name: '异常处理', who: '辅导员', detail: '未报到 / 材料缺失学生逐一跟进' }
    ]
  },
  {
    id: 'flow-leave',
    title: '请假审批流程',
    keywords: ['请假流程', '请假审批', '销假', '审批'],
    summary: '学生请假到销假的审批链路。',
    steps: [
      { name: '发起请假', who: '学生', detail: '填写事由、起止时间、附件' },
      { name: '辅导员审批', who: '辅导员', detail: '审批通过 / 退回' },
      { name: '学院审批', who: '学院', detail: '超过约定天数时上报学院复核' },
      { name: '生效', who: '系统', detail: '通过后请假生效，记录在案' },
      { name: '销假', who: '学生 / 辅导员', detail: '返校后销假，闭环归档' }
    ]
  },
  {
    id: 'flow-sa-discipline',
    title: '违纪处分办理流程',
    keywords: ['违纪', '处分', '违纪处分', '处分流程', '申诉', '处分解除', '送达', '学工'],
    summary: '违纪从登记、逐级审核、生效送达到申诉、解除的完整办理链路。入口：学工中心 › 违纪处分。',
    steps: [
      { name: '登记违纪', who: '辅导员', detail: '在「违纪处分」登记违纪事实（不少于5字）与拟处分类型，先暂存为「已登记」' },
      { name: '提交审核', who: '辅导员', detail: '提交后自动进入学院初审并生成审批流；被退回可补充后再提交' },
      { name: '逐级审核', who: '学院 → 学工处 →（校级）', detail: '各级「通过/退回」；警告类到学工处复核即可，留校察看/开除等严重处分再加校级审核' },
      { name: '处分生效', who: '系统', detail: '终审通过后自动生效，同步学生360画像，并站内信告知学生' },
      { name: '登记送达', who: '辅导员', detail: '生效后登记送达方式（当面/邮寄/公告/留置），完成告知留痕' },
      { name: '学生申诉（可选）', who: '学生 → 学工处', detail: '生效后学生可申诉，复核结论：维持 / 变更 / 撤销；撤销即处分解除' },
      { name: '处分解除（可选）', who: '辅导员 → 学院 → 学工处', detail: '到期或表现良好可申请解除，三级审核通过后标记为「已解除」' }
    ]
  },
  {
    id: 'flow-sa-aid',
    title: '家庭经济困难认定流程',
    keywords: ['困难认定', '家庭经济困难', '困难生', '贫困认定', '公示', '异议', '学工', '资助'],
    summary: '家庭经济困难学生的申请、逐级审核、公示到入库的流程。入口：学工中心 › 困难认定。',
    steps: [
      { name: '受理申请', who: '辅导员', detail: '在「困难认定」按批次受理学生申请；家庭经济敏感信息加密独立存储、不进列表' },
      { name: '班级评议', who: '班级', detail: '班级民主评议后进入辅导员初审' },
      { name: '逐级审核', who: '辅导员 → 学院 → 学校', detail: '辅导员初审给出建议档次，学院复审、学校终审逐级「通过/退回」' },
      { name: '结果公示', who: '系统', detail: '终审通过进入公示（默认5天），公示期内可提异议' },
      { name: '异议复核（可选）', who: '学工处', detail: '有异议时复核：成立则驳回申请，不成立则维持' },
      { name: '认定通过', who: '系统', detail: '公示期满自动或人工确认通过，学生进入「困难学生库」并记档次历史' },
      { name: '档次调整（可选）', who: '辅导员', detail: '情况变化可发起档次调整，复核通过后更新档次' }
    ]
  },
  {
    id: 'flow-sa-funding',
    title: '奖助学金评定与发放流程',
    keywords: ['奖学金', '助学金', '奖助', '资助', '评定', '发放', '公示', '学工'],
    summary: '奖学金/助学金从资格校验、逐级评审、公示到发放台账的流程。入口：学工中心 › 奖助勤贷补。',
    steps: [
      { name: '受理申请', who: '辅导员', detail: '按资助项目批次受理学生申请' },
      { name: '资格校验', who: '系统', detail: '受理即硬校验：奖学金需在籍+无未解除处分+无挂科；助学金需已在困难库。不符当场拦截' },
      { name: '逐级评审', who: '辅导员 → 学院 → 学校', detail: '三级「通过/退回」评审' },
      { name: '结果公示', who: '系统', detail: '通过进入公示，期满自动或人工确认，进入发放台账' },
      { name: '生成发放单', who: '资助老师', detail: '按批次为获资助学生生成待发放记录（金额脱敏，仅授权角色见真实值）' },
      { name: '银行发放', who: '资助老师', detail: '登记发放成功（记批次号+卡后4位）或失败（记原因）' }
    ]
  },
  {
    id: 'flow-sa-risk',
    title: '学生风险预警与处置流程',
    keywords: ['风险', '风险预警', '风险处置', '预警', '销号', '升级', '重点学生', '学工'],
    summary: '学生风险从多来源建单、分派到处置销号的闭环。入口：学工中心 › 风险预警与处置。',
    steps: [
      { name: '生成风险单', who: '系统 / 辅导员', detail: '请假超期、学业预警、宿舍、心理、违纪等多来源自动建单，也可人工建单' },
      { name: '分派责任人', who: '学工处 / 辅导员', detail: '指派处置责任人，系统给责任人建待办并站内信提醒' },
      { name: '处置跟进', who: '责任人', detail: '记录处置措施（不少于5字），持续跟进（谈话/帮扶）' },
      { name: '转办 / 升级（可选）', who: '责任人', detail: '可转给新责任人；重大风险升级，等级自动升一级交上级接管' },
      { name: '超时自动升级', who: '系统', detail: '分派后72小时未处置自动升级，防止漏管' },
      { name: '关闭销号', who: '责任人', detail: '至少1条处置记录后填结论关闭，闭环并同步360画像；心理类明细仅授权角色可见' }
    ]
  },
  {
    id: 'flow-sa-talk',
    title: '谈心谈话流程',
    keywords: ['谈心', '谈话', '谈心谈话', '约谈', '重点跟进', '心理', '学工'],
    summary: '辅导员谈心谈话的计划、记录与跟进分流。入口：学工中心 › 谈心谈话。',
    steps: [
      { name: '建谈话计划', who: '辅导员', detail: '圈定学生建计划：约定时间则「已约定」，否则「待谈」' },
      { name: '开展并记录', who: '辅导员', detail: '谈话后填记录（内容不少于20字），并标记是否需要跟进' },
      { name: '跟进处理', who: '辅导员', detail: '需跟进的持续跟进；无需跟进可直接办结' },
      { name: '分流处置（可选）', who: '辅导员', detail: '可一键转「风险中枢」（心理类自动归心理来源）或转「家校联系」' },
      { name: '办结归档', who: '辅导员', detail: '完成后办结，同步学生360画像；心理类谈话内容仅授权角色可见全文' }
    ]
  },
  {
    id: 'flow-sa-family',
    title: '家校联系流程',
    keywords: ['家校', '家校联系', '家访', '家长', '回执', '联系记录', '学工'],
    summary: '家校沟通的登记与家长回执（据实为「登记+回执」轻流程，无多级审批）。入口：学工中心 › 谈心家校 › 家校联系。',
    steps: [
      { name: '登记联系', who: '辅导员', detail: '登记与家长的沟通（电话/家访等）、事由与结果' },
      { name: '查看联系方式', who: '辅导员', detail: '查看家长完整号码需填原因，系统留敏感查看审计' },
      { name: '等待回执', who: '系统', detail: '记录默认「待回执」' },
      { name: '登记回执', who: '辅导员', detail: '收到家长反馈后标记「已回执」，闭环（谈心谈话也可一键转生成一条家校联系记录）' }
    ]
  },
  {
    id: 'flow-sa-dorm',
    title: '宿舍管理与调宿流程',
    keywords: ['宿舍', '公寓', '入住', '调宿', '退宿', '宿舍检查', '床位', '学工'],
    summary: '宿舍从房源、入住到调宿、检查异常的管理。入口：学工中心 › 宿舍与公寓。',
    steps: [
      { name: '建房源', who: '宿管', detail: '楼→房→床一键铺满，床位默认「空闲」' },
      { name: '办理入住', who: '宿管', detail: '为学生分配床位（校验性别），床位转「已住」，回写入住记录' },
      { name: '申请调宿', who: '学生 / 辅导员', detail: '选定空闲目标床发起调宿' },
      { name: '两级审批', who: '辅导员 → 宿管', detail: '辅导员、宿管两级通过后系统自动执行换床' },
      { name: '宿舍检查', who: '宿管', detail: '卫生/安全/违禁/夜不归宿检查，登记结果' },
      { name: '异常处置', who: '宿管 / 辅导员', detail: '检查异常自动挂「待处理」，涉事学生联动生成风险单；处置说明后办结' },
      { name: '退宿', who: '宿管', detail: '退宿释放床位，床位回「空闲」' }
    ]
  },
  {
    id: 'flow-sa-activity',
    title: '第二课堂与活动学分流程',
    keywords: ['第二课堂', '活动', '活动学分', '志愿', '积分', '社团', '综合素质', '学工'],
    summary: '学生活动从发布、报名签到到学分入账的流程。入口：学工中心 › 活动二课与社团。',
    steps: [
      { name: '创建活动', who: '辅导员 / 组织者', detail: '建活动草稿，设名额与学分类型（第二课堂/德育/志愿时长）' },
      { name: '发布报名', who: '组织者', detail: '发布后学生移动端报名，名额满或截止自动拦截' },
      { name: '开展签到', who: '学生', detail: '活动进行中学生签到（仅已报名可签）' },
      { name: '确认入账', who: '组织者', detail: '活动结束后确认，为已签到学生生成学分（防重复），同步360' },
      { name: '志愿时长补录（可选）', who: '辅导员', detail: '补录志愿服务时长，确认后计入志愿学分' },
      { name: '积分申诉（可选）', who: '学生 → 辅导员', detail: '漏记/记错可申诉，通过则补记学分' }
    ]
  },
  {
    id: 'flow-sa-archive',
    title: '学工档案归档流程',
    keywords: ['归档', '档案', '学工档案', '档案包', '封存', '批次', '学工'],
    summary: '学工档案的批次收集、复核与封存（据实为逐级向前流转，无驳回分支）。入口：学工中心 › 统计与档案 › 学工归档。',
    steps: [
      { name: '建归档批次', who: '学工处', detail: '新建归档批次（草稿）' },
      { name: '收集档案', who: '学工处', detail: '圈定学生生成档案包（每生一份，标注缺项清单）' },
      { name: '学院复核', who: '学院', detail: '复核档案完整性' },
      { name: '学工处确认', who: '学工处', detail: '终确认归档' },
      { name: '封存导出', who: '系统', detail: '生成加密水印档案包，所有档案包封存' }
    ]
  },
  {
    id: 'flow-sa-counselor-eval',
    title: '辅导员考评流程',
    keywords: ['辅导员考评', '考评', '指标', '评分', '申诉', '学工'],
    summary: '辅导员考评的指标配置、评分发布与申诉复核。入口：学工中心 › 辅导员考评。',
    steps: [
      { name: '配置指标', who: '学工处 / 学院', detail: '建考评指标（权重、满分）' },
      { name: '录入评分', who: '学工处 / 学院', detail: '按指标给辅导员打分，草稿可改，系统自动算加权总分' },
      { name: '发布考评', who: '学工处 / 学院', detail: '发布后不可再改' },
      { name: '辅导员申诉（可选）', who: '辅导员', detail: '对本人已发布考评可申诉（理由不少于5字）' },
      { name: '复核结论', who: '学工处', detail: '维持或调整（调整可改分并重算总分）' }
    ]
  },
  {
    id: 'flow-academic-warning',
    title: '成绩录入到学业预警流程',
    keywords: ['成绩流程', '成绩录入', '学业预警', '挂科', '预警'],
    summary: '从成绩录入到触发学业预警与跟进。',
    steps: [
      { name: '成绩录入', who: '教务老师', detail: '录入平时成绩与期末成绩' },
      { name: '加权计算', who: '系统', detail: '按平时+期末比例计算总评' },
      { name: '挂科判定', who: '系统', detail: '总评不及格判定为挂科' },
      { name: '生成预警', who: '系统', detail: '达阈值自动进入学业预警名单' },
      { name: '跟进', who: '辅导员', detail: '约谈、帮扶并记录预警跟进' }
    ]
  },
  {
    id: 'flow-graduation',
    title: '毕业设计全流程',
    keywords: ['毕设流程', '毕业设计流程', '选题', '开题', '答辩'],
    summary: '毕业设计从选题到成绩评定的全过程。',
    steps: [
      { name: '选题', who: '学生 / 导师', detail: '选题、双向确认、导师分配' },
      { name: '开题', who: '导师', detail: '提交并批阅开题材料' },
      { name: '过程检查', who: '导师', detail: '中期检查进度' },
      { name: '成果提交', who: '学生', detail: '提交论文/作品成果' },
      { name: '查重', who: '系统 / 教务', detail: '记录查重结果' },
      { name: '答辩', who: '答辩组', detail: '安排并组织答辩' },
      { name: '成绩评定', who: '答辩组', detail: '评定毕设成绩、归档' }
    ]
  },
  {
    id: 'flow-internship',
    title: '岗位实习流程',
    keywords: ['实习流程', '岗位实习流程', '打卡', '周报', '就业跟进'],
    summary: '岗位实习从协议到就业跟进的全过程。',
    steps: [
      { name: '签订协议', who: '学生 / 企业 / 学校', detail: '三方实习协议' },
      { name: '打卡', who: '学生', detail: '小程序按日打卡' },
      { name: '打卡异常', who: '指导教师', detail: '缺卡/异常逐条处理' },
      { name: '周报批阅', who: '指导教师', detail: '学生提交周报，教师批阅' },
      { name: '风险处理', who: '指导教师', detail: '识别并跟进实习风险学生' },
      { name: '就业跟进', who: '就业老师', detail: '就业去向登记、未就业帮扶' }
    ]
  }
]

/**
 * 高频帮助任务卡：面向老师/管理员/学生/企业导师的「照着做」任务卡。
 * 数据源拆分在 config/help/*.js，本文件仅聚合与索引。
 * 每张卡：id / module / title / roles / route / entry / keywords / summary / steps / fields / faq / related。
 */
export const HELP_CARDS = [...STUDENT_AFFAIRS_HELP_CARDS, ...INTERNSHIP_HELP_CARDS, ...GRADUATION_HELP_CARDS]

/** 分类聚合，供帮助中心页面侧栏渲染 */
export const HELP_SECTIONS = [
  { key: 'docs', label: '功能帮助', items: HELP_DOCS },
  { key: 'flows', label: '业务流程图', items: HELP_FLOWS },
  { key: 'sa-cards', label: '学工中心 · 任务卡', items: STUDENT_AFFAIRS_HELP_CARDS },
  { key: 'in-cards', label: '岗位实习 · 任务卡', items: INTERNSHIP_HELP_CARDS },
  { key: 'gd-cards', label: '毕业设计 · 任务卡', items: GRADUATION_HELP_CARDS }
]

/**
 * 帮助搜索：按标题 / 关键词 / 摘要匹配帮助文档、业务流程图与高频任务卡。
 * 任务卡额外命中角色、入口路径，并返回 sub 供搜索结果显示「模块 · 角色 · 入口」。
 * @param {string} query 关键词
 * @returns {Array} [{ id, kind:'帮助文档'|'业务流程图'|'帮助任务卡', title, sub? }]
 */
export function searchHelp(query) {
  const q = (query || '').trim().toLowerCase()
  if (!q) return []
  const hit = (item) => {
    if (item.title.toLowerCase().includes(q)) return true
    if (item.summary && item.summary.toLowerCase().includes(q)) return true
    if ((item.roles || []).some((r) => r.toLowerCase().includes(q))) return true
    if (item.entry && item.entry.toLowerCase().includes(q)) return true
    return (item.keywords || []).some((k) => {
      const kk = k.toLowerCase()
      return kk.includes(q) || q.includes(kk)
    })
  }
  const docs = HELP_DOCS.filter(hit).map((d) => ({ id: d.id, kind: '帮助文档', title: d.title }))
  const flows = HELP_FLOWS.filter(hit).map((f) => ({ id: f.id, kind: '业务流程图', title: f.title }))
  const cards = HELP_CARDS.filter(hit).map((c) => ({
    id: c.id,
    kind: '帮助任务卡',
    title: c.title,
    sub: [c.module, (c.roles || []).join('、'), c.entry].filter(Boolean).join(' · ')
  }))
  return [...cards, ...docs, ...flows]
}

/** 按 id 取帮助条目（含类型），供帮助中心页面按 ?topic= 定位 */
export function getHelpById(id) {
  const card = HELP_CARDS.find((c) => c.id === id)
  if (card) return { type: 'card', item: card }
  const doc = HELP_DOCS.find((d) => d.id === id)
  if (doc) return { type: 'doc', item: doc }
  const flow = HELP_FLOWS.find((f) => f.id === id)
  if (flow) return { type: 'flow', item: flow }
  return null
}
