import {
  HELP_CARDS as BASE_HELP_CARDS,
  HELP_DOCS,
  HELP_FLOWS,
  HELP_SECTIONS as BASE_HELP_SECTIONS
} from './helpContent'
import { FOUNDATION_HELP_CARDS } from './help/foundationHelpCards'
import { MOBILE_HELP_CARDS } from './help/mobileHelpCards'
import { MOBILE_OPERATIONS_HELP_CARDS } from './help/mobileOperationsHelpCards'
import { STUDENT_DATA_HELP_CARDS } from './help/studentDataHelpCards'
import { SYSTEM_HELP_CARDS } from './help/systemHelpCards'
import { VERIFIED_HELP_OVERRIDES } from './help/verifiedHelpOverrides'

/**
 * 帮助中心运行时聚合层。
 *
 * 兼容既有 helpContent.js 的四大业务内容，同时把 PR #48 新核验的增量任务卡注册进
 * 同一套帮助数组。这里有意就地扩展既有数组：BasePortalLayout 仍然可以继续调用
 * helpContent.js 已有的 searchHelp / findHelpForRoute，而帮助中心模型直接从本文件读取
 * 同一份运行时集合，不产生第二套正文真值。
 *
 * 小程序卡只登记 mobilePath / entry，不登记 PC route，避免管理 PC 帮助中心产生一个
 * 点击后 404 的“前往办理页面”。历史大文件中经后端静态核验确认存在偏差的条目，
 * 通过 VERIFIED_HELP_OVERRIDES 在同一对象上就地修正，不并存两个同 id 条目。
 */
export {
  FOUNDATION_HELP_CARDS,
  HELP_DOCS,
  HELP_FLOWS,
  MOBILE_HELP_CARDS,
  MOBILE_OPERATIONS_HELP_CARDS,
  STUDENT_DATA_HELP_CARDS,
  SYSTEM_HELP_CARDS,
  VERIFIED_HELP_OVERRIDES
}

const ALL_MOBILE_HELP_CARDS = [...MOBILE_HELP_CARDS, ...MOBILE_OPERATIONS_HELP_CARDS]

function registerCards(cards) {
  const existingIds = new Set(BASE_HELP_CARDS.map((item) => item.id))
  for (let index = cards.length - 1; index >= 0; index -= 1) {
    const card = cards[index]
    if (!existingIds.has(card.id)) {
      BASE_HELP_CARDS.unshift(card)
      existingIds.add(card.id)
    }
  }
}

function applyVerifiedOverrides() {
  const byId = new Map(BASE_HELP_CARDS.map((item) => [item.id, item]))
  Object.entries(VERIFIED_HELP_OVERRIDES).forEach(([id, patch]) => {
    const target = byId.get(id)
    if (target) Object.assign(target, patch)
  })
}

registerCards(SYSTEM_HELP_CARDS)
registerCards(FOUNDATION_HELP_CARDS)
registerCards(STUDENT_DATA_HELP_CARDS)
registerCards(MOBILE_HELP_CARDS)
registerCards(MOBILE_OPERATIONS_HELP_CARDS)
applyVerifiedOverrides()

if (!BASE_HELP_SECTIONS.some((section) => section.key === 'system-cards')) {
  BASE_HELP_SECTIONS.unshift({
    key: 'system-cards',
    label: '系统管理 · 任务卡',
    items: SYSTEM_HELP_CARDS
  })
}
if (!BASE_HELP_SECTIONS.some((section) => section.key === 'foundation-cards')) {
  BASE_HELP_SECTIONS.unshift({
    key: 'foundation-cards',
    label: '开局与通用基础 · 任务卡',
    items: FOUNDATION_HELP_CARDS
  })
}
if (!BASE_HELP_SECTIONS.some((section) => section.key === 'student-data-cards')) {
  BASE_HELP_SECTIONS.unshift({
    key: 'student-data-cards',
    label: '学生主档与数据 · 任务卡',
    items: STUDENT_DATA_HELP_CARDS
  })
}
if (!BASE_HELP_SECTIONS.some((section) => section.key === 'mobile-cards')) {
  BASE_HELP_SECTIONS.unshift({
    key: 'mobile-cards',
    label: '微信小程序 · 高频任务',
    items: ALL_MOBILE_HELP_CARDS
  })
}

export const HELP_CARDS = BASE_HELP_CARDS
export const HELP_SECTIONS = BASE_HELP_SECTIONS

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

/** 顶栏“本页帮助”统一匹配。无 PC route 的小程序卡不会参与路由命中。 */
export function findHelpForRoute(fullPath) {
  const current = splitRoute(fullPath)
  if (!current.path) return null
  const cards = HELP_CARDS
    .filter((card) => card.route)
    .map((card) => ({ card, route: splitRoute(card.route) }))
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
