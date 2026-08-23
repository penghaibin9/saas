import { OFFICIAL_CONTENT_UPDATED_AT } from './officialWebsiteStory.js'

export const OFFICIAL_SITE_CONTACT = Object.freeze({
  company: '湖南跃科信息工程有限公司',
  brand: '跃科',
  phone: '135 4966 6867',
  phoneHref: 'tel:13549666867',
  domain: 'hnyueke.com',
  canonicalOrigin: 'https://hnyueke.com'
})

const updated = OFFICIAL_CONTENT_UPDATED_AT

/**
 * 官网公开销售页面唯一口径。
 * - 只宣传当前代码/真实浏览器证据能够支持的能力；
 * - screenshots 只引用 /official-site 真实产品截图，不用 AI 重绘业务 UI；
 * - 路由、预渲染、sitemap、canonical、分享元数据均消费本清单；
 * - E2E 测试数据只能证明产品存在，不能包装成客户案例或运营规模。
 */
export const OFFICIAL_SALES_PAGES = Object.freeze([
  {
    key: 'product-center', path: '/products', type: 'solution', contentUpdatedAt: updated,
    title: '跃科产品中心｜职业院校学生全生命周期数字化平台', navTitle: '产品中心', eyebrow: '一套底座，覆盖学生关键业务阶段',
    description: '以岗位实习、毕业设计、学工、教务为四大重点产品，并连接数字迎新、教师工作台、学生门户、数据治理与实施交付。',
    hero: '不是把四套软件摆在一起，而是让关键学生业务共享同一套平台底座',
    screenshots: ['/official-site/workbench.webp', '/official-site/internship.webp', '/official-site/graduation-dashboard.webp', '/official-site/academic.webp'],
    keywords: ['职业院校学生全生命周期平台', '岗位实习系统', '毕业设计系统', '学工系统', '教务系统']
  },
  {
    key: 'product-academic-affairs', path: '/products/academic-affairs', type: 'product', contentUpdatedAt: updated,
    title: '教务系统｜培养方案、排课选课、考务成绩与学籍管理', navTitle: '教务系统', eyebrow: '教学运行数字化',
    description: '面向职业院校教务处、二级学院、任课教师与学生，贯通培养方案、教学任务、排课、选课、考务、成绩、学籍与教学质量。',
    hero: '让教务工作从“分散办理”变成一条连续、可追踪的教学运行主线',
    screenshots: ['/official-site/academic.webp', '/official-site/academic-schedule.webp', '/official-site/academic-registration.webp', '/official-site/academic-quality.webp'],
    keywords: ['职业院校教务系统', '排课系统', '选课系统', '成绩管理', '学籍管理']
  },
  {
    key: 'product-student-affairs', path: '/products/student-affairs', type: 'product', contentUpdatedAt: updated,
    title: '学工中心｜学生主档、资助、宿舍、风险关怀与辅导员工作', navTitle: '学工中心', eyebrow: '学生事务与关怀协同',
    description: '围绕学生主档与学生 360，连接学工处、辅导员、二级学院和学生的日常事务、奖助资助、宿舍、风险关怀与材料归档。',
    hero: '以学生为共同上下文，让学工事务、风险发现与辅导员跟进真正连起来',
    screenshots: ['/official-site/student-affairs-dashboard.png', '/official-site/student-affairs-master.png', '/official-site/student-affairs-risk.webp', '/official-site/student-affairs-talk.webp', '/official-site/student-affairs-dormitory.webp'],
    keywords: ['职业院校学工系统', '学生工作管理', '辅导员工作台', '学生主档', '学生风险预警']
  },
  {
    key: 'product-graduation', path: '/products/graduation', type: 'product', contentUpdatedAt: updated,
    title: '毕业设计系统｜选题、开题、指导、评阅、答辩与归档', navTitle: '毕业设计', eyebrow: '毕业设计全过程管理',
    description: '覆盖选题、开题、任务书、过程指导、中期检查、成果提交、评阅、答辩、成绩和归档，并支持教师移动端高频办理。',
    hero: '把材料、指导、评审和答辩放回同一条毕业设计业务链',
    screenshots: ['/official-site/graduation-dashboard.webp', '/official-site/graduation-final-review.webp', '/official-site/graduation-process.webp', '/official-site/teacher-graduation.webp', '/official-site/teacher-taskbook.webp'],
    keywords: ['毕业设计管理系统', '毕业论文管理', '开题管理', '答辩管理', '指导教师工作台']
  },
  {
    key: 'product-internship', path: '/products/internship', type: 'product', contentUpdatedAt: updated,
    title: '岗位实习系统｜企业岗位、协议、过程监管、风险处置与考核', navTitle: '岗位实习', eyebrow: '实习全过程与风险闭环',
    description: '面向学校、学院、指导教师、学生和企业，覆盖批次、企业岗位、申请、协议、打卡周报、指导巡访、风险事件、评价、成绩与归档。',
    hero: '从企业岗位到实习归档，把过程监管和风险处置真正做成闭环',
    screenshots: ['/official-site/internship.webp', '/official-site/internship-risk.webp', '/official-site/internship-guidance.webp', '/official-site/internship-students.webp', '/official-site/internship-enterprises.webp'],
    keywords: ['职业院校岗位实习系统', '实习管理系统', '三方协议', '实习风险管理', '企业协同']
  },
  {
    key: 'solution-lifecycle', path: '/solutions/student-lifecycle', type: 'solution', contentUpdatedAt: updated,
    title: '学生全生命周期解决方案｜入校到毕业就业的统一学生业务平台', navTitle: '学生全生命周期', eyebrow: '跨生命周期协同',
    description: '以统一学生身份、状态、权限与业务事实连接迎新、在校成长、教学运行、岗位实习、毕业设计与就业衔接，减少跨模块重复录入和状态割裂。',
    hero: '不是堆模块，而是让学生从入校到毕业就业始终处在同一条业务主线上',
    screenshots: ['/official-site/workbench.webp', '/official-site/student-portal.webp', '/official-site/leadership-cockpit.webp'],
    keywords: ['学生全生命周期管理', '职业院校学生管理平台', '学生数字化管理']
  },
  {
    key: 'solution-orientation', path: '/solutions/orientation', type: 'solution', contentUpdatedAt: updated,
    title: '数字迎新解决方案｜新生预报到、核验、宿舍、现场报到与统计', navTitle: '数字迎新', eyebrow: '新生入校第一站',
    description: '连接预报到信息、资格与材料核验、绿色通道、宿舍安排、现场报到、异常学生与迎新统计，让学校掌握每个新生走到哪一步。',
    hero: '让新生从到校前就开始在线报到，让现场核验和后续处理共享同一份进度',
    screenshots: ['/official-site/orientation-overview.webp', '/official-site/orientation-progress.webp'],
    keywords: ['数字迎新系统', '新生报到系统', '职业院校迎新', '绿色通道', '新生现场核验']
  },
  {
    key: 'solution-multi-terminal', path: '/solutions/multi-terminal', type: 'solution', contentUpdatedAt: updated,
    title: '多端协同方案｜管理 PC、教师 PC、学生 PC、微信小程序与 H5', navTitle: '多端协同', eyebrow: 'PC 与移动端协同',
    description: '管理端承担配置、审核和治理，教师端承担教学与指导任务，学生端承担自助办理，微信小程序与 H5 承接高频场景，共享同一业务状态与权限边界。',
    hero: '让老师、学生和管理人员在适合自己的终端完成同一件事',
    screenshots: ['/official-site/student-portal.webp', '/official-site/student-selection.webp', '/official-site/teacher-graduation.webp', '/official-site/teacher-taskbook.webp'],
    keywords: ['微信小程序校园', '教师工作台', '学生服务门户', 'H5', '多端协同']
  },
  {
    key: 'solution-teacher-workbench', path: '/solutions/teacher-workbench', type: 'solution', contentUpdatedAt: updated,
    title: '教师统一工作台｜待办、审批、消息、风险、教学与指导任务统一入口', navTitle: '教师工作台', eyebrow: '老师先看到结论和下一步',
    description: '把教师跨教务、学工、实习和毕业设计的高频任务聚合到工作台、审批和消息入口，让待办、风险、责任和下一动作更清晰。',
    hero: '减少在菜单里找事情，让老师打开系统就知道今天先处理什么',
    screenshots: ['/official-site/workbench.webp', '/official-site/approval-center.webp', '/official-site/message-center.webp', '/official-site/teacher-graduation.webp'],
    keywords: ['教师工作台', '审批中心', '消息中心', '教师待办中心', '辅导员工作台']
  },
  {
    key: 'solution-student-services', path: '/solutions/student-services', type: 'solution', contentUpdatedAt: updated,
    title: '学生服务门户｜个人待办、材料、选课与生命周期事项统一入口', navTitle: '学生服务门户', eyebrow: '学生高频自助服务',
    description: '为学生提供个人首页、待办、状态查询、材料办理与移动端高频业务入口，让学生只关注和自己有关的事项。',
    hero: '把“我现在要办什么、办到哪一步”放到学生自己的入口里',
    screenshots: ['/official-site/student-portal.webp', '/official-site/student-selection.webp'],
    keywords: ['学生服务门户', '学生办事大厅', '学生自助服务', '移动校园']
  },
  {
    key: 'platform', path: '/platform', type: 'solution', contentUpdatedAt: updated,
    title: '跃科平台能力｜多学校、组织身份、权限、数据范围、品牌与审计底座', navTitle: '平台能力', eyebrow: '一套底座托住所有业务',
    description: '以多学校租户、组织身份、角色权限、数据范围、学校品牌、工作台、数据交换与审计作为教务、学工、实习和毕设共享的平台底座。',
    hero: '客户买到的不只是业务页面，还有学校级身份、权限、数据和治理边界',
    screenshots: ['/official-site/workbench.webp', '/official-site/leadership-cockpit.webp'],
    keywords: ['教育 SaaS 平台', '多租户', '数据范围', '角色权限', '学校品牌', '审计']
  },
  {
    key: 'solution-security', path: '/solutions/security-governance', type: 'solution', contentUpdatedAt: updated,
    title: '多租户安全与数据治理｜权限、数据范围、审计与敏感操作留痕', navTitle: '安全与数据治理', eyebrow: '商业 SaaS 安全底座',
    description: '以多租户隔离、角色权限、数据范围、审计留痕和生产 fail-closed 机制作为业务系统的共同安全底座；不使用未经取得的认证作为宣传。',
    hero: '业务能跑通只是第一步，学校数据还需要始终处在明确的访问和审计边界内',
    screenshots: ['/official-site/workbench.webp'],
    keywords: ['教育 SaaS 多租户', '数据权限', '审计日志', '敏感访问', '安全治理']
  },
  {
    key: 'solution-integration', path: '/solutions/integration', type: 'solution', contentUpdatedAt: updated,
    title: '统一身份与系统集成方案｜标准 API、受控同步与学校现有系统协同', navTitle: '统一身份与集成', eyebrow: '减少信息孤岛',
    description: '围绕学校现有身份与业务系统设计标准 API、受控同步和集成方案，避免为每个业务模块重复建设账号和数据通道；具体单点登录协议以项目核验与对接方案为准。',
    hero: '让新平台接进学校现有体系，而不是再造一个新的信息孤岛',
    screenshots: ['/official-site/workbench.webp'],
    keywords: ['教育系统 API', '统一身份集成', '数据同步', '智慧校园系统集成']
  },
  {
    key: 'solution-deployment', path: '/solutions/deployment', type: 'solution', contentUpdatedAt: updated,
    title: '学校部署与上线方案｜MySQL、HTTPS、备份、上线检查与验收', navTitle: '部署与上线', eyebrow: '可部署、可维护、可交付',
    description: '围绕学校生产环境说明 MySQL、HTTPS/Nginx、健康检查、备份恢复、基础数据、权限、上线检查与验收，支持 SaaS 与私有化交付方案设计。',
    hero: '官网展示的不只是功能，也包括真正能部署、能检查、能维护的工程与实施能力',
    screenshots: ['/official-site/workbench.webp'],
    keywords: ['教育 SaaS 部署', '私有化部署', 'MySQL', 'Nginx HTTPS', '系统上线验收']
  },
  {
    key: 'service-delivery', path: '/services/delivery', type: 'service', contentUpdatedAt: updated,
    title: '实施交付与持续服务｜学校初始化、数据导入、联调、验收与升级', navTitle: '实施与服务', eyebrow: '从开通到持续运营',
    description: '围绕学校情况确认、组织主数据、用户角色、模块配置、历史数据导入、业务联调、上线检查、验收和后续升级组织交付流程。',
    hero: '系统上线不是终点，初始化、数据、验收和后续变更同样是产品的一部分',
    screenshots: ['/official-site/workbench.webp', '/official-site/student-portal.webp'],
    keywords: ['智慧校园实施', '教育软件培训', '数据迁移', '职业院校数字化交付']
  },
  {
    key: 'about', path: '/about', type: 'service', contentUpdatedAt: updated,
    title: '关于跃科｜专注职业院校学生业务数字化', navTitle: '关于跃科', eyebrow: '湖南跃科信息工程有限公司',
    description: '跃科围绕职业院校学生全生命周期业务建设产品，强调业务闭环、老师易用、多端高频、权限数据边界与可实施交付。',
    hero: '从学生生命周期出发，把学校每天真实发生的工作做成可持续运行的产品',
    screenshots: ['/official-site/workbench.webp', '/official-site/student-portal.webp'],
    keywords: ['湖南跃科信息工程有限公司', '跃科', '职业院校数字化', '学生全生命周期']
  },
  {
    key: 'privacy', path: '/privacy', type: 'legal', contentUpdatedAt: updated,
    title: '隐私政策｜跃科职业院校学生全生命周期平台', navTitle: '隐私政策', eyebrow: '信息保护与透明说明',
    description: '说明跃科官网在预约产品演示、访问与技术支持场景中的信息处理方式、使用范围和用户权利。',
    hero: '清楚说明官网会收集什么、为什么使用以及如何保护', screenshots: [],
    keywords: ['跃科隐私政策', '官网个人信息保护', '预约演示信息保护']
  },
  {
    key: 'terms', path: '/terms', type: 'legal', contentUpdatedAt: updated,
    title: '用户协议｜跃科职业院校学生全生命周期平台', navTitle: '用户协议', eyebrow: '官网与产品使用规则',
    description: '说明跃科官网公开内容、系统访问、知识产权、服务边界与责任限制等基本使用规则。',
    hero: '以明确边界保障官网访问和系统使用', screenshots: [],
    keywords: ['跃科用户协议', '官网使用条款', '系统使用规则']
  },
  {
    key: 'support', path: '/support', type: 'legal', contentUpdatedAt: updated,
    title: '技术支持｜跃科职业院校学生全生命周期平台', navTitle: '技术支持', eyebrow: '问题受理与服务协同',
    description: '提供跃科产品咨询、系统访问、问题反馈、实施交付与售后支持的联系入口和信息准备说明。',
    hero: '让问题带着必要上下文进入支持流程', screenshots: [],
    keywords: ['跃科技术支持', '职业院校软件售后', '系统问题反馈']
  },
  {
    key: 'contact-sales', path: '/contact', type: 'contact', contentUpdatedAt: updated,
    title: '联系跃科｜职业院校学生全生命周期 SaaS 咨询与方案沟通', navTitle: '联系跃科', eyebrow: '商务咨询',
    description: '联系湖南跃科信息工程有限公司，咨询岗位实习、毕业设计、学工、教务、数字迎新及学生全生命周期平台的产品能力、部署方式和项目合作。',
    hero: '把学校当前最难推进的学生业务流程告诉我们，从真实业务问题开始沟通',
    screenshots: ['/official-site/workbench.webp'],
    keywords: ['跃科', '湖南跃科信息工程有限公司', '职业院校软件', '智慧校园咨询']
  }
])

export const OFFICIAL_SALES_PAGE_MAP = Object.freeze(Object.fromEntries(OFFICIAL_SALES_PAGES.map((page) => [page.path, page])))

export const OFFICIAL_SEO_ROUTES = Object.freeze([
  { path: '/', title: '跃科｜职业院校学生全生命周期数字化平台', description: '贯通数字迎新、学工、教务、岗位实习、毕业设计与就业衔接，让老师围绕待办工作、学生高频事项移动办理、管理者看见进度与风险。', contentUpdatedAt: updated },
  ...OFFICIAL_SALES_PAGES.map((page) => ({ path: page.path, title: page.title, description: page.description, contentUpdatedAt: page.contentUpdatedAt }))
])

export function officialCanonicalUrl(path = '/') {
  const normalized = path === '/' ? '/' : `/${String(path || '').replace(/^\/+|\/+$/g, '')}`
  return `${OFFICIAL_SITE_CONTACT.canonicalOrigin}${normalized}`
}
