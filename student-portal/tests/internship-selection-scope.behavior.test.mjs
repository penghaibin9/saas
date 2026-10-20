import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import * as scopeModel from '../../shared/internshipSelectionScope.mjs'
import { normalizeCatalogQuery } from '../src/modules/internshipRecruitment/selectionContract.js'
import { latestRead as latestProjectionRead } from '../../miniapp/src/services/latestRead.js'

const scope = { batchId: '10', campaignId: '20', recordId: '30' }
function apiFor(mobile, request) {
  const path = mobile ? '../../miniapp/src/services/internshipSelectionApi.js' : '../src/services/internshipSelectionApi.js'
  const source = fs.readFileSync(new URL(path, import.meta.url), 'utf8').replace(/^import[^\n]+\n/gm, '')
    .replace(/export default internshipSelectionApi\s*/g, '').replace(/export /g, '')
  const deps = { ...scopeModel, baseRequest: request, normalizeCatalogQuery, latestProjectionRead }
  return new Function(...Object.keys(deps), source+'\nreturn internshipSelectionApi')(...Object.values(deps))
}
for (const mobile of [false, true]) {
  test(`${mobile ? 'mobile' : 'PC'} reads and writes preserve the page round without global mutation`, async () => {
    const calls = []
    const api = apiFor(mobile, async (path, options) => { calls.push({ path, options }); return {} }).forScope(scope)
    await api.context(); await api.positions({ keyword: '设备', page: 2 }); await api.position('7'); await api.company('8')
    await api.volunteers(); await api.materialPreview()
    await api.profileCompleteness()
    if (!mobile) await api.profilePreview()
    await api.submitVolunteers({ expectedGroupVersion: 5, expectedRecordVersion: 6 })
    await api.withdrawVolunteers({ expectedGroupVersion: 5 })
    for (const call of calls) {
      const query = new URL(call.path, 'http://example.test').searchParams
      for (const key of Object.keys(scope)) assert.equal(query.get(key), scope[key])
      assert.equal(query.getAll('campaignId').length, 1)
    }
    for (const call of calls.slice(-2)) {
      const body = call.options[mobile ? 'data' : 'body']
      assert.equal(body.campaignId, '20'); assert.equal(body.recordId, '30'); assert.equal(body.expectedGroupVersion, 5)
    }
    assert.throws(() => api.saveVolunteers({ campaignId: '99' }), /不一致/)
    assert.throws(() => api.submitVolunteers({ internshipId: '99' }), /不一致/)
  })
  test(`${mobile ? 'mobile' : 'PC'} factories isolate concurrent contexts and reject incomplete links`, async () => {
    const pending = []
    const api = apiFor(mobile, path => new Promise(resolve => pending.push({ path, resolve })))
    assert.throws(() => api.forScope({ campaignId: '20' }), /定位不完整/)
    assert.throws(() => api.forScope({ ...scope, recordId: ['30', '31'] }), /定位不完整/)
    const a = api.forScope(scope).context()
    const b = api.forScope({ ...scope, campaignId: '21' }).context()
    await Promise.resolve()
    pending[1].resolve({ id: 'new' }); pending[0].resolve({ id: 'old' })
    assert.equal((await a).id, 'old'); assert.equal((await b).id, 'new')
  })
}
