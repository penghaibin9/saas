import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const read = (relativePath) => fs.readFileSync(path.join(root, relativePath), 'utf8')

const products = read('src/config/officialProducts.js')
const stories = read('src/config/officialWebsiteStory.js')
const view = read('src/views/official-site/OfficialProductView.vue')
const styles = read('src/styles/official-site.css')
const assetExists = (filename) => fs.existsSync(path.join(root, 'public', 'official-site', filename))

test('岗位实习官网页包含完整销售主线与学校价值表达', () => {
  for (const text of [
    '学生出去实习，学校依然管得住',
    '学生去向统一掌握',
    '上岗条件逐项核验',
    '异常风险闭环处置',
    '材料归档',
    '学生去向看得见',
    '管理结果看得见'
  ]) assert.match(products, new RegExp(text))

  assert.match(stories, /学生实习档案/)
  assert.match(stories, /异常与风险处置记录/)
  assert.match(products, /面对几千名校外实习学生，学校需要心里有底/)
  assert.match(products, /检查来了，不再临时找材料/)
  assert.match(styles, /\.yk-product-concern-grid/)
  assert.match(styles, /\.yk-product-visibility-grid/)
})

test('岗位实习增强区块由产品数据控制，不影响其他公开产品页', () => {
  assert.match(view, /v-if="concerns\.length"/)
  assert.match(view, /v-if="visibility\.length"/)
  assert.match(view, /marketing\(\)/)
})

test('岗位实习官网采用真实运行界面并为每张图片提供业务说明', () => {
  for (const filename of [
    'internship-batch-list.png',
    'internship-participant-scope.png',
    'internship-batch-detail.png'
  ]) assert.equal(assetExists(filename), true)

  assert.match(products, /实习批次设置/)
  assert.match(products, /集中展示批次名称、学年学期、实习起止、计划与实际人数/)
  assert.match(products, /参与学生范围配置/)
  assert.match(products, /为什么进入该批次有据可查/)
  assert.match(products, /批次详情与状态留痕/)
  assert.match(products, /阶段时间线和操作留痕/)
})
