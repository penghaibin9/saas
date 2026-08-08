import {
  HELP_CARDS as BASE_HELP_CARDS,
  HELP_DOCS,
  HELP_FLOWS,
  HELP_SECTIONS as BASE_HELP_SECTIONS
} from './helpContent'
import { ACADEMIC_AFFAIRS_CLEAN_HELP_CARDS } from './help/academicAffairsCleanHelpCards'
import { ACADEMIC_AFFAIRS_CORE_FLOW_HELP_CARDS } from './help/academicAffairsCoreFlowHelpCards'
import { ACADEMIC_AFFAIRS_LEGACY_EXCLUSIONS } from './help/academicAffairsVerifiedOverrides'
import { FOUNDATION_HELP_CARDS } from './help/foundationHelpCards'
import { GRADUATION_CLEAN_HELP_CARDS } from './help/graduationCleanHelpCards'
import { GRADUATION_CORE_FLOW_HELP_CARDS } from './help/graduationCoreFlowHelpCards'
import { HIGH_FREQUENCY_TROUBLESHOOTING_HELP_CARDS } from './help/highFrequencyTroubleshootingHelpCards'
import { HIGH_FREQUENCY_TROUBLESHOOTING_V305B_CARDS } from './help/highFrequencyTroubleshootingHelpCardsV305B'
import { INTERNSHIP_CLEAN_HELP_CARDS } from './help/internshipCleanHelpCards'
import { INTERNSHIP_CORE_FLOW_HELP_CARDS } from './help/internshipCoreFlowHelpCards'
import {
  EXCLUDED_LEGACY_HELP_IDS,
  LEGACY_HELP_EXCLUSIONS,
  VERIFIED_HELP_FLOW_OVERRIDES
} from './help/legacyHelpPolicy'
import { MOBILE_HELP_CARDS } from './help/mobileHelpCards'
import { MOBILE_OPERATIONS_HELP_CARDS } from './help/mobileOperationsHelpCards'
import { MOBILE_CLEAN_HELP_CARDS } from './help/mobileCleanHelpCards'
import { STUDENT_AFFAIRS_CLEAN_HELP_CARDS } from './help/studentAffairsCleanHelpCards'
import { STUDENT_AFFAIRS_CORE_FLOW_HELP_CARDS } from './help/studentAffairsCoreFlowHelpCards'
import { STUDENT_DATA_HELP_CARDS } from './help/studentDataHelpCards'
import { SYSTEM_HELP_CARDS } from './help/systemHelpCards'
import { VERIFIED_HELP_OVERRIDES } from './help/verifiedHelpOverrides'

export {
  ACADEMIC_AFFAIRS_CLEAN_HELP_CARDS,
  ACADEMIC_AFFAIRS_CORE_FLOW_HELP_CARDS,
  ACADEMIC_AFFAIRS_LEGACY_EXCLUSIONS,
  FOUNDATION_HELP_CARDS,
  GRADUATION_CLEAN_HELP_CARDS,
  GRADUATION_CORE_FLOW_HELP_CARDS,
  HIGH_FREQUENCY_TROUBLESHOOTING_HELP_CARDS,
  HIGH_FREQUENCY_TROUBLESHOOTING_V305B_CARDS,
  HELP_DOCS,
  HELP_FLOWS,
  INTERNSHIP_CLEAN_HELP_CARDS,
  INTERNSHIP_CORE_FLOW_HELP_CARDS,
  LEGACY_HELP_EXCLUSIONS,
  MOBILE_CLEAN_HELP_CARDS,
  MOBILE_HELP_CARDS,
  MOBILE_OPERATIONS_HELP_CARDS,
  STUDENT_AFFAIRS_CLEAN_HELP_CARDS,
  STUDENT_AFFAIRS_CORE_FLOW_HELP_CARDS,
  STUDENT_DATA_HELP_CARDS,
  SYSTEM_HELP_CARDS,
  VERIFIED_HELP_FLOW_OVERRIDES,
  VERIFIED_HELP_OVERRIDES
}

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

function replaceOrRegisterCards(cards) {
  for (let index = cards.length - 1; index >= 0; index -= 1) {
    const card = cards[index]
    const existingIndex = BASE_HELP_CARDS.findIndex((item) => item.id === card.id)
    if (existingIndex >= 0) BASE_HELP_CARDS.splice(existingIndex, 1, card)
    else BASE_HELP_CARDS.unshift(card)
  }
}

function applyCardOverrides(cardsById, overrides) {
  Object.entries(overrides || {}).forEach(([id, patch]) => {
    const target = cardsById.get(id)
    if (target) Object.assign(target, patch)
  })
}

function applyVerifiedOverrides() {
  const cardsById = new Map(BASE_HELP_CARDS.map((item) => [item.id, item]))
  applyCardOverrides(cardsById, VERIFIED_HELP_OVERRIDES)
  const flowsById = new Map(HELP_FLOWS.map((item) => [item.id, item]))
  Object.entries(VERIFIED_HELP_FLOW_OVERRIDES).forEach(([id, patch]) => {
    const target = flowsById.get(id)
    if (target) Object.assign(target, patch)
  })
}

function removeIdsInPlace(items, ids) {
  for (let index = items.length - 1; index >= 0; index -= 1) {
    if (ids.has(items[index]?.id)) items.splice(index, 1)
  }
}

function removeUnverifiedInPlace(items, verifiedIds, quarantineSink) {
  for (let index = items.length - 1; index >= 0; index -= 1) {
    const id = items[index]?.id
    if (!id || verifiedIds.has(id)) continue
    quarantineSink.add(id)
    items.splice(index, 1)
  }
}

function policyIds(kind) {
  return new Set([
    ...Object.keys((LEGACY_HELP_EXCLUSIONS[kind] || {})),
    ...Object.keys((ACADEMIC_AFFAIRS_LEGACY_EXCLUSIONS[kind] || {}))
  ])
}

function quarantineConfirmedStaleHelp() {
  const cardIds = policyIds('cards')
  const docIds = policyIds('docs')
  const flowIds = policyIds('flows')
  const allExcludedIds = new Set([...EXCLUDED_LEGACY_HELP_IDS, ...cardIds, ...docIds, ...flowIds])
  removeIdsInPlace(BASE_HELP_CARDS, cardIds)
  removeIdsInPlace(HELP_DOCS, docIds)
  removeIdsInPlace(HELP_FLOWS, flowIds)
  BASE_HELP_SECTIONS.forEach((section) => {
    if (!Array.isArray(section.items)) return
    section.items = section.items.filter((item) => !allExcludedIds.has(item?.id))
  })
}

export const VERIFIED_HELP_CARD_IDS = new Set([
  ...SYSTEM_HELP_CARDS.map((item) => item.id),
  ...FOUNDATION_HELP_CARDS.map((item) => item.id),
  ...STUDENT_DATA_HELP_CARDS.map((item) => item.id),
  ...MOBILE_CLEAN_HELP_CARDS.map((item) => item.id),
  ...ACADEMIC_AFFAIRS_CLEAN_HELP_CARDS.map((item) => item.id),
  ...ACADEMIC_AFFAIRS_CORE_FLOW_HELP_CARDS.map((item) => item.id),
  ...INTERNSHIP_CLEAN_HELP_CARDS.map((item) => item.id),
  ...INTERNSHIP_CORE_FLOW_HELP_CARDS.map((item) => item.id),
  ...GRADUATION_CLEAN_HELP_CARDS.map((item) => item.id),
  ...GRADUATION_CORE_FLOW_HELP_CARDS.map((item) => item.id),
  ...STUDENT_AFFAIRS_CLEAN_HELP_CARDS.map((item) => item.id),
  ...STUDENT_AFFAIRS_CORE_FLOW_HELP_CARDS.map((item) => item.id),
  ...HIGH_FREQUENCY_TROUBLESHOOTING_HELP_CARDS.map((item) => item.id),
  ...HIGH_FREQUENCY_TROUBLESHOOTING_V305B_CARDS.map((item) => item.id),
  ...Object.keys(VERIFIED_HELP_OVERRIDES)
])

export const VERIFIED_HELP_FLOW_IDS = new Set(Object.keys(VERIFIED_HELP_FLOW_OVERRIDES))
export const VERIFIED_HELP_DOC_IDS = new Set()
export const QUARANTINED_UNVERIFIED_HELP_IDS = new Set()

function quarantineUnverifiedKnowledge() {
  removeUnverifiedInPlace(BASE_HELP_CARDS, VERIFIED_HELP_CARD_IDS, QUARANTINED_UNVERIFIED_HELP_IDS)
  removeUnverifiedInPlace(HELP_DOCS, VERIFIED_HELP_DOC_IDS, QUARANTINED_UNVERIFIED_HELP_IDS)
  removeUnverifiedInPlace(HELP_FLOWS, VERIFIED_HELP_FLOW_IDS, QUARANTINED_UNVERIFIED_HELP_IDS)
  const publishedIds = new Set([...VERIFIED_HELP_CARD_IDS, ...VERIFIED_HELP_DOC_IDS, ...VERIFIED_HELP_FLOW_IDS])
  BASE_HELP_SECTIONS.forEach((section) => {
    if (!Array.isArray(section.items)) return
    section.items = section.items.filter((item) => publishedIds.has(item?.id))
  })
}

registerCards(SYSTEM_HELP_CARDS)
registerCards(FOUNDATION_HELP_CARDS)
registerCards(STUDENT_DATA_HELP_CARDS)
applyVerifiedOverrides()
replaceOrRegisterCards(ACADEMIC_AFFAIRS_CLEAN_HELP_CARDS)
replaceOrRegisterCards(ACADEMIC_AFFAIRS_CORE_FLOW_HELP_CARDS)
replaceOrRegisterCards(INTERNSHIP_CLEAN_HELP_CARDS)
replaceOrRegisterCards(INTERNSHIP_CORE_FLOW_HELP_CARDS)
replaceOrRegisterCards(GRADUATION_CLEAN_HELP_CARDS)
replaceOrRegisterCards(GRADUATION_CORE_FLOW_HELP_CARDS)
replaceOrRegisterCards(STUDENT_AFFAIRS_CLEAN_HELP_CARDS)
replaceOrRegisterCards(STUDENT_AFFAIRS_CORE_FLOW_HELP_CARDS)
replaceOrRegisterCards(HIGH_FREQUENCY_TROUBLESHOOTING_HELP_CARDS)
replaceOrRegisterCards(HIGH_FREQUENCY_TROUBLESHOOTING_V305B_CARDS)
replaceOrRegisterCards(MOBILE_CLEAN_HELP_CARDS)
quarantineConfirmedStaleHelp()
quarantineUnverifiedKnowledge()

if (!BASE_HELP_SECTIONS.some((section) => section.key === 'system-cards')) BASE_HELP_SECTIONS.unshift({ key: 'system-cards', label: '系统管理 · 任务卡', items: SYSTEM_HELP_CARDS })
if (!BASE_HELP_SECTIONS.some((section) => section.key === 'foundation-cards')) BASE_HELP_SECTIONS.unshift({ key: 'foundation-cards', label: '开局与通用基础 · 任务卡', items: FOUNDATION_HELP_CARDS })
if (!BASE_HELP_SECTIONS.some((section) => section.key === 'student-data-cards')) BASE_HELP_SECTIONS.unshift({ key: 'student-data-cards', label: '学生主档与数据 · 任务卡', items: STUDENT_DATA_HELP_CARDS })
if (!BASE_HELP_SECTIONS.some((section) => section.key === 'academic-v3-core-cards')) BASE_HELP_SECTIONS.unshift({ key: 'academic-v3-core-cards', label: '教务中心 · V3核心事实链', items: ACADEMIC_AFFAIRS_CORE_FLOW_HELP_CARDS })
if (!BASE_HELP_SECTIONS.some((section) => section.key === 'academic-clean-cards')) BASE_HELP_SECTIONS.unshift({ key: 'academic-clean-cards', label: '教务中心 · 已核验任务', items: ACADEMIC_AFFAIRS_CLEAN_HELP_CARDS })
if (!BASE_HELP_SECTIONS.some((section) => section.key === 'internship-v3-core-cards')) BASE_HELP_SECTIONS.unshift({ key: 'internship-v3-core-cards', label: '岗位实习 · V3完整办理链', items: INTERNSHIP_CORE_FLOW_HELP_CARDS })
if (!BASE_HELP_SECTIONS.some((section) => section.key === 'internship-clean-cards')) BASE_HELP_SECTIONS.unshift({ key: 'internship-clean-cards', label: '岗位实习 · 已核验任务', items: INTERNSHIP_CLEAN_HELP_CARDS })
if (!BASE_HELP_SECTIONS.some((section) => section.key === 'graduation-v3-core-cards')) BASE_HELP_SECTIONS.unshift({ key: 'graduation-v3-core-cards', label: '毕业设计 · V3完整办理链', items: GRADUATION_CORE_FLOW_HELP_CARDS })
if (!BASE_HELP_SECTIONS.some((section) => section.key === 'graduation-clean-cards')) BASE_HELP_SECTIONS.unshift({ key: 'graduation-clean-cards', label: '毕业设计 · 已核验任务', items: GRADUATION_CLEAN_HELP_CARDS })
if (!BASE_HELP_SECTIONS.some((section) => section.key === 'student-affairs-v3-core-cards')) BASE_HELP_SECTIONS.unshift({ key: 'student-affairs-v3-core-cards', label: '学工中心 · V3四条高频办理线', items: STUDENT_AFFAIRS_CORE_FLOW_HELP_CARDS })
if (!BASE_HELP_SECTIONS.some((section) => section.key === 'student-affairs-clean-cards')) BASE_HELP_SECTIONS.unshift({ key: 'student-affairs-clean-cards', label: '学工中心 · 已核验任务', items: STUDENT_AFFAIRS_CLEAN_HELP_CARDS })
if (!BASE_HELP_SECTIONS.some((section) => section.key === 'troubleshooting-v3-cards')) BASE_HELP_SECTIONS.unshift({ key: 'troubleshooting-v3-cards', label: '高频故障库 · V3自助排障', items: [...HIGH_FREQUENCY_TROUBLESHOOTING_HELP_CARDS, ...HIGH_FREQUENCY_TROUBLESHOOTING_V305B_CARDS] })
if (!BASE_HELP_SECTIONS.some((section) => section.key === 'mobile-cards')) BASE_HELP_SECTIONS.unshift({ key: 'mobile-cards', label: '微信小程序 · 已核验高频任务', items: MOBILE_CLEAN_HELP_CARDS })

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

export function searchHelp(query) {
  const q = String(query || '').trim().toLowerCase()
  if (!q) return []
  const docs = HELP_DOCS.filter((item) => hitHelp(item, q)).map((item) => ({ id: item.id, kind: '功能帮助', title: item.title }))
  const flows = HELP_FLOWS.filter((item) => hitHelp(item, q)).map((item) => ({ id: item.id, kind: '业务流程图', title: item.title }))
  const cards = HELP_CARDS.filter((item) => hitHelp(item, q)).map((item) => ({
    id: item.id,
    kind: '帮助任务卡',
    title: item.title,
    sub: [item.module, (item.roles || []).join('、'), item.entry].filter(Boolean).join(' · ')
  }))
  return [...cards, ...flows, ...docs]
}

function splitRoute(route) {
  const [path, qs = ''] = String(route || '').split('?')
  const panel = new URLSearchParams(qs).get('panel') || ''
  return { path, panel }
}

export function findHelpForRoute(fullPath) {
  const current = splitRoute(fullPath)
  if (!current.path) return null
  const cards = HELP_CARDS.filter((card) => card.route).map((card) => ({ card, route: splitRoute(card.route) }))
  const exact = cards.find((item) => item.route.path === current.path && item.route.panel === current.panel)
  const samePath = exact || cards.find((item) => item.route.path === current.path)
  const prefix = samePath || cards.filter((item) => item.route.path && current.path.startsWith(item.route.path + '/')).sort((a, b) => b.route.path.length - a.route.path.length)[0]
  return prefix ? { id: prefix.card.id, title: prefix.card.title } : null
}

export function getHelpById(id) {
  const card = HELP_CARDS.find((item) => item.id === id)
  if (card) return { type: 'card', item: card }
  const doc = HELP_DOCS.find((item) => item.id === id)
  if (doc) return { type: 'doc', item: doc }
  const flow = HELP_FLOWS.find((item) => item.id === id)
  if (flow) return { type: 'flow', item: flow }
  return null
}
