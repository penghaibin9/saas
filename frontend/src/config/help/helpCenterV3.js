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
 * 不把尚未完成重新验真的历史节点塞进流程图；各领域按 V3-01~04 逐段扩展。
 * 角色筛选只做帮助相关性；文章内进一步解释 permissionCode + 数据范围 + 业务关系，真正鉴权仍以后端为准。
 */
export const HELP_V3_CORE_JOURNEYS = Object.freeze([
  {
    key: 'academic',
    title: '教务完整事实链',
    description: '按正式数据依赖从学籍一路走到毕业资格：学籍 → 培养方案/课程 → 教学任务 → 排课 → 选课 → 考务 → 成绩 → 学分/GPA → 补考重修 → 毕业资格。每个节点同时解释角色权限模板、数据范围和必要业务关系。',
    helpIds: [
      'aa-card-status-change',
      'aa-v3-program-course',
      'aa-v3-teaching-task',
      'aa-v3-schedule',
      'aa-card-selection-publish',
      'aa-card-exam-publish',
      'aa-card-grade-review-publish',
      'aa-v3-credit-gpa',
      'aa-v3-makeup-retake',
      'aa-v3-graduation-qualification'
    ]
  },
  {
    key: 'internship',
    title: '岗位实习核心办理链',
    description: '当前已核验学生申请、协议、过程办理、调岗退岗、企业评价、成绩，并已经按实习指导教师/学院管理员/学校管理员/审计角色解释权限模板、数据范围和稳定指导关系；批次、岗前合规、风险事故、学生鉴定和归档继续按 V3-02 验真扩展。',
    helpIds: [
      'in-v2-student-application',
      'in-v2-agreement',
      'in-v2-teacher-process',
      'in-v2-student-change',
      'in-v2-enterprise-eval',
      'in-v2-score'
    ]
  },
  {
    key: 'graduation',
    title: '毕业设计核心办理链',
    description: '覆盖选题、开题、答辩、成绩；任务书、中期、成果定稿、归档继续按 V3-03 验真后扩展。',
    helpIds: [
      'gd-v2-topic-selection',
      'gd-v2-proposal',
      'gd-v2-defense',
      'gd-v2-grade'
    ]
  },
  {
    key: 'student-affairs',
    title: '学工核心业务线',
    description: '当前正式发布风险关怀与学工归档；请假、奖助资助、宿舍、心理、违纪继续按 V3-04 重新验真后加入。',
    helpIds: [
      'sa-card-risk-handle',
      'sa-card-archive'
    ]
  }
])
