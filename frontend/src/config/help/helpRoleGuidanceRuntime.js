import { ACADEMIC_AFFAIRS_CLEAN_HELP_CARDS } from './academicAffairsCleanHelpCards.js'
import { ACADEMIC_AFFAIRS_CORE_FLOW_HELP_CARDS } from './academicAffairsCoreFlowHelpCards.js'
import { INTERNSHIP_CLEAN_HELP_CARDS } from './internshipCleanHelpCards.js'
import {
  ACADEMIC_ROLE_GUIDANCE,
  HELP_AUTHORIZATION_PRINCIPLE
} from './helpRoleGuidance.js'
import { INTERNSHIP_ROLE_GUIDANCE } from './internshipRoleGuidance.js'

function stringifyRoleGuidance(item) {
  const parts = [
    `${item.role}${item.roleCode ? `（${item.roleCode}）` : ''}`,
    item.permission ? `权限模板：${item.permission}` : '',
    item.scope ? `数据范围：${item.scope}` : '',
    item.relation ? `业务关系：${item.relation}` : '',
    item.canDo ? `职责边界：${item.canDo}` : ''
  ].filter(Boolean)
  return parts.join('；')
}

function attachGuidance(card, guidanceMap) {
  const guidance = guidanceMap[card.id]
  if (!guidance?.length) return card

  card.authorizationPrinciple = HELP_AUTHORIZATION_PRINCIPLE
  card.roleGuidance = guidance

  const existingSections = Array.isArray(card.sections) ? card.sections : []
  const withoutRoleSection = existingSections.filter((section) => section?.key !== 'authorization-role-scope')
  card.sections = [
    {
      key: 'authorization-role-scope',
      title: '谁能办、能看哪些数据、还要满足什么关系',
      body: HELP_AUTHORIZATION_PRINCIPLE,
      items: guidance.map(stringifyRoleGuidance)
    },
    ...withoutRoleSection
  ]
  return card
}

export function applyHelpRoleGuidanceRuntime() {
  ;[
    ...ACADEMIC_AFFAIRS_CLEAN_HELP_CARDS,
    ...ACADEMIC_AFFAIRS_CORE_FLOW_HELP_CARDS
  ].forEach((card) => attachGuidance(card, ACADEMIC_ROLE_GUIDANCE))

  INTERNSHIP_CLEAN_HELP_CARDS.forEach((card) => attachGuidance(card, INTERNSHIP_ROLE_GUIDANCE))
}

applyHelpRoleGuidanceRuntime()
