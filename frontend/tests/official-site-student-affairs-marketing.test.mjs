import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const read = (relativePath) => fs.readFileSync(path.join(root, relativePath), 'utf8')

const products = read('src/config/officialProducts.js')
const stories = read('src/config/officialWebsiteStory.js')

test('学工中心官网页包含学生工作数字中枢销售主线', () => {
  for (const text of [
    '把全校学生工作，真正管到一个平台里',
    '辅导员统一工作台',
    '一人一档与学生 360',
    '风险发现与处置闭环',
    '困难认定与奖助帮扶',
    '宿舍全过程管理',
    '谈心家校与敏感边界',
    '活动与第二课堂成长'
  ]) assert.match(products, new RegExp(text))

  assert.match(products, /学生的事，办得更方便/)
  assert.match(products, /学生的成长，留得下来/)
  assert.match(stories, /风险分级与处置历史/)
  assert.match(stories, /统计台账与学生成长档案/)
})

test('学工宣传内容保留学生理解与敏感数据边界', () => {
  assert.match(stories, /不以单一标签替代对学生真实情况的理解/)
  assert.match(stories, /角色权限、数据范围和敏感访问边界/)
  assert.match(stories, /不声称自动心理诊断/)
})
