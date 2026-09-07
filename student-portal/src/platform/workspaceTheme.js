export const WORKSPACE_THEMES = [
  { key: 'dark', label: '曜石黑', description: '石墨底色 · 冷蓝强调', bg: '#151619', surface: '#202126', header: '#1b1c20', soft: '#292d38', line: '#34363f', accent: '#95b1ff', ink: '#e9ecf3', muted: '#aeb6c6', on: '#162039' },
  { key: 'blue', label: '雾蓝', description: '雾蓝顶栏 · 清晰层次', bg: '#f4f7fc', surface: '#ffffff', header: '#edf3fc', soft: '#e5edfc', line: '#dce5f3', accent: '#285bb5', ink: '#203450', muted: '#586d89', on: '#ffffff' },
  { key: 'sage', label: '护眼绿', description: '雾绿底色 · 松绿强调', bg: '#f0f4ed', surface: '#fbfcf8', header: '#f7faf3', soft: '#e2eee4', line: '#d5e1d2', accent: '#347254', ink: '#243c31', muted: '#536d5d', on: '#ffffff' },
  { key: 'plum', label: '石墨紫', description: '灰白底色 · 柔紫点缀', bg: '#f3f3f6', surface: '#ffffff', header: '#f4f1f8', soft: '#eae4f4', line: '#e0daeb', accent: '#6954a3', ink: '#302d42', muted: '#6b617e', on: '#ffffff' }
]
export function normalizeTheme(key) {
  const legacy = { green: 'sage', purple: 'plum', orange: 'blue', pink: 'plum' }
  return WORKSPACE_THEMES.some(item => item.key === key) ? key : legacy[key] || 'blue'
}
export function themeTokens(key) {
  const t = WORKSPACE_THEMES.find(item => item.key === normalizeTheme(key))
  return {
    '--sp-primary': t.accent, '--sp-primary-rgb': [1, 3, 5].map(offset => parseInt(t.accent.slice(offset, offset + 2), 16)).join(','),
    '--pri-display': t.accent, '--pri': t.accent, '--pri-text': t.accent, '--pri-h': `color-mix(in srgb, ${t.accent} 85%, ${t.ink})`, '--pri-on': t.on,
    '--pri-50': t.soft, '--pri-100': t.soft, '--pri-500': t.accent, '--g1': t.soft, '--g2': t.accent,
    '--bg': t.bg, '--bg2': t.bg, '--surface': t.surface, '--surface-2': t.header, '--field-bg': t.header, '--shell-header': t.header,
    '--t1': t.ink, '--t2': t.ink, '--t3': t.muted, '--t4': t.muted, '--line': t.line, '--line2': t.line
  }
}
