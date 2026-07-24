/**
 * 系统管理 9 工作区与权限门覆盖冒烟。
 */
import assert from 'node:assert/strict'
import test from 'node:test'
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
})

test('permissionGate covers employment/system/orientation', async () => {
  const mod = await import(toUrl(path.join(root, 'src/security/permissionGate.js')))
  for (const code of ['EMPLOYMENT', 'SYSTEM', 'ORIENTATION', 'WORKBENCH']) {
    assert.ok(mod.GUARDED_MODULES.has(code), `missing guarded ${code}`)
  }
})
