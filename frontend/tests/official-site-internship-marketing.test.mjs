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
