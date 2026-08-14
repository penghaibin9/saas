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

function declarationCount(source, methodName) {
  const escaped = methodName.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  return [...source.matchAll(new RegExp(`^ {2}(?:async\\s+)?${escaped}\\s*\\(`, 'gm'))].length
}

test('S0-F freezes D1 academicAffairsApi aggregate keys', async () => {
  const source = await readFile(apiUrl, 'utf8')

  for (const name of d1Methods) {
    assert.equal(
      declarationCount(source, name),
      1,
      `academicAffairsApi D1 key must have one stable declaration: ${name}`
    )
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
