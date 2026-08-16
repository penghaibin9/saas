import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

import {
  normalizeMobilePage,
  normalizeMobilePosition,
  normalizeMobileSelectionContext
} from '../src/modules/internshipSelectionModel.js'

const pageSource = readFileSync(new URL('../src/pages/student/internship/enterprises/index.vue', import.meta.url), 'utf8')
const apiSource = readFileSync(new URL('../src/services/internshipSelectionApi.js', import.meta.url), 'utf8')

test('A03-9 preserves old enterprises route file but renames product surface to 实习选岗', () => {
  assert.match(pageSource, /:title="navTitle"/)
  assert.match(pageSource, /navTitle\(\)\s*\{[^\n]*'实习选岗'/)
  assert.match(pageSource, /学校认可岗位/)
})

test('A03-9 forbids client full-list filtering and uses server catalog pagination', () => {
  assert.doesNotMatch(pageSource, /(?:this\.)?positions\.filter\s*\(/)
  assert.match(pageSource, /internshipSelectionApi\.positions/)
  assert.match(pageSource, /pageSize:\s*20/)
  assert.match(pageSource, /350/)
})

test('A03-9 mobile context exposes campaign, deadline, supply and volunteer progress', () => {
  const context = normalizeMobileSelectionContext({
    campaign: { name: '2026 秋季实习双选', status: 'OPEN', studentSelectionEndAt: '2026-09-10T18:00:00+08:00' },
    stats: { publishedPositions: 120, partnerCompanies: 42, matchedPositions: 30 },
    volunteerGroup: { status: 'DRAFT', selectedCount: 2 }
  })
  assert.equal(context.campaignName, '2026 秋季实习双选')
  assert.equal(context.canSelect, true)
  assert.equal(context.publishedPositions, 120)
  assert.equal(context.partnerCompanies, 42)
  assert.equal(context.matchedPositions, 30)
  assert.equal(context.selectedVolunteers, 2)
})

test('A03-9 mobile job card keeps only 2-3 compact tags and backend match state', () => {
  const position = normalizeMobilePosition({
    id: 201,
    title: '数控加工实习生',
    remunerationDisplay: '3200-3800 元/月',
    companyName: '企业A',
    workLocation: '长沙',
    remaining: 6,
    matchState: 'MATCHED',
    accommodationProvided: true,
    mealProvided: true,
    benefitTags: ['餐补', '班车']
  })
  assert.equal(position.matchState, 'MATCHED')
  assert.equal(position.tags.length, 3)
  assert.deepEqual(position.tags, ['专业匹配', '提供住宿', '提供餐食'])
  const page = normalizeMobilePage({ items: [position], total: 25, page: 1, pageSize: 20 })
  assert.equal(page.total, 25)
  assert.equal(page.items.length, 1)
})

test('A03 production seal makes mobile authority reads latest-wins and context fail-closed', () => {
  assert.match(apiSource, /function latestRead\(/)
  assert.match(apiSource, /context\(\) \{ return latestRead\('context'/)
  assert.match(apiSource, /position\(positionId\) \{ return latestRead\('position'/)
  assert.match(apiSource, /company\(companyId\) \{ return latestRead\('company'/)
  assert.match(apiSource, /profile\(\) \{ return latestRead\('profile'/)
  assert.match(apiSource, /volunteers\(\) \{ return latestRead\('volunteers'/)
  assert.match(apiSource, /canSelect: false/)
  assert.match(apiSource, /selectionBlockReason/)
  assert.match(apiSource, /availableFrom: profile\?\.availableFrom/)
})

test('A03 mobile profile read switches only to the registered P0 context authority', () => {
  assert.match(apiSource, /realRequest\('\/mobile\/internship\/context\/profile'\)/)
  assert.doesNotMatch(apiSource, /realRequest\('\/mobile\/internship\/profile'\)/)
  assert.match(apiSource, /\/mobile\/internship\/profile\/completeness/)
})
