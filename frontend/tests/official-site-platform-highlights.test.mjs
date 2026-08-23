import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'

const here = path.dirname(fileURLToPath(import.meta.url))
const root = path.resolve(here, '..')
const pageSource = fs.readFileSync(path.join(root, 'src/views/official-site/OfficialPlatformCapabilityView.vue'), 'utf8')
const styleSource = fs.readFileSync(path.join(root, 'src/styles/official-platform-highlights.css'), 'utf8')

test('platform page promotes current foundation capabilities without reducing the product to module count', () => {
  for (const marker of [
    '学生 360° 成长工作台',
    '统一安全文件与版本中心',
    '跨业务统一审批中心',
    '业务待办一键直达',
    '可信 Excel 数据交换中心',
    '内置业务知识与操作帮助中心',
    '统一后台任务与批处理中心',
    '多租户、权限、数据范围与审计底座'
  ]) {
    assert.ok(pageSource.includes(marker), `missing current foundation capability: ${marker}`)
  }
})

test('platform highlights keep live and evolving states explicit', () => {
  for (const marker of [
    '六项核心能力',
    '四端在线文档预览与批阅',
    '材料合规智能检查',
    '可信电子证据链',
    '全局业务搜索',
    '协同工作台',
    "status: '当前具备'",
    "status: '持续演进'",
    '具体交付范围以项目合同、正式版本与上线验收为准'
  ]) {
    assert.ok(pageSource.includes(marker), `missing truthful highlight marker: ${marker}`)
  }
  assert.ok(!pageSource.includes('已全面支持'))
  assert.ok(!pageSource.includes('全部已上线'))
})

test('platform evolution stays customer-facing without exposing internal roadmap framing', () => {
  assert.ok(pageSource.includes('当前能力与演进方向清晰区分'))
  assert.ok(pageSource.includes('“持续演进”表示产品方向'))
  assert.ok(!pageSource.includes('ABCD · 下一阶段平台演进'))
  assert.ok(!pageSource.includes('当前产品代码'))
  assert.ok(!pageSource.includes('隔离浏览器环境'))
})

test('platform highlight page ships responsive dedicated styling', () => {
  for (const marker of [
    '.yk-highlight-hero',
    '.yk-highlight-foundation-grid',
    '.yk-highlight-feature-grid',
    '.yk-highlight-proof-grid',
    '.yk-highlight-evolution-grid',
    '@media (max-width: 720px)'
  ]) {
    assert.ok(styleSource.includes(marker), `missing platform highlight style: ${marker}`)
  }
})
