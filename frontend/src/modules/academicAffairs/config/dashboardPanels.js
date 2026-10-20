export const DASHBOARD_PANELS = {
  academicProgress: { title: '学业过程', description: '从成绩提交、学籍变动到预警处置和毕业审核，查看当前需要关注的学业事项。' },
  todos: { title: '教务待办', description: '按业务分类查看待处理事项，带着对象和办理上下文进入责任页面。' },
  todayTeaching: { title: '今日教学运行', description: '依据当前学期已发布课表查看今日安排；课表时段状态不代表实际到课。' },
  todayCourses: { title: '今日课程', description: '按节次查看今日课程、班级、任课教师及上课地点。' },
  gradeProgress: { title: '成绩提交进度', description: '关注未开始、录入中和退回的成绩任务，进入成绩工作区继续办理。' },
  examReminders: { title: '考试安排提醒', description: '查看近期已确认的考试安排，进入考务工作区核对完整名单。' },
  statusChangeReminders: { title: '学籍异动提醒', description: '查看在途学籍异动，进入原申请查看审批进度。' },
  warningReminders: { title: '学业预警提醒', description: '查看待处置学业预警，进入对应学生的跟进事项。' },
  graduationWarnings: { title: '毕业资格预警', description: '关注毕业预审异常、待复核及延期事项，查看对应结果与原因。' },
  scheduleChangeReminders: { title: '调停课提醒', description: '查看尚在审批中的调课、停课和补课申请。' },
  resourceOccupancy: { title: '教学资源占用', description: '根据教室字典、今日课表和已通过预约查看教室占用。' },
  dataTrends: { title: '教务数据趋势', description: '查看近 14 天已发生的业务量，不进行预测或插值。' }
}

export function dashboardPanel(value) {
  return typeof value === 'string' && Object.hasOwn(DASHBOARD_PANELS, value) ? value : ''
}

export function dashboardTodoRows(groups, category = '') {
  return (Array.isArray(groups) ? groups : [])
    .filter(group => !category || group.key === category)
    .flatMap(group => (Array.isArray(group.items) ? group.items : []).map(item => ({ ...item, categoryKey: group.key, categoryLabel: group.label })))
}
