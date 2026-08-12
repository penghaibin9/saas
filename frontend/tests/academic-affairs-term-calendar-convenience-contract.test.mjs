import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'

const apiUrl = new URL(
  '../src/modules/academicAffairs/api/term-calendar-convenience.api.js',
  import.meta.url
)
const calendarUrl = new URL(
  '../src/modules/academicAffairs/views/AaCalendarView.vue',
  import.meta.url
)
const timeSlotUrl = new URL(
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

test('D1-U pages keep final writes on existing academicAffairsApi canonical methods', async () => {
  const [calendar, timeSlot] = await Promise.all([
    readFile(calendarUrl, 'utf8'),
    readFile(timeSlotUrl, 'utf8')
  ])

  // These are the only permitted final-write owners for the convenience workflow.
  assert.match(calendar, /academicAffairsApi\.addCalendarEvent\(/)
  assert.match(timeSlot, /academicAffairsApi\.createTimeSlot\(/)

  // Once the UI is wired, it must call preview through the dedicated read-side adapter.
  assert.match(calendar, /termCalendarConvenienceApi\.previewCalendarCopy\(/)
  assert.match(timeSlot, /termCalendarConvenienceApi\.previewTimeSlotTemplate\(/)
})
