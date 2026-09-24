import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { test } from 'node:test'
import { fileURLToPath } from 'node:url'

const read = (relativePath) => readFileSync(fileURLToPath(new URL(relativePath, import.meta.url)), 'utf8')
const page = read('../src/pages/student/affairs/leave.vue')
const studentApi = read('../src/services/studentApi.js')
const realApi = read('../src/services/realApi.js')

test('学生请假列表走服务端分页，异步迟到响应不会回写已卸载页面', () => {
  assert.match(page, /pageSize:\s*20/)
  assert.match(page, /studentApi\.getMyLeaves\(requestedPage, this\.pageSize\)/)
  assert.match(page, /loadEpoch/)
  assert.match(page, /onUnload\(\) \{ this\.detailEpoch\+\+; this\.loadEpoch\+\+ \}/)
  assert.match(page, /上一页/)
  assert.match(page, /下一页/)
  assert.match(studentApi, /getMyLeaves:\s*\(page = 1, pageSize = 20\)/)
  assert.match(realApi, /affairsLeaveMy\s*=\s*async \(page = 1, pageSize = 20\)/)
  assert.match(realApi, /\/mobile\/affairs\/leave\/my\?page=/)
})

test('请假证明先是私有临时文件，正式绑定只由提交或退回修改命令完成', () => {
  assert.match(page, /MobileAttachmentPicker/)
  assert.match(page, /biz-purpose="AFFAIRS_LEAVE"/)
  assert.match(page, /fileIds: this\.fileIds/)
  assert.match(page, /attachmentsReady/)
  assert.match(page, /已正式提交的历史材料会保留在办理详情/)
  assert.match(page, /this\.fileIds = \[\]/)
  assert.doesNotMatch(page, /localStorage\.(setItem|getItem).*leave/i)
})
