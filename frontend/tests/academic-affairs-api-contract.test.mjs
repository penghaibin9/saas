import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'

const apiUrl = new URL(
  '../src/modules/academicAffairs/api/academic-affairs.api.js',
  import.meta.url
)

const d1Methods = [
  'getCurrentTerm',
  'getTerms',
  'createTerm',
  'publishTerm',
  'setCurrentTerm',
  'getTermDetail',
  'getTermWeeks',
  'updateTeachingWeeks',
  'freezeTerm',
  'unfreezeTerm',
  'getTermArchiveOverview',
  'getAcademicYears',
  'getTermSwitchLog',
  'getCalendar',
  'addCalendarEvent',
  'updateCalendarEvent',
  'deleteCalendarEvent',
  'getWeekCalendar',
  'publishCalendar',
  'getTimeSlots',
  'createTimeSlot',
  'updateTimeSlot',
  'deleteTimeSlot',
  'getTimeBands',
  'createTimeBand',
  'updateTimeBand',
  'deleteTimeBand'
]

function methodNames(source) {
  const names = []
  const pattern = /^ {2}(?:async\s+)?([A-Za-z_$][\w$]*)\s*\([^\n]*\)\s*\{/gm
  for (const match of source.matchAll(pattern)) names.push(match[1])
  return names
}

test('S0-F freezes D1 academicAffairsApi aggregate keys', async () => {
  const source = await readFile(apiUrl, 'utf8')
  const keys = methodNames(source)
  const unique = new Set(keys)

  assert.equal(unique.size, keys.length, 'academicAffairsApi contains duplicate top-level method names')
  for (const name of d1Methods) {
    assert.ok(unique.has(name), `missing academicAffairsApi D1 key: ${name}`)
  }
})

test('S0-F keeps D1 URL/method/body/query contracts stable', async () => {
  const source = await readFile(apiUrl, 'utf8')

  const contracts = [
    /getCurrentTerm\(\)[\s\S]*?request\(`\$\{BASE\}\/terms\/current`\)/,
    /getTerms\(params = \{\}\)[\s\S]*?callList\(`\$\{BASE\}\/terms`, params\)/,
    /createTerm\(body\)[\s\S]*?request\(`\$\{BASE\}\/terms`, \{ method: 'POST', body \}\)/,
    /publishTerm\(termId\)[\s\S]*?\/terms\/\$\{termId\}\/publish`[^\n]*method: 'POST'/,
    /setCurrentTerm\(termId\)[\s\S]*?\/terms\/\$\{termId\}\/set-current`[^\n]*method: 'POST'/,
    /updateTeachingWeeks\(termId, body\)[\s\S]*?\/teaching-weeks`[^\n]*method: 'PUT', body/,
    /freezeTerm\(termId\)[\s\S]*?\/freeze`[^\n]*method: 'POST'/,
    /unfreezeTerm\(termId, reason\)[\s\S]*?\/unfreeze`[^\n]*method: 'POST', body: \{ reason \}/,
    /getTermArchiveOverview\(\)[\s\S]*?\/terms\/archive-overview`/,
    /getAcademicYears\(\)[\s\S]*?\/terms\/years`/,
    /getTermSwitchLog\(params = \{\}\)[\s\S]*?\/terms\/switch-log`, params/,
    /getCalendar\(termId, eventType\)[\s\S]*?\/terms\/\$\{termId\}\/calendar`/,
    /addCalendarEvent\(termId, body\)[\s\S]*?\/calendar`[^\n]*method: 'POST', body/,
    /updateCalendarEvent\(termId, eventId, body\)[\s\S]*?\/calendar\/\$\{eventId\}`[^\n]*method: 'PUT', body/,
    /deleteCalendarEvent\(termId, eventId\)[\s\S]*?\/calendar\/\$\{eventId\}`[^\n]*method: 'DELETE'/,
    /publishCalendar\(termId\)[\s\S]*?\/calendar\/publish`[^\n]*method: 'POST'/,
    /getTimeSlots\(includeDisabled = false\)[\s\S]*?\/time-slots`/,
    /createTimeSlot\(body\)[\s\S]*?\/time-slots`[^\n]*method: 'POST', body/,
    /updateTimeSlot\(slotId, body\)[\s\S]*?\/time-slots\/\$\{slotId\}`[^\n]*method: 'PUT', body/,
    /deleteTimeSlot\(slotId\)[\s\S]*?\/time-slots\/\$\{slotId\}`[^\n]*method: 'DELETE'/,
    /getTimeBands\(slotId\)[\s\S]*?\/time-slots\/\$\{slotId\}\/time-bands`/,
    /createTimeBand\(slotId, body\)[\s\S]*?\/time-bands`[^\n]*method: 'POST', body/,
    /updateTimeBand\(bandId, body\)[\s\S]*?\/time-bands\/\$\{bandId\}`[^\n]*method: 'PUT', body/,
    /deleteTimeBand\(bandId\)[\s\S]*?\/time-bands\/\$\{bandId\}`[^\n]*method: 'DELETE'/
  ]

  for (const contract of contracts) assert.match(source, contract)
})
