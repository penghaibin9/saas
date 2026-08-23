import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'
import { OFFICIAL_SALES_PAGE_MAP, OFFICIAL_SEO_ROUTES } from '../src/config/officialSalesPages.js'

const here = path.dirname(fileURLToPath(import.meta.url))
const root = path.resolve(here, '..')
const mainSource = fs.readFileSync(path.join(root, 'src/main.js'), 'utf8')
const pageSource = fs.readFileSync(path.join(root, 'src/views/official-site/OfficialPlatformCapabilityView.vue'), 'utf8')
const styleSource = fs.readFileSync(path.join(root, 'src/styles/official-platform-highlights.css'), 'utf8')

test('platform route keeps official sales SEO truth but renders the dedicated capability narrative', () => {
  assert.ok(OFFICIAL_SALES_PAGE_MAP['/platform'])
  assert.ok(OFFICIAL_SEO_ROUTES.some((item) => item.path === '/platform'))
  assert.ok(mainSource.includes("page.path === '/platform'"))
  assert.ok(mainSource.includes('OfficialPlatformCapabilityView.vue'))
  assert.ok(pageSource.includes("syncOfficialSeo('/platform')"))
})

test('platform capability page preserves truthful build-status language', () => {
  for (const marker of [
    '六项核心能力 · 当前能力与演进方向清晰区分',
    '“当前具备”表示可进入现有产品工作区',
    '“持续演进”表示产品方向',
    '具体交付范围以项目合同、正式版本与上线验收为准'
  ]) {
    assert.ok(pageSource.includes(marker), `missing truthfulness marker: ${marker}`)
  }
  assert.ok(!pageSource.includes('全部已支持'))
  assert.ok(!pageSource.includes('全部已上线'))
})

test('platform capability page promotes a compact current foundation and six flagship capabilities', () => {
  for (const marker of [
    '学生 360° 成长工作台',
    '统一安全文件与版本中心',
    '跨业务统一审批中心',
    '业务待办一键直达',
    '可信 Excel 数据交换中心',
    '内置业务知识与操作帮助中心',
    '统一后台任务与批处理中心',
    '四端在线文档预览与批阅',
    '材料合规智能检查',
    '可信电子证据链',
    '全局业务搜索',
    '协同工作台'
  ]) {
    assert.ok(pageSource.includes(marker), `missing platform capability copy: ${marker}`)
  }
})

test('platform capability page does not expose internal roadmap framing to customers', () => {
  assert.ok(!pageSource.includes('ABCD · 下一阶段平台演进'))
  assert.ok(!pageSource.includes('当前产品代码'))
  assert.ok(!pageSource.includes('隔离浏览器环境'))
})

test('platform capability page ships responsive dedicated styling', () => {
  for (const marker of [
    '.yk-highlight-hero',
    '.yk-highlight-foundation-grid',
    '.yk-highlight-feature-grid',
    '.yk-highlight-proof-grid',
    '@media (max-width: 720px)'
  ]) {
    assert.ok(styleSource.includes(marker), `missing platform capability style: ${marker}`)
  }
})
