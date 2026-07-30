/**
 * 系统管理 9 工作区与权限门覆盖冒烟。
 */
import assert from 'node:assert/strict'
import test from 'node:test'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const root = path.resolve(__dirname, '..')
const toUrl = (p) => pathToFileURL(p).href

test('system management catalog has 9 workspaces', async () => {
  const mod = await import(toUrl(path.join(root, 'src/modules/system/systemManagementCatalog.js')))
  assert.equal(mod.SYSTEM_MANAGEMENT_CATALOG.length, 9)
  const labels = mod.SYSTEM_MANAGEMENT_CATALOG.map((g) => g.label)
  for (const need of [
    '系统总览', '实施与验收', '身份与账号', '组织与任职',
    '角色权限与数据范围', '模块与学校配置', '流程配置与运行',
    '安全与审计', '接口同步与数据迁移',
  ]) {
    assert.ok(labels.includes(need), `missing ${need}`)
  }
  const itemKeys = mod.SYSTEM_MANAGEMENT_ITEMS.map((item) => item.key)
  for (const nonOperational of [
    'sys-numbering-rules',
    'sys-dictionaries-fields',
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
