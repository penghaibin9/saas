/**
 * 路由索引与能力注册表 routeExists 专项。
 */
import assert from 'node:assert/strict'
import test from 'node:test'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { buildRouteIndex, matchRouteExists } from '../../scripts/check/build-route-index.mjs'

const __dirname = path.dirname(fileURLToPath(import.meta.url))

function withRegexes(index) {
  // 复用生产脚本的匹配语义：直接走 buildRouteIndex 结果，或补齐 patternRegexes
  if (index.patternRegexes?.length) return index
  // 简化：委托真实 build 中的 patternToRegex 不可导出时，用 match 测真实索引即可
  return index
}

test('static route exact match', () => {
  const index = buildRouteIndex()
  const hit = matchRouteExists(index, '/admin/workflow/processes')
  assert.equal(hit.exists, true)
  assert.equal(hit.matchType, 'exact')
})

test('dynamic detail / optional param routes', () => {
  const index = buildRouteIndex()
  const base = matchRouteExists(index, '/admin/academic-affairs/schedule/class')
  assert.equal(base.exists, true)
  const detail = matchRouteExists(index, '/admin/academic-affairs/schedule/class/99')
  assert.equal(detail.exists, true)
  assert.equal(detail.matchType, 'param')
})

test('missing route is not exists', () => {
  const index = buildRouteIndex()
  const miss = matchRouteExists(index, '/admin/no-such-governance-page-xyz')
  assert.equal(miss.exists, false)
  assert.equal(miss.matchType, 'missing')
})

test('redirect and alias recorded when present in route files', () => {
  const index = buildRouteIndex()
  assert.ok(Array.isArray(index.redirects))
  assert.ok(Array.isArray(index.aliases))
  // 若索引内有 redirect/alias，matchType 应区分
  for (const r of index.redirects.slice(0, 5)) {
    if (r.from) {
      const m = matchRouteExists(index, r.from)
      assert.equal(m.exists, true)
      assert.ok(['redirect', 'exact', 'alias'].includes(m.matchType))
    }
  }
  for (const a of index.aliases.slice(0, 5)) {
    if (a.from) {
      const m = matchRouteExists(index, a.from)
      assert.equal(m.exists, true)
      assert.ok(['alias', 'exact', 'redirect'].includes(m.matchType))
    }
  }
})

test('hidden/detail/action nodes still get permissionPolicy in registry', async () => {
  const fs = await import('node:fs')
  const root = path.resolve(__dirname, '../..')
  const regPath = path.join(root, 'shared/generated/capability-registry.json')
  assert.ok(fs.existsSync(regPath), 'registry must be generated')
  const reg = JSON.parse(fs.readFileSync(regPath, 'utf8'))
  assert.equal(reg.routeMatchStats.missing, 0)
  assert.equal(reg.permissionPolicyStats.UNRESOLVED, 0)
  for (const c of reg.capabilities) {
    assert.ok(c.permissionPolicy, `missing policy ${c.capabilityKey}`)
    if (['DETAIL', 'ACTION', 'FILTER_VIEW'].includes(c.entryType)) {
      assert.ok(
        ['INHERIT_WORKSPACE', 'EXEMPT', 'EXPLICIT', 'INHERIT_FIRST_LEAF'].includes(c.permissionPolicy),
        `bad policy for ${c.capabilityKey}: ${c.permissionPolicy}`,
      )
    }
  }
})

test('buildRouteIndex non-empty', () => {
  const index = withRegexes(buildRouteIndex())
  assert.ok(index.exact.size > 20)
})
