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
 * 这里故意不把尚未完成重新验真的历史节点塞进流程图：
 * “完整流程”会在 V3-01~04 按代码事实逐段扩展，当前首页只展示已经可信的办理链。
 */
export const HELP_V3_CORE_JOURNEYS = Object.freeze([
  {
    key: 'academic',
    title: '教务核心办理链',
    description: '当前先覆盖已重新验真的学籍、选课、考务、成绩链；培养方案、教学任务、排课、学分/GPA、补考重修、毕业资格继续按 V3-01 验真后扩展。',
    helpIds: [
      'aa-card-status-change',
      'aa-card-selection-round',
      'aa-card-selection-publish',
      'aa-card-exam-arrangement',
      'aa-card-exam-publish',
      'aa-card-grade-entry',
      'aa-card-grade-review-publish',
      'aa-card-grade-change'
    ]
  },
  {
    key: 'internship',
    title: '岗位实习核心办理链',
    description: '覆盖学生申请、协议、过程办理、调岗退岗、企业评价、成绩；岗前准备、归档等节点继续按 V3-02 验真后扩展。',
    helpIds: [
      'in-v2-student-application',
      'in-v2-agreement',
      'in-v2-teacher-process',
      'in-v2-change',
      'in-v2-enterprise-evaluation',
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
