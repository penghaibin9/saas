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

test('毕业设计官网页包含全过程质量管理销售主线', () => {
  for (const text of [
    '从选题到归档，一套系统管住毕业设计全过程',
    '退回、修改与重交留痕',
    '指导、中期与整改闭环',
    '成果文件版本管理',
    '评阅答辩角色分离',
    '材料齐套与冻结归档',
    '过程管得住',
    '材料拿得出'
  ]) assert.match(products, new RegExp(text))

  assert.match(stories, /开题版本与审核意见/)
  assert.match(stories, /中期检查与整改复核/)
  assert.match(stories, /综合成绩与申诉历史/)
  assert.match(view, /marketing\.concernTitle/)
  assert.match(view, /marketing\.workflowSummary/)
})

test('毕业设计增强内容保留质量建设边界说明', () => {
  assert.match(stories, /不能代替学校的教学质量建设/)
  assert.match(stories, /减少检查前临时补过程、找材料的压力/)
})
