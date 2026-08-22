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
const styleSource = fs.readFileSync(path.join(root, 'src/styles/official-platform-capabilities.css'), 'utf8')

test('platform route keeps official sales SEO truth but renders the dedicated capability narrative', () => {
  assert.ok(OFFICIAL_SALES_PAGE_MAP['/platform'])
  assert.ok(OFFICIAL_SEO_ROUTES.some((item) => item.path === '/platform'))
  assert.ok(mainSource.includes("page.path === '/platform'"))
  assert.ok(mainSource.includes('OfficialPlatformCapabilityView.vue'))
})

test('platform capability page preserves truthful build-status language', () => {
  for (const marker of [
    '平台能力持续构建',
    '未完成生产封板的能力统一标注“持续构建”',
    '具体可交付范围以项目合同、正式版本与上线验收为准',
    '能力说明示意 · 不作为未封板功能的已上线界面证明'
  ]) {
    assert.ok(pageSource.includes(marker), `missing truthfulness marker: ${marker}`)
  }
  assert.ok(!pageSource.includes('已全面上线'))
  assert.ok(!pageSource.includes('全部已支持'))
})

test('platform capability page covers ABCD matrix and seven requested public capabilities', () => {
  for (const marker of [
    '可信证据链',
    '规则与表单引擎',
    '文档与事实智能',
    '搜索与协同工作台',
    '可信电子证据链',
    '材料合规智能检查',
    '动态业务表单',
    '文档版本智能比对',
    '学生全生命周期事实流',
    '全局业务搜索',
    '协同待办 2.0'
  ]) {
    assert.ok(pageSource.includes(marker), `missing capability copy: ${marker}`)
  }
})

test('platform capability page ships responsive dedicated styling', () => {
  for (const marker of ['.yk-cap-hero', '.yk-cap-matrix', '.yk-capability-detail', '.yk-day-track', '@media (max-width: 720px)']) {
    assert.ok(styleSource.includes(marker), `missing platform capability style: ${marker}`)
  }
})
