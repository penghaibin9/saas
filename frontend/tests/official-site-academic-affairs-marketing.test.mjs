import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const read = (relativePath) => fs.readFileSync(path.join(root, relativePath), 'utf8')

const products = read('src/config/officialProducts.js')
const stories = read('src/config/officialWebsiteStory.js')
const salesPages = read('src/config/officialSalesPages.js')

test('教务官网页包含从培养方案到毕业审核的全过程销售主线', () => {
  for (const text of [
    '从培养方案到毕业审核，一套系统管住教学运行全过程',
    '培养方案驱动教学运行',
    '教学任务、排课与调课',
    '选课容量与教学班名单',
    '课堂考勤与教学执行',
    '考试考务与特殊业务',
    '可信成绩全生命周期',
    '学籍、预警与毕业审核',
    '教学质量与可信数据'
  ]) assert.match(products, new RegExp(text))

  assert.match(products, /排得开 · 选得稳 · 教得清 · 考得准 · 成绩可信 · 毕业有据/)
  assert.match(products, /毕业资格审核/)
  assert.match(stories, /成绩审核发布与更正历史/)
  assert.match(stories, /学籍异动、学业预警与毕业审核/)
})

test('教务宣传内容保留正式教学事实与数据边界', () => {
  assert.match(stories, /不会把正式成绩当作可以静默覆盖的普通字段/)
  assert.match(stories, /不会虚构通过依据/)
  assert.match(stories, /不作为脱离业务流程的独立事实源/)
  assert.match(stories, /按学校制度与角色权限配置/)
})

test('教务页搜索摘要覆盖关键采购词', () => {
  assert.match(salesPages, /职业院校教务管理系统｜排课、选课、考务、成绩、学籍、毕业审核全过程管理/)
  assert.match(salesPages, /教师移动端、学生 PC 与移动端协同办理/)
})
