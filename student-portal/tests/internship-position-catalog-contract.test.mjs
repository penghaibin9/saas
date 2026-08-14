import test from 'node:test'
import assert from 'node:assert/strict'

import {
  CATALOG_MAX_PAGE_SIZE,
  CATALOG_PAGE_SIZE,
  CATALOG_SORTS,
  normalizeCatalogQuery
} from '../src/modules/internshipRecruitment/selectionContract.js'

test('A03-2 catalog defaults to server pagination 20 and max 100', () => {
  assert.equal(CATALOG_PAGE_SIZE, 20)
  assert.equal(CATALOG_MAX_PAGE_SIZE, 100)
  assert.deepEqual(normalizeCatalogQuery({}), { page: 1, pageSize: 20, sort: 'RECOMMENDED' })
  assert.equal(normalizeCatalogQuery({ pageSize: 101 }).pageSize, 100)
})

test('A03-2 catalog forwards V3 filters instead of client materialize/filter', () => {
  const query = normalizeCatalogQuery({
    page: 3,
    keyword: '数控 长沙',
    city: '长沙',
    companyId: 18,
    accommodation: true,
    meal: false,
    industry: '智能制造',
    scale: '500-999',
    nightShift: false,
    weeklyHours: 40,
    remaining: 2,
    publishedFrom: '2026-08-01',
    majorMatched: true,
    remuneration: 3000,
    sort: 'REMAINING'
  })
  assert.equal(query.page, 3)
  assert.equal(query.pageSize, 20)
  assert.equal(query.keyword, '数控 长沙')
  assert.equal(query.city, '长沙')
  assert.equal(query.companyId, 18)
  assert.equal(query.accommodation, true)
  assert.equal(query.meal, false)
  assert.equal(query.nightShift, false)
  assert.equal(query.weeklyHours, 40)
  assert.equal(query.remaining, 2)
  assert.equal(query.majorMatched, true)
  assert.equal(query.sort, 'REMAINING')
})

test('A03-2 only accepts frozen server sort contract', () => {
  assert.deepEqual(CATALOG_SORTS, ['RECOMMENDED', 'LATEST', 'REMUNERATION', 'REMAINING'])
  assert.equal(normalizeCatalogQuery({ sort: 'CLIENT_SCORE' }).sort, 'RECOMMENDED')
})
