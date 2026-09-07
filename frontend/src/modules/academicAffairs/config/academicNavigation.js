/** 教务业务入口投影。原目录保留完整路由/权限，按已确认的业务责任组织呈现。 */
const LABELS = {
  '组织结构同步': '组织核对',
  '教务看板（教务中心）': '运行总览',
  '学业过程总览（现有）': '学业过程',
  '当前学期设置': '当前学期',
  '分流批次与分配': '分流批次',
  '学生志愿与录取结果': '分流志愿与录取',
  '分流统计（同页志愿名单）': '分流统计',
  '年级/专业教学计划（培养方案）': '专业教学计划',
  '学期教学计划/课程开设计划（教学任务）': '学期开课计划',
  '计划归档（教务归档）': '计划归档',
  '人工排课工作台（课表维护）': '手工排课',
  '课表批次 / 排课': '课表批次',
  '发起调停课（调课/停课/补课）': '调停课申请',
  '课堂考勤统计（出勤/迟到/旷课/请假汇总）': '课堂考勤',
  '选课批次控制台（批次/课程/名单/统计）': '选课批次',
  '我的选课（学生自助）': '本人选课',
  '选课结果（并入学生课表，见课表三视图）': '选课结果',
  '考务控制台（批次/课程/考场/座位/监考/巡考/异常/统计）': '考务安排',
  '座位表/准考证/门贴打印': '考务打印',
  '缓考审批（并入控制台/学生小程序申请）': '缓考审批',
  '等级考务（四六级/普通话/技能证书）': '等级考试',
  '重修免修申请（学生自助）': '重修免修申请',
  '成绩录入（含暂存/提交）': '成绩录入',
  '成绩认定/课程替代': '成绩认定与替代',
  '学院审核（待审核/通过/退回）': '学院成绩审核',
  '教务发布（发布/退回/归档）': '成绩发布',
  '成绩更正申请与审核': '成绩更正',
  '成绩复查复审（学生发起）': '成绩复查',
  '毕业资格预审': '毕业预审',
  '费用结清（待接入财务系统）': '费用结清（待接入）',
  '评教批次（结果分级）': '评价批次',
  '学生评教(小程序)': '学生评教',
  '运行质量看板 + 质量报告导出': '质量看板',
  '归档批次 + 9数据域完整性检查 + 学期封存': '归档与封存',
  '教务总览（15 项指标 · 多维筛选 · 下钻 · 导出）': '统计总览',
  '工作量申报审核（教师申报）': '工作量申报审核'
}

const WORKSPACE_ICONS = {
  'aa-big-screen': 'DataBoard',
  'aa-dashboard': 'Monitor',
  'aa-terms': 'SetUp',
  'aa-student-status': 'User',
  'aa-training': 'Reading',
  'aa-teaching-tasks': 'List',
  'aa-schedule': 'Calendar',
  'aa-course-selection': 'Select',
  'aa-daily': 'Clock',
  'aa-exam': 'Tickets',
  'aa-grades': 'TrendCharts',
  'aa-graduation-qual': 'Medal',
  'aa-textbooks': 'Notebook',
  'aa-resources': 'OfficeBuilding',
  'aa-quality': 'CircleCheck',
  'aa-stats': 'DataAnalysis',
  'aa-archive': 'FolderChecked'
}

export const ACADEMIC_WORKSPACES = [
  ['aa-big-screen', '教务大屏', ['aa-big-screen']],
  ['aa-dashboard', '教务总览', ['aa-dashboard']],
  ['aa-terms', '教务基础', ['aa-terms', 'aa-calendar', 'aa-orgs']],
  ['aa-student-status', '学籍管理', ['aa-student-status', 'aa-registration', 'aa-major-split', 'aa-status-change', 'aa-warning']],
  ['aa-training', '培养与课程', ['aa-training', 'aa-courses', 'aa-teaching-plan']],
  ['aa-teaching-tasks', '开课管理', ['aa-teaching-tasks']],
  ['aa-schedule', '排课与课表', ['aa-schedule', 'aa-scheduling']],
  ['aa-course-selection', '选课管理', ['aa-course-selection']],
  ['aa-daily', '日常教学', ['aa-schedule-change', 'aa-attendance']],
  ['aa-exam', '考务管理', ['aa-exam']],
  ['aa-grades', '成绩管理', ['aa-grades', 'aa-grade-review', 'aa-makeup']],
  ['aa-graduation-qual', '毕业管理', ['aa-graduation-qual']],
  ['aa-textbooks', '教材管理', ['aa-textbooks']],
  ['aa-resources', '教学资源', ['aa-resources']],
  ['aa-quality', '教学质量', ['aa-quality', 'aa-evaluation']],
  ['aa-stats', '教务统计', ['aa-stats']],
  ['aa-archive', '教务归档', ['aa-archive']]
]

// 常驻入口按完整工作区/责任队列选择；其余入口保留在分组目录、搜索、收藏与深链中。
const PRIMARY = {
  'aa-big-screen': ['教务运行大屏'],
  'aa-dashboard': ['运行总览', '教务待办', '今日教学运行', '学业过程'],
  'aa-terms': ['学期管理', '校历管理', '作息时间', '学院管理', '专业管理', '行政班管理', '教学班管理'],
  'aa-student-status': ['学籍名册', '学籍信息更正', '注册批次', '注册资格核验', '分流批次', '异动台账', '异动审批', '预警扫描与列表', '预警跟进'],
  'aa-training': ['方案列表', '课程列表', '方案审核', '方案发布', '方案变更', '专业教学计划'],
  'aa-teaching-tasks': ['教学任务批次', '任课教师分配', '合班拆班', '教学任务确认', '教师任务确认', '教学任务调整', '工作量申报审核'],
  'aa-schedule': ['课表批次', '排课规则', '自动排课', '冲突报告', '课表发布', '班级课表', '教师课表', '学生课表'],
  'aa-course-selection': ['选课批次', '选课规则', '补选管理', '冲突检测', '选课结果', '选课归档'],
  'aa-daily': ['调停课台账', '调停课申请', '调停课审批', '课堂考勤', '考勤场次查询', '教室预约', '实训室预约'],
  'aa-exam': ['考务安排', '缓考审批', '补考批次', '缓考合流', '毕业清考', '等级考试', '考务打印'],
  'aa-grades': ['成绩总览', '成绩录入', '学院成绩审核', '成绩发布', '成绩更正', '成绩复查', '学生成绩单', '重修审批', '免修审批', '成绩认定与替代'],
  'aa-graduation-qual': ['毕业预审', '审核批次', '毕业学生名单', '毕业资格终审', '审核结果', '毕业证书管理'],
  'aa-textbooks': ['教材目录', '教材选用', '审核备案', '征订到货', '教材库存', '费用台账'],
  'aa-resources': ['教室资源', '实训室资源', '设备资源', '资源占用', '资源冲突', '资源维修'],
  'aa-quality': ['质量看板', '评价批次', '评价统计', '督导听课', '巡课记录', '教学检查', '教学事故', '质量整改', '申诉审核'],
  'aa-stats': ['统计总览', '学籍与注册', '开课与教学运行', '考试与成绩', '学业与毕业', '师资与资源', '报表与快照'],
  'aa-archive': ['归档与封存', '归档缺失提醒', '归档导出']
}

export const STATS_TOPICS = [
  { key: 'overview', label: '统计总览', tabs: ['overview'], description: '从开学准备到毕业审核，查看当前范围内的教务运行指标。' },
  { key: 'student', label: '学籍与注册', tabs: ['registration', 'statusChange'], description: '核对注册完成情况与已生效的学籍异动。' },
  { key: 'teaching', label: '开课与教学运行', tabs: ['course', 'teachingTask', 'schedule', 'courseSelection'], description: '查看课程供给、任务确认、课表发布和选课情况。' },
  { key: 'assessment', label: '考试与成绩', tabs: ['exam', 'grade'], description: '查看考试准备、成绩发布和学生课程考核情况。' },
  { key: 'completion', label: '学业与毕业', tabs: ['warning', 'graduation'], description: '识别未关闭的学业风险，核对毕业资格达成情况。' },
  { key: 'resources', label: '师资与资源', tabs: ['workload', 'resource'], description: '查看教师教学任务量和教室资源使用情况。' },
  { key: 'reports', label: '报表与快照', tabs: ['export', 'snapshot'], description: '按业务用途导出报表，查看已保存的统计快照。' }
]

export function statsTopic(tab) {
  return STATS_TOPICS.find(topic => topic.tabs.includes(tab)) || STATS_TOPICS[0]
}

function destination(source, leaf) {
  const path = leaf.path || ''
  if (path === '/admin/academic-affairs/workload-review') return 'aa-teaching-tasks'
  if (source.key === 'aa-makeup' && /tab=(makeup|deferred|clearance)(?:&|$)/.test(path)) return 'aa-exam'
  if (/\/(classroom-bookings|resources\/lab-bookings)$/.test(path)) return 'aa-daily'
  if (path.startsWith('/admin/academic-affairs/stats') && !path.includes('scope=roster')) return 'aa-stats'
  if (source.key === 'aa-teaching-plan' && path.startsWith('/admin/academic-affairs/teaching-tasks')) return 'aa-teaching-tasks'
  if (path === '/admin/academic-affairs/archive') return 'aa-archive'
  return ACADEMIC_WORKSPACES.find(([, , sources]) => sources.includes(source.key))?.[0]
}

export function buildAcademicNavigation(sourceModules) {
  const result = ACADEMIC_WORKSPACES.map(([key, label, sources]) => ({
    ...sourceModules.find(source => source.key === sources[0]), key, label, menuIcon: WORKSPACE_ICONS[key], children: []
  }))
  for (const source of sourceModules) source.children.forEach((leaf, index) => {
    const target = result.find(group => group.key === destination(source, leaf))
    if (!target) throw new Error(`Unmapped academic module: ${source.key}`)
    let label = LABELS[leaf.label] || leaf.label
    if (source.key === 'aa-stats') {
      const tab = new URL(leaf.path, 'http://navigation.local').searchParams.get('tab') || 'overview'
      const topic = STATS_TOPICS.find(item => item.tabs[0] === tab)
      if (topic && leaf.path.startsWith('/admin/academic-affairs/stats')) label = topic.label
    }
    const statisticsTab = target.key === 'aa-stats' && leaf.path.startsWith('/admin/academic-affairs/stats')
      ? new URL(leaf.path, 'http://navigation.local').searchParams.get('tab') || 'overview' : null
    const topic = statisticsTab && statsTopic(statisticsTab)
    target.children.push({ ...leaf, label, sourceKey: `${source.key}:${index}`, menuSection: source.label,
      ...(topic ? { menuParentPath: `/admin/academic-affairs/stats${topic.tabs[0] === 'overview' ? '' : `?tab=${topic.tabs[0]}`}` } : {}),
      menuSecondary: !PRIMARY[target.key].includes(label),
      searchAliases: [...new Set([leaf.label, LABELS[leaf.label], source.label, ...(leaf.searchAliases || [])].filter(Boolean))]
    })
  })
  // 精确相同的地址和权限才合并呈现；原条目仍保留用于逐条迁移审计。
  for (const group of result) {
    group.children.sort((a, b) => Number(!a.sourceKey.startsWith(`${group.key}:`)) - Number(!b.sourceKey.startsWith(`${group.key}:`)))
    const seen = new Map()
    for (const leaf of group.children) {
      if (leaf.hidden) continue
      const key = JSON.stringify([leaf.path, leaf.permissionKey, leaf.permissionAny, leaf.permissionAll, leaf.status, leaf.disabled])
      const primary = seen.get(key)
      if (primary) {
        primary.searchAliases = [...new Set([...primary.searchAliases, leaf.label, ...leaf.searchAliases])]
        primary.menuSecondary = primary.menuSecondary && leaf.menuSecondary
        leaf.hidden = true
        leaf.menuDuplicateOf = primary.sourceKey
      } else seen.set(key, leaf)
    }
    // 展示标题不承担权限裁决，仍由每一个原叶子的权限决定是否可见。
    group.path = group.children.find(leaf => !leaf.hidden && !leaf.menuSecondary)?.path || group.path
  }
  return result
}
