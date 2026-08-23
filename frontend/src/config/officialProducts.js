export const OFFICIAL_PRODUCTS = {
  'academic-affairs': {
    slug: 'academic-affairs',
    key: 'academic',
    mark: '教',
    name: '教务系统',
    eyebrow: '教学运行数字化',
    heroTitle: '把培养方案、排课选课、考务成绩与学籍管理连成一条教学运行主线',
    summary: '面向教务处、二级学院、任课教师与学生，围绕教学计划、教学任务、排课、选课、考务、成绩、学籍和质量管理组织真实业务工作。',
    accent: '#6d52d9',
    soft: '#f2efff',
    roles: ['教务处', '二级学院', '任课教师', '学生'],
    highlights: [
      { title: '教学运行工作台', desc: '把当前阻断项、待办责任与下一动作放在首屏，减少老师在菜单里找问题。' },
      { title: '培养方案到教学任务', desc: '从课程与培养方案出发，把开课、教学任务和后续排课建立连续关系。' },
      { title: '排课、选课与考务', desc: '围绕正式学期、容量、考试批次与发布状态组织业务动作，避免前端自造业务真值。' },
      { title: '成绩、学籍与质量', desc: '成绩发布、更正、学籍异动、预警与质量分析保持可追溯的业务链。' }
    ],
    workflow: ['培养方案', '课程与教学任务', '排课', '选课', '考务', '成绩', '学籍', '质量与归档'],
    screenshots: [
      {
        src: '/official-site/academic.webp',
        title: '教务工作台',
        tag: '管理 PC · A级素材',
        desc: '真实教务工作台按业务阻断和责任工作组织首屏，让教务人员先看到要处理的事情，而不是先看到一排统计卡。'
      },
      {
        src: '/official-site/academic-schedule.webp',
        title: '排课与课表维护',
        tag: '管理 PC · 真实浏览器证据',
        desc: '真实排课工作区展示教学任务进入课表后的结果与维护上下文，演示数据来自隔离 Playwright 环境。'
      },
      {
        src: '/official-site/academic-registration.webp',
        title: '学生注册名单',
        tag: '管理 PC · 真实浏览器证据',
        desc: '通过真实名单、状态与批量办理入口展示学籍注册工作区，体现教务不是静态看板，而是可执行的业务台账。'
      },
      {
        src: '/official-site/academic-quality.webp',
        title: '教学质量',
        tag: '管理 PC · B级素材',
        desc: '用于展示教学质量模块的页面结构、指标入口与业务导航；截图来自隔离 E2E 环境，不把测试数据包装成学校运营结果。'
      }
    ],
    devices: [
      { label: '教务 / 管理 PC', title: '配置、发布、审核与治理', desc: '承载培养方案、排课、考务、成绩、学籍及质量管理等管理型工作。' },
      { label: '教师 PC', title: '教学任务与成绩办理', desc: '教师围绕本人教学任务进入对应工作区，权限与数据范围由后端业务事实约束。' },
      { label: '学生 PC / 移动端', title: '选课、查询与个人事项', desc: '学生端承接高频自助业务，当前素材包已提供移动端网上选课真实证据。', image: '/official-site/student-selection.webp' }
    ],
    relationMap: '/help/academic-affairs-relationship-overview.html'
  },
  'student-affairs': {
    slug: 'student-affairs',
    key: 'affairs',
    mark: '学',
    name: '学工中心',
    eyebrow: '学生事务与关怀协同',
    heroTitle: '以学生主档为中心，把日常事务、资助、风险关怀与辅导员工作连起来',
    summary: '面向学工处、辅导员、二级学院与学生，以学生主档和学生 360 为共同上下文，组织日常事务、奖助资助、宿舍、谈心关怀、风险处置与材料归档。',
    accent: '#cf7a13',
    soft: '#fff5e7',
    roles: ['学工处', '辅导员', '二级学院', '学生'],
    highlights: [
      { title: '学生主档与学生 360', desc: '从一名学生进入真实业务上下文，减少跨模块手工抄学号和重复定位。' },
      { title: '日常事务办理', desc: '围绕请假、宿舍、活动、材料等高频事项形成申请、审核、返回、补交与完成闭环。' },
      { title: '奖助与资助', desc: '把批次、资格、申请、审核与发放过程放在可追踪的业务链上。' },
      { title: '风险关怀与跟进', desc: '风险、谈心、心理转介等敏感工作保持权限边界、责任人和过程留痕。' }
    ],
    workflow: ['学生主档', '日常事务', '奖助资助', '宿舍与活动', '风险识别', '关怀跟进', '材料与归档'],
    screenshots: [
      {
        src: '/official-site/student-affairs-master.webp',
        title: '学生主档',
        tag: '管理 PC · A级素材',
        desc: '真实学生主档页面包含筛选、身份信息、风险提示与学生 360 入口，是学工业务跨模块协同的核心入口。'
      },
      {
        src: '/official-site/student-affairs-risk.webp',
        title: '风险预警工作区',
        tag: '管理 PC · 真实浏览器证据',
        desc: '真实演示数据下的风险预警工作区同时呈现风险分类、待处理对象与处置入口，适合说明“发现—跟进—留痕”的闭环。'
      },
      {
        src: '/official-site/student-affairs-talk.webp',
        title: '谈心谈话台账',
        tag: '辅导员 PC · 真实浏览器证据',
        desc: '谈心谈话台账展示学生、责任人、状态与记录入口，证明学工日常工作不是只停留在统计层。'
      },
      {
        src: '/official-site/student-affairs-dormitory.webp',
        title: '宿舍管理',
        tag: '管理 PC · 真实浏览器证据',
        desc: '宿舍工作区展示房间、入住、空床等真实业务结构，数据为隔离演示数据，不代表真实学校规模。'
      }
    ],
    devices: [
      { label: '学工 / 辅导员 PC', title: '学生工作主战场', desc: '承载学生主档、审批、风险、关怀、资助与材料等高频管理工作。' },
      { label: '学生 PC', title: '个人服务与办理入口', desc: '学生服务门户承接个人待办、材料、状态查询与生命周期服务。', image: '/official-site/student-portal.webp' },
      { label: '移动端', title: '高频事项随时办理', desc: '移动端作为学生和教师高频任务入口，与 PC 端共享同一业务状态；当前没有学工专用移动截图，因此官网不伪造。' }
    ],
    relationMap: '/help/student-affairs-relationship-overview.html'
  },
  graduation: {
    slug: 'graduation',
    key: 'graduation',
    mark: '毕',
    name: '毕业设计',
    eyebrow: '毕业设计全过程管理',
    heroTitle: '从选题到归档，把指导、材料、评审、答辩与成绩放进同一条毕设业务链',
    summary: '面向教务、二级学院、指导教师与学生，覆盖选题、开题、任务书、过程指导、中期检查、成果提交、评阅、答辩、成绩与归档。',
    accent: '#2563eb',
    soft: '#eaf2ff',
    roles: ['教务 / 学院', '指导教师', '评阅 / 答辩教师', '学生'],
    highlights: [
      { title: '选题与开题', desc: '学生、教师与学院围绕课题、指导关系和开题材料形成清晰的前置链路。' },
      { title: '任务书与过程指导', desc: '任务书版本、过程材料和指导记录保持可追踪，避免线下文件与系统状态脱节。' },
      { title: '成果、评阅与答辩', desc: '成果提交、评阅、查重、答辩安排与结果进入同一业务上下文。' },
      { title: '成绩、申诉与归档', desc: '成绩发布、申诉、更正与最终归档按正式状态流转，保留证据与版本。' }
    ],
    workflow: ['选题', '开题', '任务书', '过程指导', '中期检查', '成果提交', '评阅 / 查重', '答辩', '成绩', '归档'],
    screenshots: [
      {
        src: '/official-site/graduation-dashboard.webp',
        title: '毕业设计工作台',
        tag: '管理 PC · 真实浏览器证据',
        desc: '真实演示批次下的毕设工作台同时呈现阶段结论、待办与异常，让老师先看到本批次现在要处理什么。'
      },
      {
        src: '/official-site/graduation-final-review.webp',
        title: '成果评阅工作区',
        tag: '教师 PC · 真实浏览器证据',
        desc: '成果评阅页展示学生、版本、材料与审核动作，是毕业设计“材料—评阅—结果”闭环的直接证据。'
      },
      {
        src: '/official-site/graduation-process.webp',
        title: '过程指导',
        tag: '指导教师 PC · 真实浏览器证据',
        desc: '过程指导页展示学生队列、当前学生上下文与真实指导记录，体现指导工作可持续跟进并保留过程证据。'
      }
    ],
    devices: [
      { label: '教师移动端', title: '毕设指导工作台', desc: '教师在移动端查看毕业设计指导任务与过程事项。', image: '/official-site/teacher-graduation.webp' },
      { label: '教师移动端', title: '任务书处理', desc: '教师移动处理任务书相关工作，关键状态与 PC 业务链保持一致。', image: '/official-site/teacher-taskbook.webp' },
      { label: '学生 PC / 移动端', title: '材料提交与进度查询', desc: '学生围绕本人课题、材料、节点与结果办理，避免在不同渠道重复找状态。' }
    ],
    relationMap: '/help/graduation-module-relationship-map.html'
  },
  internship: {
    slug: 'internship',
    key: 'internship',
    mark: '实',
    name: '岗位实习',
    eyebrow: '实习全过程与风险闭环',
    heroTitle: '把企业、岗位、协议、过程监管、风险处置与考核归档放在一条实习主线上',
    summary: '面向实习管理部门、学院、指导教师、学生与企业，覆盖实习批次、企业岗位、申请与协议、打卡周报、指导巡访、风险事件、评价、成绩和归档。',
    accent: '#059669',
    soft: '#e8f8f2',
    roles: ['实习管理部门', '学院 / 指导教师', '学生', '企业'],
    highlights: [
      { title: '批次与过程总览', desc: '首屏同时呈现当前批次、流程、关键进度与风险，让老师先得到结论。' },
      { title: '企业与岗位协同', desc: '企业库、岗位、协议与学生实习关系在同一业务域内管理。' },
      { title: '过程监管与指导', desc: '打卡、周报、指导、巡访等过程事项形成持续可跟进的工作链。' },
      { title: '风险、评价与归档', desc: '风险事件、企业评价、学校评价、成绩与归档保持清晰的状态和责任边界。' }
    ],
    workflow: ['批次', '企业与岗位', '学生申请', '协议', '过程监管', '指导巡访', '风险处置', '评价', '成绩', '归档'],
    screenshots: [
      {
        src: '/official-site/internship.webp',
        title: '岗位实习总览',
        tag: '管理 PC · A级素材',
        desc: '真实岗位实习总览把批次、流程、进度与风险放在同一首屏，是官网展示实习闭环最强的产品证据。'
      },
      {
        src: '/official-site/internship-risk.webp',
        title: '风险处置看板',
        tag: '管理 PC · 真实浏览器证据',
        desc: '真实演示数据下的风险处置看板展示风险类型、学生对象、责任人与处置入口，适合解释实习过程监管如何落到具体事项。'
      },
      {
        src: '/official-site/internship-guidance.webp',
        title: '指导巡访管理',
        tag: '指导教师 PC · 真实浏览器证据',
        desc: '指导巡访工作区展示学生队列、指导记录与当前实习上下文，证明系统不仅记录结果，也覆盖持续指导过程。'
      },
      {
        src: '/official-site/internship-students.webp',
        title: '学生实习台账',
        tag: '管理 PC · 真实浏览器证据',
        desc: '学生实习台账展示学生、企业、岗位、状态与业务操作入口，数据来自隔离 Playwright 演示租户。'
      },
      {
        src: '/official-site/internship-enterprises.webp',
        title: '企业库',
        tag: '管理 PC · B级素材',
        desc: '展示企业信息与实习业务协同入口，企业数据来自隔离测试环境，不作为真实客户案例。'
      }
    ],
    devices: [
      { label: '教师 / 管理 PC', title: '监管与指导工作台', desc: '批次、企业、学生、协议、过程、风险、评价与归档集中在正式管理工作区。' },
      { label: '学生 PC / 移动端', title: '实习过程办理', desc: '学生围绕个人实习关系办理高频过程事项；当前没有实习移动专图，因此此处只陈述真实能力，不放假图。' },
      { label: '企业 PC', title: '企业注册 / 登录', desc: '企业端承接岗位、协同与评价。首次注册由学校邀请激活，不提供开放式自由注册。', enterprise: true }
    ],
    relationMap: '/help/internship-module-relationship-map.html'
  }
}

export const OFFICIAL_PRODUCT_LIST = [
  OFFICIAL_PRODUCTS['academic-affairs'],
  OFFICIAL_PRODUCTS['student-affairs'],
  OFFICIAL_PRODUCTS.graduation,
  OFFICIAL_PRODUCTS.internship
]

export function getOfficialProduct(slug) {
  return OFFICIAL_PRODUCTS[slug] || null
}
