import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const here = path.dirname(fileURLToPath(import.meta.url))
const viewPath = path.resolve(here, '../src/modules/academicAffairs/views/AaScheduleMaintainView.vue')
const source = fs.readFileSync(viewPath, 'utf8')

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

test('schedule import uses authoritative File Exchange instead of text CSV writer', () => {
  assert.match(source, /AppExcelImportDrawer/)
  assert.match(source, /academicFileExchangeApi\.uploadScheduleImport\(this\.batchId, file\)/)
  assert.match(source, /academicFileExchangeApi\.confirmImport\(this\.currentImportJob\.id, this\.currentImportJob\.version\)/)
  assert.doesNotMatch(source, /<textarea/)
  assert.doesNotMatch(source, /importText/)
  assert.doesNotMatch(source, /academicAffairsApi\.importSchedule/)
})
