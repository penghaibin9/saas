import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const here = path.dirname(fileURLToPath(import.meta.url))
const viewPath = path.resolve(here, '../src/modules/academicAffairs/views/AaScheduleMaintainView.vue')
const drawerPath = path.resolve(here, '../src/modules/academicAffairs/components/AaAuthoritativeImportDrawer.vue')
const apiPath = path.resolve(here, '../src/modules/academicAffairs/api/academic-file-exchange.api.js')
const scheduleApiPath = path.resolve(here, '../src/modules/academicAffairs/api/academic-affairs.api.js')
const dialogPath = path.resolve(here, '../src/components/common/AppConfirmDialog.vue')
const source = fs.readFileSync(viewPath, 'utf8')
const drawer = fs.readFileSync(drawerPath, 'utf8')
const api = fs.readFileSync(apiPath, 'utf8')
const scheduleApi = fs.readFileSync(scheduleApiPath, 'utf8')
const dialog = fs.readFileSync(dialogPath, 'utf8')

test('schedule maintenance is READY TeachingTask-first', () => {
  assert.match(source, /listAllTasks\(\{\s*status:\s*'READY'/)
  assert.match(source, /taskId:\s*String\(task\.taskId\)/)
  assert.match(source, /selectedTask\?\.courseName/)
  assert.match(source, /selectedTask\?\.teacherName/)
  assert.match(source, /selectedTask\?\.teachingClassName/)
  assert.doesNotMatch(source, /AppCoursePicker/)
  assert.doesNotMatch(source, /AppTeacherPicker/)
})

test('schedule weeks come from task rather than an 18-week UI default', () => {
  assert.match(source, /this\.add\.startWeek = task\?\.startWeek \?\? null/)
  assert.match(source, /this\.add\.endWeek = task\?\.endWeek \?\? null/)
  assert.doesNotMatch(source, /endWeek:\s*18/)
  assert.doesNotMatch(source, /startWeek:\s*1,\s*endWeek:\s*18/)
})

test('schedule import uses the server-authoritative ImportJob flow instead of browser rows or text CSV', () => {
  assert.match(source, /AaAuthoritativeImportDrawer/)
  assert.match(source, /show-import-mode/)
  assert.match(source, /:upload-fn="\(file, mode\) => academicFileExchangeApi\.uploadScheduleImport\(batchId, file, mode\)"/)
  assert.match(api, /uploadScheduleImport\(batchId, file, importMode = 'ATOMIC'\)/)
  assert.match(api, /\['ATOMIC', 'PARTIAL'\]/)
  assert.match(drawer, /academicFileExchangeApi\.confirmImport\(this\.job\.id, this\.job\.version\)/)
  assert.match(drawer, /academicFileExchangeApi\.exportImportErrors\(this\.job\.id\)/)
  assert.match(drawer, /createExportDownloadTicket\(exportJob\.id, exportJob\.version\)/)
  assert.doesNotMatch(drawer, /confirmImport\([^)]*rows/)
  assert.doesNotMatch(source, /<textarea[^>]*v-model="importText"/)
  assert.doesNotMatch(source, /academicAffairsApi\.importSchedule/)
})

test('schedule add and drag candidates use a pure-read preflight before the canonical write', () => {
  assert.match(scheduleApi, /preflightScheduleItem\(batchId, body\)/)
  assert.match(scheduleApi, /items\/preflight/)
  assert.match(scheduleApi, /preflightScheduleMove\(itemId, weekday, slotNo\)/)
  assert.match(scheduleApi, /move-preflight/)
  assert.match(source, /academicAffairsApi\.preflightScheduleItem\(this\.batchId, body\)/)
  assert.match(source, /academicAffairsApi\.preflightScheduleMove\(item\.itemId, weekday, slotNo\)/)
  assert.match(source, /存在硬冲突，最终提交已锁定/)
  assert.match(source, /可选无硬冲突时段/)
  assert.match(source, /:options="weekdayOptions"/)
  assert.match(source, /:options="slotOptions"/)
  assert.match(source, /可改到无硬冲突时段/)
  assert.match(source, /checked\.data\?\.alternatives \|\| \[\]/)
  assert.match(source, /:confirm-disabled="preflight\.loading \|\| !preflight\.result\?\.allowed"/)
  assert.match(dialog, /confirmDisabled:\s*\{ type: Boolean/)
  assert.match(source, /size="wide"/)
  assert.match(dialog, /:disabled="busy \|\| confirmDisabled"/)
})

test('task-first handoff does not expose raw class or teaching-task ids', () => {
  assert.match(source, /已从排课工作台定位任务/)
  assert.doesNotMatch(source, /<small>ID \{\{/)
  assert.doesNotMatch(source, /`班级\$\{task\.classId/)
})
