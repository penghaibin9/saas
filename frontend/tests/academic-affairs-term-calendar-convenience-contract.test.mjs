import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'

const apiUrl = new URL(
  '../src/modules/academicAffairs/api/term-calendar-convenience.api.js',
  import.meta.url
)
const calendarPanelUrl = new URL(
  '../src/modules/academicAffairs/components/AaCalendarCopyPanel.vue',
  import.meta.url
)
const timeSlotPanelUrl = new URL(
  '../src/modules/academicAffairs/components/AaTimeSlotTemplatePanel.vue',
  import.meta.url
)
const calendarViewUrl = new URL(
  '../src/modules/academicAffairs/views/AaCalendarView.vue',
  import.meta.url
)
const timeSlotViewUrl = new URL(
  '../src/modules/academicAffairs/views/AaTimeSlotView.vue',
  import.meta.url
)

test('D1-U convenience API remains preview-only and uses canonical URLs', async () => {
  const source = await readFile(apiUrl, 'utf8')

  assert.match(source, /previewCalendarCopy\(targetTermId, sourceTermId\)/)
  assert.match(source, /\/terms\/\$\{targetTermId\}\/calendar\/copy-preview/)
  assert.match(source, /method: 'POST'[\s\S]*body: \{ sourceTermId \}/)
  assert.match(source, /previewTimeSlotTemplate\(templateKey\)/)
  assert.match(source, /\/time-slots\/template-preview/)
  assert.match(source, /body: \{ templateKey \}/)

  assert.doesNotMatch(source, /\/calendar\/copy-confirm/)
  assert.doesNotMatch(source, /\/time-slots\/template-apply/)
})

test('D1-U panels keep final writes on existing canonical methods', async () => {
  const [calendarPanel, timeSlotPanel] = await Promise.all([
    readFile(calendarPanelUrl, 'utf8'),
    readFile(timeSlotPanelUrl, 'utf8')
  ])

  assert.match(calendarPanel, /termCalendarConvenienceApi\.previewCalendarCopy\(/)
  assert.match(calendarPanel, /academicAffairsApi\.addCalendarEvent\(/)
  assert.match(timeSlotPanel, /termCalendarConvenienceApi\.previewTimeSlotTemplate\(/)
  assert.match(timeSlotPanel, /academicAffairsApi\.createTimeSlot\(/)

  assert.doesNotMatch(calendarPanel, /localStorage|sessionStorage/)
  assert.doesNotMatch(timeSlotPanel, /localStorage|sessionStorage/)
})

test('D1-U panels are embedded in existing workspaces instead of replacing them', async () => {
  const [calendarView, timeSlotView] = await Promise.all([
    readFile(calendarViewUrl, 'utf8'),
    readFile(timeSlotViewUrl, 'utf8')
  ])

  assert.match(calendarView, /<AaCalendarCopyPanel/)
  assert.match(calendarView, /academicAffairsApi\.addCalendarEvent\(/)
  assert.match(calendarView, /academicAffairsApi\.publishCalendar\(/)

  assert.match(timeSlotView, /<AaTimeSlotTemplatePanel/)
  assert.match(timeSlotView, /academicAffairsApi\.createTimeSlot\(/)
  assert.match(timeSlotView, /academicAffairsApi\.createTimeBand\(/)
})
