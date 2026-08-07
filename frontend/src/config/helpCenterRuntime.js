import {
  HELP_CARDS as BASE_HELP_CARDS,
  HELP_DOCS,
  HELP_FLOWS,
  HELP_SECTIONS as BASE_HELP_SECTIONS
} from './helpContent'
import { SYSTEM_HELP_CARDS } from './help/systemHelpCards'

/**
 * 帮助中心运行时聚合层。
 *
 * 兼容既有 helpContent.js 的四大业务内容，同时把 PR #48 新核验的系统管理
 * 任务卡接入同一套帮助搜索、本页帮助、深链与帮助中心模型。
 * helpContent.js 仍保留既有正文真值；新增系统卡按模块拆文件，避免继续膨胀单文件。
 */
export { HELP_DOCS, HELP_FLOWS, SYSTEM_HELP_CARDS }

export const HELP_CARDS = [...SYSTEM_HELP_CARDS, ...BASE_HELP_CARDS]

export const HELP_SECTIONS = [
  { key: 'system-cards', label: '系统管理 · 任务卡', items: SYSTEM_HELP_CARDS },
  ...BASE_HELP_SECTIONS
]

function hitHelp(item, query) {
  if (item.title && item.title.toLowerCase().includes(query)) return true
  if (item.summary && item.summary.toLowerCase().includes(query)) return true
  const roles = Array.isArray(item.roles) ? item.roles : item.role ? [item.role] : []
  if (roles.some((role) => String(role).toLowerCase().includes(query))) return true
  if (item.entry && item.entry.toLowerCase().includes(query)) return true
  return (item.keywords || []).some((keyword) => {
    const normalized = String(keyword).toLowerCase()
    return normalized.includes(query) || query.includes(normalized)
  })
}

/** 顶部功能 / 帮助搜索使用的统一帮助索引。 */
export function searchHelp(query) {
  const q = String(query || '').trim().toLowerCase()
  if (!q) return []
  const docs = HELP_DOCS.filter((item) => hitHelp(item, q)).map((item) => ({
    id: item.id,
    kind: '帮助文档',
    title: item.title
  }))
  const flows = HELP_FLOWS.filter((item) => hitHelp(item, q)).map((item) => ({
    id: item.id,
    kind: '业务流程图',
    title: item.title
  }))
  const cards = HELP_CARDS.filter((item) => hitHelp(item, q)).map((item) => ({
    id: item.id,
    kind: '帮助任务卡',
    title: item.title,
    sub: [item.module, (item.roles || []).join('、'), item.entry].filter(Boolean).join(' · ')
  }))
  return [...cards, ...docs, ...flows]
}

function splitRoute(route) {
  const [path, qs = ''] = String(route || '').split('?')
  const panel = new URLSearchParams(qs).get('panel') || ''
  return { path, panel }
}

/** 顶栏“本页帮助”统一匹配，包含新增系统管理任务卡。 */
export function findHelpForRoute(fullPath) {
  const current = splitRoute(fullPath)
  if (!current.path) return null
  const cards = HELP_CARDS.map((card) => ({ card, route: splitRoute(card.route) }))
  const exact = cards.find((item) => item.route.path === current.path && item.route.panel === current.panel)
  const samePath = exact || cards.find((item) => item.route.path === current.path)
  const prefix = samePath || cards
    .filter((item) => item.route.path && current.path.startsWith(item.route.path + '/'))
    .sort((a, b) => b.route.path.length - a.route.path.length)[0]
  return prefix ? { id: prefix.card.id, title: prefix.card.title } : null
}

/** 帮助中心 ?topic= 深链取条目。 */
export function getHelpById(id) {
  const card = HELP_CARDS.find((item) => item.id === id)
  if (card) return { type: 'card', item: card }
  const doc = HELP_DOCS.find((item) => item.id === id)
  if (doc) return { type: 'doc', item: doc }
  const flow = HELP_FLOWS.find((item) => item.id === id)
  if (flow) return { type: 'flow', item: flow }
  return null
}
