import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const read = (relativePath) => fs.readFileSync(path.join(root, relativePath), 'utf8')
const assetExists = (assetPath) => fs.existsSync(path.join(root, 'public', assetPath.replace(/^\//, '')))
const escapeRegExp = (text) => text.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')

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

test('教务官网采用二十五个二级模块真实界面并逐张提供业务说明', () => {
  const screens = [
    ['/official-site/academic-workbench.png', '教务运行阻断工作台'],
    ['/official-site/academic-calendar.png', '校历节次与教学日历'],
    ['/official-site/academic-term-governance.png', '学年学期与业务日历治理'],
    ['/official-site/academic-enrollment-change-detail-annotated.png', '学籍异动审批详情'],
    ['/official-site/academic-registration-roster.png', '注册名单批量办理'],
    ['/official-site/academic-major-placement.png', '专业分流与志愿分配'],
    ['/official-site/academic-enrollment-change-ledger.png', '学籍异动全流程台账'],
    ['/official-site/academic-org-structure.png', '学院、专业与班级组织'],
    ['/official-site/academic-program-editor.png', '人才培养方案编制与校验'],
    ['/official-site/academic-course-catalog.png', '课程库与课程标准'],
    ['/official-site/academic-teaching-plan.png', '学期教学计划工作台'],
    ['/official-site/academic-task-progress-annotated.png', '教学任务执行进度'],
    ['/official-site/academic-scheduling-rules.png', '排课规则与冲突约束'],
    ['/official-site/academic-schedule-change-annotated.png', '调课、停课与补课申请'],
    ['/official-site/academic-attendance-stats.png', '课堂考勤与缺勤统计'],
    ['/official-site/academic-warning-dashboard.png', '学业预警教务处控制台'],
    ['/official-site/academic-course-selection-annotated.png', '选课批次、容量与名单锁定'],
    ['/official-site/academic-grade-correction-annotated.png', '成绩更正申请与审核'],
    ['/official-site/academic-graduation-precheck.png', '毕业资格十一项预审'],
    ['/official-site/academic-graduation-audit-annotated.png', '毕业资格审核工作台'],
    ['/official-site/academic-textbook-management.png', '教材目录、选用与费用台账'],
    ['/official-site/academic-resource-management.png', '教室、实训室与设备资源'],
    ['/official-site/academic-evaluation.png', '教学评价与申诉审核'],
    ['/official-site/academic-quality-dashboard.png', '教学质量运行看板'],
    ['/official-site/academic-archive-export.png', '教务档案归档与导出']
  ]

  for (const [asset, title] of screens) {
    assert.equal(assetExists(asset), true, `missing academic-affairs screenshot ${asset}`)
    assert.match(products, new RegExp(escapeRegExp(asset)))
    assert.match(products, new RegExp(escapeRegExp(title)))
  }

  for (const evidence of ['重点标注实际界面', '不允许静默覆盖', '跨域十一项审核', '带水印批量打包']) {
    assert.match(products, new RegExp(evidence))
  }
})
