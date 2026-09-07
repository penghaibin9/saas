// 只登记学生门户已经存在的页面。模块开关继续取自 portal-config，服务端仍裁决业务权限。
const page = (id, title, short, to) => ({ id, title, short, to })
const group = (id, title, short, module, pages) => ({ id, title, short, module, pages })
export const WORKSPACE_CENTERS = [
  { id: 'student', title: '在校服务', groups: [
    group('work', '我的办理', '办理', 'dashboard', [page('home', '我的工作台', '待办', '/home'), page('hall', '办事大厅', '大厅', '/service-hall')]),
    group('leave', '请假返校', '请假', 'campusService', [page('leave', '请假与返校', '请假', '/campus-service?tab=leave')]),
    group('dorm', '我的住宿', '住宿', 'campusService', [page('dorm', '住宿与调宿', '住宿', '/campus-service?tab=dorm')]),
    group('aid', '困难认定', '认定', 'campusService', [page('aid', '申请与认定进度', '认定', '/campus-service?tab=aid')]),
    group('funding', '奖助服务', '奖助', 'campusService', [page('funding', '奖助申请与进度', '奖助', '/campus-service?tab=funding')]),
    group('activity', '活动成长', '活动', 'campusService', [page('activity', '活动与第二课堂', '活动', '/campus-service?tab=activity')]),
    group('care', '谈心关怀', '关怀', 'campusService', [page('talk', '谈心谈话', '谈话', '/campus-service?tab=talk'), page('psy', '心理自评', '自评', '/campus-service?tab=psy')]),
    group('discipline', '决定与申诉', '申诉', 'campusService', [page('discipline', '本人处分与申诉', '申诉', '/campus-service?tab=discipline')]),
    group('profile', '我的档案', '档案', 'profile', [page('profile', '本人资料', '资料', '/profile')]),
    group('materials', '材料补交', '材料', 'campusService', [page('materials', '补交材料', '补交', '/materials')]),
    group('orientation', '迎新报到', '报到', 'orientation', [page('orientation', '报到进度', '进度', '/orientation'), page('orientation-info', '信息核验', '核验', '/orientation/info'), page('orientation-arrival', '到校计划', '到校', '/orientation/arrival'), page('orientation-materials', '报到材料', '材料', '/orientation/materials'), page('orientation-green', '绿色通道', '通道', '/orientation/green-channel')]),
    group('departure', '离校手续', '离校', 'dashboard', [page('departure', '离校办理', '离校', '/departure')]),
    group('messages', '消息通知', '消息', 'messages', [page('messages', '我的消息', '消息', '/messages')])
  ] },
  { id: 'academic', title: '教务学业', groups: [
    group('academic-home', '学业工作台', '学业', 'academic', [page('academic', '学业总览', '总览', '/academic')]),
    group('academic-study', '注册与安排', '安排', 'academic', [page('registration', '学期注册', '注册', '/academic/registration'), page('schedule', '我的课表', '课表', '/academic/schedule'), page('selection', '网上选课', '选课', '/academic/selection'), page('attendance', '课堂考勤', '考勤', '/academic/attendance'), page('calendar', '校历', '校历', '/academic/calendar')]),
    group('academic-exam', '成绩与考试', '成绩', 'academic', [page('grades', '我的成绩', '成绩', '/academic/grades'), page('evaluation', '学生评教', '评教', '/academic/evaluation'), page('recheck', '成绩复查', '复查', '/academic/recheck'), page('exam', '考试与缓考', '考试', '/academic/exam'), page('makeup', '补考重修', '补考', '/academic/makeup'), page('clearance', '清考结果', '清考', '/academic/clearance')]),
    group('academic-growth', '培养与毕业', '培养', 'academic', [page('status', '学籍与异动', '学籍', '/academic/status'), page('credits', '学分修读', '学分', '/academic/credits'), page('warning', '学业预警', '预警', '/academic/warning'), page('textbook', '教材领用', '教材', '/academic/textbook'), page('level-exam', '等级考试', '考级', '/academic/level-exam'), page('major-split', '专业分流', '分流', '/academic/major-split'), page('recognition', '成绩认定', '认定', '/academic/recognition'), page('academic-graduation', '毕业资格自查', '毕业', '/academic/graduation')]),
    group('academic-all', '全部教务事项', '全部', 'academic', [page('academic-all', '全部教务事项', '全部', '/academic/all')])
  ] },
  { id: 'graduation', title: '毕业设计', groups: [
    group('graduation', '毕业设计', '毕设', 'graduation', [page('graduation', '毕业设计工作台', '总览', '/graduation'), page('graduation-materials', '毕业设计材料库', '材料', '/graduation/materials'), page('graduation-feedback', '反馈与重提', '反馈', '/graduation/feedback'), page('graduation-evidence', '归档证据包', '归档', '/graduation/evidence-package')])
  ] },
  { id: 'internship', title: '岗位实习', groups: [
    group('internship', '我的实习', '实习', 'internship', [page('internship', '实习工作台', '总览', '/internship'), page('internship-selection', '岗位选择', '岗位', '/internship/selection'), page('internship-profile', '实习简历', '简历', '/internship/profile'), page('internship-compliance', '上岗合规与安全教育', '安全', '/internship/compliance')])
  ] },
  { id: 'employment', title: '就业服务', groups: [group('employment', '我的就业', '就业', 'employment', [page('employment', '就业办理', '就业', '/employment')])] }
]

export function availableCenters(config) {
  return WORKSPACE_CENTERS.map(center => ({ ...center, groups: center.groups.filter(item => item.module === 'dashboard' || (config?.enabled && config.modules?.[item.module] === true)) })).filter(center => center.groups.length)
}
export function flattenPages(centers) {
  return centers.flatMap(center => center.groups.flatMap(group => group.pages.map(item => ({ ...item, centerId: center.id, groupId: group.id, module: group.module, trail: `${center.title} / ${group.title}` }))))
}
export function pageForRoute(route, pages) {
  const base = route.path === '/campus-service' ? `/campus-service?tab=${['leave', 'dorm', 'aid', 'funding', 'activity', 'talk', 'psy', 'discipline'].includes(route.query?.tab) ? route.query.tab : 'leave'}` : route.path
  return pages.find(item => item.to === base) || null
}
export function searchPages(pages, query, currentCenter, recent = []) {
  const text = String(query || '').trim().toLowerCase()
  return pages.filter(item => !text || `${item.title} ${item.trail}`.toLowerCase().includes(text)).map(item => ({ item, score: (item.title === text ? 100 : item.title.includes(text) ? 30 : 0) + (item.centerId === currentCenter ? 10 : 0) + (recent.includes(item.id) ? 5 : 0) })).sort((a, b) => b.score - a.score).map(row => row.item)
}

export const DEFAULT_SHORTCUTS = ['home', 'profile', 'leave', 'dorm', 'schedule', 'materials']
export const SHORTCUT_COLORS = ['blue', 'teal', 'purple', 'amber', 'coral']
export function normalizePreferences(value, pages) {
  const allowed = new Set(pages.map(item => item.id))
  const ids = list => [...new Set(Array.isArray(list) ? list.filter(id => allowed.has(id)) : [])].slice(0, 16)
  const rail = mode => ['auto', 'compact', 'full'].includes(mode) ? mode : 'compact'
  const shortcuts = ids(Array.isArray(value?.shortcuts) ? value.shortcuts : DEFAULT_SHORTCUTS).slice(0, 8)
  const appearance = Object.fromEntries(shortcuts.map(id => [id, { label: typeof value?.appearance?.[id]?.label === 'string' ? value.appearance[id].label.trim().slice(0, 12) : '', color: SHORTCUT_COLORS.includes(value?.appearance?.[id]?.color) ? value.appearance[id].color : SHORTCUT_COLORS[shortcuts.indexOf(id) % SHORTCUT_COLORS.length] }]))
  return { second: rail(value?.second), third: rail(value?.third), collapsed: value?.collapsed === true, shortcuts, appearance, tabs: ids(value?.tabs), theme: ['dark', 'blue', 'sage', 'plum'].includes(value?.theme) ? value.theme : 'blue' }
}
