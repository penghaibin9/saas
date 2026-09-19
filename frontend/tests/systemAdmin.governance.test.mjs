/**
 * 系统管理工作区与正式入口权限回归。
 */
import assert from 'node:assert/strict'
import test from 'node:test'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const root = path.resolve(__dirname, '..')
const toUrl = (p) => pathToFileURL(p).href

test('restricted viewers can find the same read workspaces accepted by the server', async () => {
  const { getVisibleNavPlan } = await import(toUrl(path.join(root, 'src/config/navPlan.js')))
  const visiblePaths = (permission) => {
    const plan = getVisibleNavPlan({ permissionPatterns: [permission], ctxKey: `restricted-${permission}` })
    return plan.flatMap(group => group.children || []).flatMap(group => group.children || []).map(item => item.path)
  }
  assert.ok(visiblePaths('systemAdmin.role.view').includes('/admin/system/iam?surface=templates'))
  assert.ok(visiblePaths('systemAdmin.role.view').includes('/admin/system/iam?surface=permissions'))
  assert.ok(visiblePaths('systemAdmin.audit.view').includes('/admin/system/logs?tab=operation'))
  assert.ok(visiblePaths('systemAdmin.audit.view').includes('/admin/system/logs?tab=login'))
  assert.ok(visiblePaths('systemAdmin.config.view').includes('/admin/system/config?tab=brand'))
  assert.ok(!visiblePaths('academicAffairs.grade.view').includes('/admin/system/iam?surface=permissions'))
})

test('all recorded legacy capabilities retain their exact deep links after regrouping', async () => {
  const { SYSTEM_MANAGEMENT_ITEMS } = await import(toUrl(path.join(root, 'src/modules/system/systemManagementCatalog.js')))
  const record = fs.readFileSync(path.join(root, '../docs/03-业务模块设计/系统管理中心/04-学校级系统管理-8组26项能力目录与实施规范.md'), 'utf8')
  const entries = [...record.matchAll(/\| `(sys-[^`]+)` \| [^|]+ \| `([^`]+)` \|/g)]
  assert.equal(entries.length, 52)
  for (const [, key, route] of entries) assert.equal(SYSTEM_MANAGEMENT_ITEMS.find(item => item.key === key)?.path, route, key)
})

test('system management has 8 workspaces and retains operational dictionary and implementation entries', async () => {
  const mod = await import(toUrl(path.join(root, 'src/modules/system/systemManagementCatalog.js')))
  assert.equal(mod.SYSTEM_MANAGEMENT_CATALOG.length, 8)
  const labels = mod.SYSTEM_MANAGEMENT_CATALOG.map((g) => g.label)
  for (const need of [
    '系统概览', '身份与账号', '组织主数据',
    '角色与权限', '学校配置', '流程配置',
    '安全与审计', '接口与同步',
  ]) {
    assert.ok(labels.includes(need), `missing ${need}`)
  }
  const itemKeys = mod.SYSTEM_MANAGEMENT_ITEMS.map((item) => item.key)
  assert.equal(itemKeys.length, 52)
  assert.equal(new Set(itemKeys).size, 52)
  assert.ok(itemKeys.includes('sys-dictionaries-fields'))
  const overview = mod.SYSTEM_MANAGEMENT_CATALOG.find(group => group.key === 'sys-overview')
  assert.equal(overview.items[0].path, '/admin/system/overview')
  assert.ok(overview.items.some(item => item.key === 'sys-implementation-wizard'))
  assert.ok(overview.items.some(item => item.key === 'sys-implementation-acceptance'))
  for (const nonOperational of [
    'sys-numbering-rules',
    'sys-process-rules',
    'sys-process-monitor',
  ]) {
    assert.ok(!itemKeys.includes(nonOperational), `non-operational menu must be hidden: ${nonOperational}`)
  }
})

test('permissionGate covers employment/system/orientation', async () => {
  const mod = await import(toUrl(path.join(root, 'src/security/permissionGate.js')))
  for (const code of ['EMPLOYMENT', 'SYSTEM', 'ORIENTATION', 'WORKBENCH']) {
    assert.ok(mod.GUARDED_MODULES.has(code), `missing guarded ${code}`)
  }
})

test('system management formal pages never fall back to mock data or fake brand reset', () => {
  const api = fs.readFileSync(path.join(root, 'src/modules/system/api/system.api.js'), 'utf8')
  const configView = fs.readFileSync(path.join(root, 'src/modules/system/views/SystemConfigView.vue'), 'utf8')
  const importDialog = fs.readFileSync(path.join(root, 'src/modules/system/components/ImportDialog.vue'), 'utf8')

  assert.doesNotMatch(api, /from ['"]@\/mocks\/system/)
  assert.doesNotMatch(api, /withFallback\(/)
  assert.match(api, /request\('\/system\/overview-board'/)
  assert.match(api, /request\('\/system\/brand\/reset'/)
  assert.match(configView, /systemApi\.resetBrandConfig/)
  assert.doesNotMatch(configView, /已提交恢复默认申请/)
  assert.doesNotMatch(importDialog, /演示环境|模拟上传/)
})

test('staff and student accounts are separate formal routes and server queries', () => {
  const routes = fs.readFileSync(path.join(root, 'src/modules/system/system.routes.js'), 'utf8')
  const catalog = fs.readFileSync(path.join(root, 'src/modules/system/systemManagementCatalog.js'), 'utf8')
  const api = fs.readFileSync(path.join(root, 'src/modules/system/api/system.api.js'), 'utf8')
  const view = fs.readFileSync(path.join(root, 'src/modules/system/views/SystemUserListView.vue'), 'utf8')

  assert.match(routes, /path: 'accounts\/staff'/)
  assert.match(routes, /path: 'accounts\/students'/)
  assert.match(routes, /path: 'users'[\s\S]*redirect: '\/admin\/system\/accounts\/staff'/)
  assert.match(catalog, /label: '教职工账号'/)
  assert.match(catalog, /label: '学生账号'/)
  assert.doesNotMatch(catalog, /label: '师生账号'/)
  assert.match(api, /account_type: params\.accountType/)
  assert.match(api, /account_type.*accountType/s)
  assert.match(view, /v-if="!isStudent"[\s\S]*批量分配角色/)
  assert.match(view, /学生账号固定绑定 STUDENT/)
  assert.match(view, /按班级/)
  assert.match(view, /按年级/)
  assert.match(view, /按学院/)
  assert.match(view, /全校学生账号/)
  assert.match(api, /confirmSchoolScope/)
})
