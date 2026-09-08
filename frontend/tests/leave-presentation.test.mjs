import test from 'node:test'
import { Buffer } from 'node:buffer'
import process from 'node:process'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
const here = path.dirname(fileURLToPath(import.meta.url))
const root = path.resolve(here, '../..')
const labels = JSON.parse(fs.readFileSync(path.join(root, 'shared/contracts/leave-presentation.json'), 'utf8'))
const relative = "frontend/src/modules/studentAffairs/utils/leavePresentation.js"
const source = fs.readFileSync(path.join(root, relative), 'utf8').replace(/^import labels[^\n]+/m, 'const labels = ' + JSON.stringify(labels))
const { presentLeave, leaveError, leaveDate } = await import('data:text/javascript;base64,' + Buffer.from(source).toString('base64'))
process.env.TZ = 'Asia/Shanghai'
test('unknown leave enums never leak machine values, user text remains intact', () => {
  const item = presentLeave({ id:'9007199254740993', status:'NEW_INTERNAL_STATE', leaveType:'NEW_TYPE', reason:'参加 ACM 比赛', studentName:'Alice', allowedActions:[] })
  assert.equal(item.statusLabel, '状态待确认')
  assert.equal(item.leaveTypeLabel, '假种待确认')
  assert.equal(item.reason, '参加 ACM 比赛')
  assert.equal(item.studentName, 'Alice')
  assert.equal(item.id, '9007199254740993')
  assert.equal(presentLeave({status:'__proto__'}).statusLabel, '状态待确认')
})
test('RFC3339 leave dates render on the correct local day', () => {
  assert.equal(leaveDate('2026-09-04T16:00:00Z'), '2026-09-05')
  assert.equal(leaveDate('2026-09-05T15:59:59Z', true), '2026-09-05 23:59')
  assert.equal(leaveDate('2026-09-05'), '2026-09-05')
  assert.equal(leaveDate('invalid'), '—')
})
test('timeline exposes readable known and unknown events', () => {
  const item = presentLeave({status:'WAIT_CANCEL_LEAVE', timeline:[{action:'EXTENSION_APPROVED',description:'fromStatus=RAW'}, {action:'UNRECOGNIZED_INTERNAL_EVENT'}]})
  assert.equal(item.statusLabel, '返校待确认')
  assert.equal(item.timeline[0].actionLabel, '续假批准')
  assert.equal(item.timeline[1].actionLabel, '办理状态已更新')
  assert.ok(!JSON.stringify(item.timeline.map(e=>e.description)).includes('fromStatus'))
})
test('technical errors are Chinese and conflicts keep inputs recoverable', () => {
  for (const error of [{message:'Network Error'}, {message:'权限失败 studentId=1'}, {message:'查询错误 SQL SELECT'}, {message:'失败 UNKNOWN_INTERNAL_CODE'}]) assert.equal(leaveError(error), '操作未完成，请重试')
  assert.match(leaveError({code:409001, message:'VERSION_CONFLICT'}), /内容仍保留/)
  assert.equal(leaveError({message:'结束日期必须晚于开始日期'}), '结束日期必须晚于开始日期')
})
