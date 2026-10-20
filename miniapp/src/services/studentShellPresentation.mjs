// Display-only metadata. Never used for routes, permissions or business state.
const visuals = [
  [/报到|档案|资料/, 'user', 'blue'], [/宿舍|住宿/, 'home', 'teal'],
  [/请假|课表|校历|安排/, 'calendar', 'blue'], [/谈心|谈话/, 'message-dots', 'teal'],
  [/活动|二课|意向/, 'flag', 'amber'], [/违纪|预警/, 'shield-exclamation', 'red'],
  [/困难|减免|补助/, 'heart', 'red'], [/奖助|贷款/, 'database', 'blue'],
  [/岗位|企业|勤工|就业/, 'briefcase', 'teal'], [/成绩|学分|进度/, 'chart-bar', 'teal'],
  [/教材|选课|教育/, 'book', 'blue'], [/安全|保险|协议|确认/, 'shield-check', 'teal'],
  [/考试|答辩|考勤|打卡|鉴定/, 'clipboard-check', 'amber'], [/求助|反馈/, 'lifebuoy', 'blue'],
  [/办理|申请|材料|报告|任务|成果|毕设/, 'file-text', 'violet']
]
export function serviceVisual(label) {
  const match = visuals.find(([pattern]) => pattern.test(String(label || '')))
  return { icon: match?.[1] || 'file-text', tone: match?.[2] || 'blue' }
}
export function studentDateText(date = new Date()) {
  return `${date.getMonth() + 1}月${date.getDate()}日 星期${'日一二三四五六'[date.getDay()]}`
}
