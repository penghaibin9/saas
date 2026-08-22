import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const here = path.dirname(fileURLToPath(import.meta.url))
const viewPath = path.resolve(here, '../src/modules/academicAffairs/views/AaScheduleMaintainView.vue')
const drawerPath = path.resolve(here, '../src/modules/academicAffairs/components/AaAuthoritativeImportDrawer.vue')
const apiPath = path.resolve(here, '../src/modules/academicAffairs/api/academic-file-exchange.api.js')
const source = fs.readFileSync(viewPath, 'utf8')
const drawer = fs.readFileSync(drawerPath, 'utf8')
const api = fs.readFileSync(apiPath, 'utf8')

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
