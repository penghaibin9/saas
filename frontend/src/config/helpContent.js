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

/** 分类聚合，供帮助中心页面侧栏渲染 */
export const HELP_SECTIONS = [
  { key: 'docs', label: '功能帮助', items: HELP_DOCS },
  { key: 'flows', label: '业务流程图', items: HELP_FLOWS }
]

/**
 * 帮助搜索：按标题 / 关键词 / 摘要匹配帮助文档与业务流程图。
 * @param {string} query 关键词
 * @returns {Array} [{ id, kind:'帮助文档'|'业务流程图', title }]
 */
export function searchHelp(query) {
  const q = (query || '').trim().toLowerCase()
  if (!q) return []
  const hit = (item) => {
    if (item.title.toLowerCase().includes(q)) return true
    if (item.summary && item.summary.toLowerCase().includes(q)) return true
    return (item.keywords || []).some((k) => {
      const kk = k.toLowerCase()
      return kk.includes(q) || q.includes(kk)
    })
  }
  const docs = HELP_DOCS.filter(hit).map((d) => ({ id: d.id, kind: '帮助文档', title: d.title }))
  const flows = HELP_FLOWS.filter(hit).map((f) => ({ id: f.id, kind: '业务流程图', title: f.title }))
  return [...docs, ...flows]
}

/** 按 id 取帮助条目（含类型），供帮助中心页面按 ?topic= 定位 */
export function getHelpById(id) {
  const doc = HELP_DOCS.find((d) => d.id === id)
  if (doc) return { type: 'doc', item: doc }
  const flow = HELP_FLOWS.find((f) => f.id === id)
  if (flow) return { type: 'flow', item: flow }
  return null
}
