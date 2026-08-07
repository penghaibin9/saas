export const HELP_V3_HOME_INTENTS = Object.freeze([
  {
    key: 'tasks',
    title: '我要办一件事',
    description: '直接找入口和步骤，照着做完成高频业务。',
    hint: '例如：录入成绩、发布选课、处理实习申请'
  },
  {
    key: 'problems',
    title: '我遇到问题',
    description: '先自查权限、状态、前置数据和错误提示，尽量不找人工。',
    hint: '例如：为什么提交不了、为什么按钮是灰的'
  },
  {
    key: 'journeys',
    title: '核心业务流程',
    description: '按业务链看现在在哪一步、下一步谁处理。',
    hint: '教务、岗位实习、毕业设计、学工'
  }
])

export const HELP_V3_QUICK_QUESTIONS = Object.freeze([
  { label: '为什么提交不了？', query: '提交' },
  { label: '为什么按钮是灰色或看不到？', query: '权限' },
  { label: '为什么被退回后不能继续？', query: '退回' },
  { label: '为什么看不到学生、班级或任务？', query: '数据范围' },
  { label: '为什么提示数据冲突 / 409？', query: '409' },
  { label: '为什么发布被阻断？', query: '发布' },
  { label: '为什么导入失败？错误行在哪？', query: '错误行' },
  { label: '为什么处理后待办还在？', query: '待办' }
])

/**
 * V3 核心业务地图只引用 verified-only 已发布 help id。
 * 角色筛选只做帮助相关性；文章内进一步解释 permissionCode + 数据范围 + 业务关系，真正鉴权仍以后端为准。
 */
export const HELP_V3_CORE_JOURNEYS = Object.freeze([
  {
    key: 'academic',
    title: '教务完整事实链',
    description: '按正式数据依赖从学籍一路走到毕业资格：学籍 → 培养方案/课程 → 教学任务 → 排课 → 选课 → 考务 → 成绩 → 学分/GPA → 补考重修 → 毕业资格。每个节点同时解释角色权限模板、数据范围和必要业务关系。',
    helpIds: [
      'aa-card-status-change', 'aa-v3-program-course', 'aa-v3-teaching-task', 'aa-v3-schedule',
      'aa-card-selection-publish', 'aa-card-exam-publish', 'aa-card-grade-review-publish',
      'aa-v3-credit-gpa', 'aa-v3-makeup-retake', 'aa-v3-graduation-qualification'
    ]
  },
  {
    key: 'internship',
    title: '岗位实习完整办理链',
    description: '按正式实习事实推进：批次 → 学生申请/正式去向 → 三方协议 → 岗前合规 → 周报/指导巡访 → 风险与事故 → 调岗退岗 → 企业评价 → 学生鉴定 → 综合成绩 → 实习归档。每个节点同时解释 permissionCode、数据范围、稳定指导关系/本人关系和当前状态。',
    helpIds: [
      'in-v3-batch-lifecycle', 'in-v2-student-application', 'in-v2-agreement', 'in-v3-onboard-compliance',
      'in-v2-teacher-process', 'in-v3-risk-incident', 'in-v2-student-change', 'in-v2-enterprise-eval',
      'in-v3-student-evaluation', 'in-v2-score', 'in-v3-archive'
    ]
  },
  {
    key: 'graduation',
    title: '毕业设计完整事实链',
    description: '按真实毕设证据推进：批次/规则 → 学生与导师 → 选题 → 任务书 → 开题 → 指导/中期整改 → 成果定稿 → 查重 → 独立评阅 → 答辩 → 成绩/申诉 → 归档。每个节点同时解释 permissionCode、学院/专业数据范围、稳定导师/评阅/答辩席位关系和当前状态；备案后证据进入不可变终态。',
    helpIds: [
      'gd-v3-batch-setup', 'gd-v3-student-mentor', 'gd-v2-topic-selection', 'gd-v3-taskbook',
      'gd-v2-proposal', 'gd-v3-guidance-midterm', 'gd-v3-final-submission', 'gd-v3-plagiarism',
      'gd-v3-review', 'gd-v2-defense', 'gd-v2-grade', 'gd-v3-archive'
    ]
  },
  {
    key: 'student-affairs',
    title: '学工四条高频办理线',
    description: '按真实业务组织四条高频线：①请假审批 → 续假/销假/逾期；②困难认定 → 困难学生库 → 奖学金/助学金；③处分登记 → 审批生效 → 送达/申诉 → 解除；④谈心谈话 → 家校/心理转介 → 风险中枢。风险处置和学工归档作为跨业务收口继续复用已核验任务卡。',
    helpIds: [
      'sa-v3-leave-lifecycle',
      'sa-v3-aid-funding',
      'sa-v3-discipline',
      'sa-v3-care-risk',
      'sa-card-risk-handle',
      'sa-card-archive'
    ]
  }
])
