import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const read = (relativePath) => fs.readFileSync(path.join(root, relativePath), 'utf8')
const assetExists = (assetPath) => fs.existsSync(path.join(root, 'public', assetPath.replace(/^\//, '')))

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

test('学工中心官网采用十五个二级模块真实界面并逐张提供业务说明', () => {
  const screens = [
    ['/official-site/student-affairs-student360.png', '学生 360 全生命周期档案'],
    ['/official-site/student-affairs-student-roster.png', '学生主档统一管理'],
    ['/official-site/student-affairs-enrollment-status.png', '学籍异动全过程台账'],
    ['/official-site/student-affairs-class-counselor.png', '班级与辅导员责任关系'],
    ['/official-site/student-affairs-orientation-dashboard.png', '数字迎新进度看板'],
    ['/official-site/student-affairs-leave-closure.png', '请假、续假与销假闭环'],
    ['/official-site/student-affairs-dorm-checkin.png', '宿舍入住与床位实况'],
    ['/official-site/student-affairs-risk-workbench.png', '风险预警与责任处置'],
    ['/official-site/student-affairs-hardship-review.png', '困难学生认定评审'],
    ['/official-site/student-affairs-funding-review.png', '奖助勤贷补申请评审'],
    ['/official-site/student-affairs-discipline-workbench.png', '违纪处分办理与解除'],
    ['/official-site/student-affairs-talk-followup.png', '谈心谈话与持续跟进'],
    ['/official-site/student-affairs-mental-care.png', '心理关注与授权回访'],
    ['/official-site/student-affairs-activity-workbench.png', '活动、第二课堂与社团'],
    ['/official-site/student-affairs-archive-workbench.png', '学工材料归档与统计']
  ]

  for (const [asset, title] of screens) {
    assert.equal(assetExists(asset), true, `missing student-affairs screenshot ${asset}`)
    assert.match(products, new RegExp(asset.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')))
    assert.match(products, new RegExp(title.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')))
  }

  for (const evidence of ['实际运行界面', '逐人授权并填写业务原因', '不替代专业判断', '经过圈定学生、学院审核、学工处确认']) {
    assert.match(products, new RegExp(evidence))
  }
})
