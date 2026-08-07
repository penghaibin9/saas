import { ACADEMIC_AFFAIRS_CLEAN_HELP_CARDS } from './academicAffairsCleanHelpCards.js'
import { ACADEMIC_AFFAIRS_CORE_FLOW_HELP_CARDS } from './academicAffairsCoreFlowHelpCards.js'
import { GRADUATION_CLEAN_HELP_CARDS } from './graduationCleanHelpCards.js'
import { GRADUATION_CORE_FLOW_HELP_CARDS } from './graduationCoreFlowHelpCards.js'
import { INTERNSHIP_CLEAN_HELP_CARDS } from './internshipCleanHelpCards.js'
import { INTERNSHIP_CORE_FLOW_HELP_CARDS } from './internshipCoreFlowHelpCards.js'
import { STUDENT_AFFAIRS_CLEAN_HELP_CARDS } from './studentAffairsCleanHelpCards.js'
import { STUDENT_AFFAIRS_CORE_FLOW_HELP_CARDS } from './studentAffairsCoreFlowHelpCards.js'
import {
  ACADEMIC_ROLE_GUIDANCE,
  HELP_AUTHORIZATION_PRINCIPLE
} from './helpRoleGuidance.js'
import { GRADUATION_ROLE_GUIDANCE } from './graduationRoleGuidance.js'
import { GRADUATION_V3_SELF_SERVICE_GUIDANCE } from './graduationV3SelfServiceGuidance.js'
import { INTERNSHIP_ROLE_GUIDANCE } from './internshipRoleGuidance.js'
import { INTERNSHIP_V3_SELF_SERVICE_GUIDANCE } from './internshipV3SelfServiceGuidance.js'
import { STUDENT_AFFAIRS_ROLE_GUIDANCE } from './studentAffairsRoleGuidance.js'

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

function attachSelfService(card, guidanceMap) {
  const patch = guidanceMap[card.id]
  if (!patch) return card
  if (patch.nextSteps?.length) card.nextSteps = patch.nextSteps
  if (patch.contactAdminWhen?.length) card.contactAdminWhen = patch.contactAdminWhen
  return card
}

export function applyHelpRoleGuidanceRuntime() {
  ;[
    ...ACADEMIC_AFFAIRS_CLEAN_HELP_CARDS,
    ...ACADEMIC_AFFAIRS_CORE_FLOW_HELP_CARDS
  ].forEach((card) => attachGuidance(card, ACADEMIC_ROLE_GUIDANCE))

  ;[
    ...INTERNSHIP_CLEAN_HELP_CARDS,
    ...INTERNSHIP_CORE_FLOW_HELP_CARDS
  ].forEach((card) => {
    attachGuidance(card, INTERNSHIP_ROLE_GUIDANCE)
    attachSelfService(card, INTERNSHIP_V3_SELF_SERVICE_GUIDANCE)
  })

  ;[
    ...GRADUATION_CLEAN_HELP_CARDS,
    ...GRADUATION_CORE_FLOW_HELP_CARDS
  ].forEach((card) => {
    attachGuidance(card, GRADUATION_ROLE_GUIDANCE)
    attachSelfService(card, GRADUATION_V3_SELF_SERVICE_GUIDANCE)
  })

  ;[
    ...STUDENT_AFFAIRS_CLEAN_HELP_CARDS,
    ...STUDENT_AFFAIRS_CORE_FLOW_HELP_CARDS
  ].forEach((card) => attachGuidance(card, STUDENT_AFFAIRS_ROLE_GUIDANCE))
}

applyHelpRoleGuidanceRuntime()
