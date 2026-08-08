import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, resolve } from 'node:path'
import { FOUNDATION_HELP_CARDS } from '../help/foundationHelpCards.js'
import { VERIFIED_HELP_OVERRIDES } from '../help/verifiedHelpOverrides.js'

const here = dirname(fileURLToPath(import.meta.url))
const modelSource = readFileSync(resolve(here, '../helpCenterModel.js'), 'utf8')
const runtimeSource = readFileSync(resolve(here, '../helpCenterRuntime.js'), 'utf8')
const viewSource = readFileSync(resolve(here, '../../views/admin/help/AdminHelpView.vue'), 'utf8')
const implementationSource = readFileSync(
  resolve(here, '../../../../backend/app/services/system_implementation_service.py'),
  'utf8'
)

function firstSchoolGuide() {
  const base = FOUNDATION_HELP_CARDS.find((item) => item.id === 'sys-card-first-school-setup')
  assert.ok(base, 'first-school setup card must exist in verified foundation source')
  return { ...base, ...(VERIFIED_HELP_OVERRIDES['sys-card-first-school-setup'] || {}) }
}

test('V3-06 turns first-school setup into an ordered no-training checklist', () => {
  const guide = firstSchoolGuide()
  assert.match(guide.title, /第一次使用|首次/)
  assert.match(guide.summary, /实施项目工作区/)
  assert.ok(guide.steps.length >= 8)
  assert.ok(guide.nextSteps.length >= 3)
  assert.ok(guide.contactAdminWhen.length >= 3)

  const text = [
    ...guide.steps,
    ...guide.successCriteria,
    ...guide.troubleshooting,
    ...guide.nextSteps,
    ...guide.contactAdminWhen
  ].join('\n')
  for (const token of [
    '实施项目',
    '组织',
    '角色',
    '数据范围',
    '教职工账号',
    '学生',
    '登录',
    '学期',
    '上线检查',
    '验收'
  ]) assert.match(text, new RegExp(token))
})

test('V3-06 preserves hard governance boundaries instead of teaching shortcuts', () => {
  const guide = firstSchoolGuide()
  const text = [
    ...(guide.warnings || []),
    ...(guide.troubleshooting || []),
    ...(guide.permissions || []),
    ...(guide.contactAdminWhen || [])
  ].join('\n')
  for (const token of ['预检', '授权', 'BLOCKER', '权限', '数据范围']) {
    assert.match(text, new RegExp(token))
  }
  assert.doesNotMatch(text, /跳过.*BLOCKER|强行.*验收|绕过.*授权/)
})

test('V3-06 is grounded in the real 12-section implementation and acceptance state machine', () => {
  for (const token of [
    'SECTION_DEFINITIONS',
    'school_opening',
    'role_permission',
    'organization',
    'identity_import',
    'business_relation',
    'security_audit',
    'go_live_check',
    'module_business',
    'READY_FOR_ACCEPTANCE',
    '阻断项不能通过人工确认绕过',
    'IMPLEMENTATION_ACCEPTANCE_SUMMARY_FROZEN'
  ]) assert.match(implementationSource, new RegExp(token))
  assert.match(implementationSource, /project\.status = "READY_FOR_ACCEPTANCE" if ready else "VERIFYING"/)
  assert.match(implementationSource, /if project\.status != "READY_FOR_ACCEPTANCE"/)
})

test('V3-06 remains the first verified priority task and is rendered with next-step guidance', () => {
  assert.match(modelSource, /const PRIORITY_HELP_IDS = \[\s*'sys-card-first-school-setup'/)
  assert.match(runtimeSource, /FOUNDATION_HELP_CARDS/)
  assert.match(runtimeSource, /applyVerifiedOverrides\(\)/)
  assert.match(viewSource, /办完以后下一步/)
  assert.match(viewSource, /什么情况才需要找管理员/)
})
