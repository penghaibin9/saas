/**
 * 门户模块登记表。key 必须与后端 portal-config.modules 对齐。
 * d1/d2：侧栏导航 SVG 双 path（1:1 取自设计交付稿 design_handoff）。
 * domain：对应 /mobile/{domain}/my 的域名；null 表示走 /mobile/me/* 专用端点。
 */
export const MODULES = [
  { key: 'dashboard', title: '首页工作台', path: 'home', domain: null, icon: '🏠',
    d1: 'M4 11.5 12 4l8 7.5', d2: 'M6 10.5V20h12v-9.5' },
  { key: 'profile', title: '我的档案', path: 'profile', domain: null, icon: '📄',
    d1: 'M5 4h14v16H5z', d2: 'M12 11a2.2 2.2 0 1 0 0-4.4 2.2 2.2 0 0 0 0 4.4M8 17c.4-2 2-3 4-3s3.6 1 4 3' },
  { key: 'academic', title: '教务学业', path: 'academic', domain: 'academic', icon: '📚',
    d1: 'M6 4h10a2 2 0 0 1 2 2v14H8a2 2 0 0 1-2-2z', d2: 'M6 18a2 2 0 0 1 2-2h10' },
  { key: 'graduation', title: '毕业设计', path: 'graduation', domain: 'graduation', icon: '🎓',
    d1: 'M2.5 8.5 12 4.5l9.5 4-9.5 4z', d2: 'M6.5 11v4.2c0 1.3 2.5 2.3 5.5 2.3s5.5-1 5.5-2.3V11M21.5 8.5V13' },
  { key: 'internship', title: '岗位实习', path: 'internship', domain: 'internship', icon: '🧑‍💼',
    d1: 'M4 8h16v11H4z', d2: 'M9 8V6a2 2 0 0 1 2-2h2a2 2 0 0 1 2 2v2M4 13h16' },
  { key: 'employment', title: '就业服务', path: 'employment', domain: 'employment', icon: '💼',
    d1: 'M5 20V5a1 1 0 0 1 1-1h8a1 1 0 0 1 1 1v15', d2: 'M15 9h3a1 1 0 0 1 1 1v10M8 8h3M8 12h3M8 16h3' },
  { key: 'campusService', title: '学工事务', path: 'campus-service', domain: 'campus-service', icon: '🏫',
    d1: 'M8 5h8v2H8z', d2: 'M7 6H5v14h14V6h-2M9.3 13l1.8 1.8L15 11' },
  { key: 'orientation', title: '迎新报到', path: 'orientation', domain: 'orientation', icon: '🎒',
    d1: 'M6 3v18', d2: 'M6 4h11l-2 3 2 3H6' },
  { key: 'messages', title: '消息通知', path: 'messages', domain: null, icon: '🔔',
    d1: 'M6 9a6 6 0 0 1 12 0c0 5 2 6 2 6H4s2-1 2-6', d2: 'M10 20a2 2 0 0 0 4 0' }
]

// 办事大厅：一站式聚合入口，不含独立后端模块开关（README 明确），始终可见。
export const SERVICE_HALL = {
  key: 'hall', title: '办事大厅', path: 'service-hall',
  d1: 'M4 4h7v7H4zM13 4h7v7h-7z', d2: 'M4 13h7v7H4zM13 13h7v7h-7z'
}

export function moduleByPath(path) {
  return MODULES.find((m) => m.path === path) || null
}
export function moduleByKey(key) {
  return MODULES.find((m) => m.key === key) || null
}
