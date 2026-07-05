/**
 * 门户模块登记表。key 必须与后端 portal-config.modules 对齐。
 * domain：对应 /mobile/{domain}/my 的域名；null 表示走 /mobile/me/* 专用端点。
 */
export const MODULES = [
  { key: 'dashboard', title: '首页概览', path: 'home', domain: null, icon: '🏠' },
  { key: 'profile', title: '我的档案', path: 'profile', domain: null, icon: '📄' },
  { key: 'orientation', title: '迎新报到', path: 'orientation', domain: 'orientation', icon: '🎒' },
  { key: 'campusService', title: '在校服务', path: 'campus-service', domain: 'campus-service', icon: '🏫' },
  { key: 'academic', title: '学业过程', path: 'academic', domain: 'academic', icon: '📚' },
  { key: 'internship', title: '岗位实习', path: 'internship', domain: 'internship', icon: '🧑‍💼' },
  { key: 'graduation', title: '毕业设计', path: 'graduation', domain: 'graduation', icon: '🎓' },
  { key: 'employment', title: '就业服务', path: 'employment', domain: 'employment', icon: '💼' },
  { key: 'messages', title: '消息中心', path: 'messages', domain: null, icon: '🔔' }
]

export function moduleByPath(path) {
  return MODULES.find((m) => m.path === path) || null
}
export function moduleByKey(key) {
  return MODULES.find((m) => m.key === key) || null
}
