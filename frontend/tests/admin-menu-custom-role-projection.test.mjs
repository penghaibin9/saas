import assert from 'node:assert/strict'
import { Buffer } from 'node:buffer'
import fs from 'node:fs'
import test from 'node:test'
import { fileURLToPath, pathToFileURL } from 'node:url'

const adminMenuPath = new URL('../src/config/adminMenu.js', import.meta.url)
const navPlanUrl = pathToFileURL(fileURLToPath(new URL('../src/config/navPlan.js', import.meta.url))).href
const moduleEntitlementUrl = pathToFileURL(
  fileURLToPath(new URL('../src/security/moduleEntitlement.js', import.meta.url))
).href

async function loadAdminMenu() {
  const source = fs.readFileSync(adminMenuPath, 'utf8')
    .replace("from '@/config/navPlan'", `from '${navPlanUrl}'`)
    .replace("from '@/security/moduleEntitlement'", `from '${moduleEntitlementUrl}'`)
  return import(`data:text/javascript;base64,${Buffer.from(source).toString('base64')}`)
}

function customRoleContext(moduleEntitlements) {
  return {
    activeContextId: 'role:15',
    currentRole: { roleCode: 'E2E_CUSTOM_MENU', contextId: 'role:15' },
    permissionPatterns: ['internship.recruitment.view'],
    permissionVersion: 'test-custom-role-v1',
    moduleEntitlements,
    moduleAccessHealthy: true
  }
}

test('custom role can enter a purchased module through any assigned descendant permission', async () => {
  const { getVisibleAdminMenu } = await loadAdminMenu()
  const menu = getVisibleAdminMenu(customRoleContext(['internship']))

  const internship = menu.find((group) => group.key === 'internship')
  assert.ok(internship, '岗位实习中心 should be visible for purchased module + assigned descendant permission')
  const enterprisePosition = internship.children.find((item) => item.key === 'in-enterprise-position')
  assert.equal(enterprisePosition?.path, '/admin/internship/recruitment-campaigns')
  assert.equal(enterprisePosition?.permissionKey, 'internship.recruitment.view')
})

test('custom role descendant permission cannot bypass an explicit unpurchased module set', async () => {
  const { getVisibleAdminMenu } = await loadAdminMenu()
  const menu = getVisibleAdminMenu(customRoleContext([]))
  assert.equal(menu.some((group) => group.key === 'internship'), false)
})
