import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'

const here = path.dirname(fileURLToPath(import.meta.url))
const root = path.resolve(here, '..')
const page = fs.readFileSync(path.join(root, 'src/modules/academicAffairs/views/AaTeacherScheduleView.vue'), 'utf8')
const api = fs.readFileSync(path.join(root, 'src/modules/academicAffairs/api/academic-affairs.api.js'), 'utf8')
const changePage = fs.readFileSync(path.join(root, 'src/modules/academicAffairs/views/AaScheduleChangeApplyView.vue'), 'utf8')
const changeApi = fs.readFileSync(path.join(root, 'src/modules/academicAffairs/api/academic-schedule-change.api.js'), 'utf8')
const publishPage = fs.readFileSync(path.join(root, 'src/modules/academicAffairs/views/AaSchedulePublishView.vue'), 'utf8')
const batchPage = fs.readFileSync(path.join(root, 'src/modules/academicAffairs/views/AaScheduleBatchListView.vue'), 'utf8')

test('teacher PC consumes the same server-projected Teacher Today truth as the miniapp', () => {
  assert.match(api, /mobile\/academic\/teacher-schedule\/my/)
  assert.match(page, /todayRes\.data\.todayItems/)
  assert.match(page, /calendarSource === 'HOLIDAY'/)
  assert.match(page, /calendarSource === 'SWAP_SOURCE'/)
  assert.match(page, /calendarSource === 'OUT_OF_TERM'/)
  assert.doesNotMatch(page, /new Date\(\)\.getDay\(\)/)
})

test('teacher PC keeps arbitrary teacher lookup separate from self-only Today projection', () => {
  assert.match(page, /u\.loginName \|\| u\.userId/)
  assert.match(page, /this\.isSameTeacherKey\(this\.teacherKey\)/)
  assert.match(page, /Promise\.resolve\(null\)/)
  assert.match(page, /v-if="isSelfView"/)
})

test('published schedule UI separates daily changes from dangerous batch reissue', () => {
  for (const source of [publishPage, batchPage]) {
    assert.match(source, /日常单课位调课、停课、补课走「调停课」审批/)
    assert.match(source, /作废重发（重大纠错）/)
    assert.match(source, /调停课台账/)
  }
  assert.match(publishPage, /查看已发布课表/)
  assert.doesNotMatch(publishPage, /如需调整走「作废重发」/)
})

test('teacher timetable hands a selected published item into change application without editable IDs', () => {
  assert.match(page, /申请调课/)
  assert.match(page, /申请停课/)
  assert.match(page, /申请补课/)
  assert.match(page, /query: \{ originItemId: String\(originItemId\), changeType \}/)
  assert.match(changeApi, /origin-items\/\$\{itemId\}/)
  assert.match(changePage, /scheduleChangeApi\.originItem\(this\.form\.originItemId\)/)
  assert.match(changePage, /系统会自动带入正式课位，不需要复制或填写任何内部 ID/)
  assert.doesNotMatch(changePage, /v-model\.trim="form\.originItemId"/)
  assert.doesNotMatch(changePage, /请填写原课表项 ID/)
})
