import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'

const here = path.dirname(fileURLToPath(import.meta.url))
const root = path.resolve(here, '..')
const selection = fs.readFileSync(path.join(root, 'src/views/academic/StudentSelectionView.vue'), 'utf8')
const schedule = fs.readFileSync(path.join(root, 'src/views/academic/StudentScheduleView.vue'), 'utf8')

test('selection shows published meeting context before the student acts', () => {
  assert.match(selection, /上课安排/)
  assert.match(selection, /course\.scheduleItems/)
  assert.match(selection, /时间待排，以正式课表为准/)
})

test('selection success gives one clear next step and counts locked results', () => {
  assert.match(selection, /查看我的课表/)
  assert.match(selection, /名单锁定且课表正式发布后/)
  assert.match(selection, /\['SELECTED', 'LOCKED'\]/)
})

test('schedule leads with a backend-projected today view', () => {
  assert.match(schedule, /今天上什么课始终以正式课表为准|今天没有课程安排|今天有/)
  assert.match(schedule, /schedule\.value\.todayItems/)
  assert.match(schedule, /calendarSource/)
  assert.match(schedule, /今天 ·/)
})
