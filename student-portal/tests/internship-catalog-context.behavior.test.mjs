import * as scopeModel from '../../shared/internshipSelectionScope.mjs'
import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import { parse } from '@vue/compiler-sfc'
import * as contextModel from '../src/modules/internshipRecruitment/contextModel.js'
import * as queryModel from '../src/modules/internshipRecruitment/selectionContract.js'
import * as volunteerModel from '../src/modules/internshipRecruitment/volunteerModel.js'
import * as materialModel from '../src/modules/internshipRecruitment/materialPreviewModel.js'
import * as positionModel from '../src/modules/internshipRecruitment/positionModel.js'
import * as mobileContext from '../../miniapp/src/modules/internshipSelectionModel.js'
import * as mobileVolunteer from '../../miniapp/src/modules/internshipVolunteerModel.js'
import { latestRead as latestProjectionRead } from '../../miniapp/src/services/latestRead.js'

const read = (path) => fs.readFileSync(new URL(path, import.meta.url), 'utf8')
const stripImports = (source) => source.replace(/^import[\s\S]*?from\s*['"][^'"]+['"]\s*$/gm, '')
const empty = { catalogState: 'NO_OPEN_CAMPAIGN', canSelect: false, selectionBlockReason: '等待学校开放' }
const available = { catalogState: 'AVAILABLE', campaignId: '1', campaignStatus: 'OPEN', canSelect: true }
const deferred = () => { let resolve; const promise = new Promise((r) => { resolve = r }); return { promise, resolve } }

function fixture(mobile = false, contextRequest = async () => empty) {
  const calls = []
  const api = { context: contextRequest, positions: async () => { calls.push('positions'); return { items: [], total: 0 } },
    volunteers: async () => { calls.push('volunteers'); return {} }, profile: async () => ({}), profileCompleteness: async () => ({}) }
  api.forScope = () => api
  if (mobile) {
    const source = parse(read('../../miniapp/src/pages/student-internship/enterprises/index.vue')).descriptor.script.content
    const deps = { ...scopeModel, ...mobileContext, ...mobileVolunteer, internshipSelectionApi: api, normalizeMobileCatalogQuery: queryModel.normalizeCatalogQuery }
    const options = new Function(...Object.keys(deps), stripImports(source).replace('export default', 'return'))(...Object.values(deps))
    const page = { ...options.data() }
    for (const [name, method] of Object.entries(options.methods)) page[name] = method.bind(page)
    for (const [name, getter] of Object.entries(options.computed)) Object.defineProperty(page, name, { get: () => getter.call(page) })
    return { page, calls, unload: () => options.onUnload.call(page), api }
  }
  const source = parse(read('../src/views/internship/InternshipSelectionView.vue')).descriptor.scriptSetup.content
  let unload = () => {}
  const deps = { ...contextModel, ...queryModel, ...volunteerModel, ...materialModel, ...positionModel, internshipSelectionApi: api,
    ref: (value) => ({ value }), computed: (getter) => ({ get value() { return getter() } }),
    watch: () => {}, useRoute: () => ({ query: {} }), onMounted: () => {}, onBeforeUnmount: (fn) => { unload = fn }, useRouter: () => ({ push() {} }) }
  const page = new Function(...Object.keys(deps), stripImports(source) + '\nreturn {loadContext, loadPositions, loadVolunteerGroup, context, error, catalogReady}')(...Object.values(deps))
  return { page, calls, unload: () => unload(), api }
}

for (const mobile of [false, true]) {
  const label = mobile ? 'mobile' : 'PC'
  const ready = (page) => mobile ? page.catalogReady : page.catalogReady.value
  const value = (page) => mobile ? page.context : page.context.value
  test(label + ': preparation does not request a nonexistent catalog or volunteer group', async () => {
    const { page, calls } = fixture(mobile)
    await page.loadContext(); await page.loadPositions()
    assert.equal(ready(page), false); assert.deepEqual(calls, [])
    assert.equal(value(page).catalogState, 'NO_OPEN_CAMPAIGN')
  })
  test(label + ': retry after school opens drives both catalog and volunteer reads', async () => {
    let current = empty
    const { page, calls } = fixture(mobile, async () => current)
    await page.loadContext(); current = available; await page.loadContext()
    assert.equal(ready(page), true); assert.deepEqual(calls.sort(), ['positions', 'volunteers'])
  })
  test(label + ': connection failures stay errors and never become an empty business result', async () => {
    const { page, calls } = fixture(mobile, async () => { throw new Error('连接失败') })
    await page.loadContext()
    assert.equal(ready(page), false); assert.equal(mobile ? page.contextError : page.error.value, '连接失败')
    assert.deepEqual(calls, [])
  })
  test(label + ': stale context cannot overwrite a newer result or start extra reads', async () => {
    const old = deferred(); let count = 0
    const { page, calls } = fixture(mobile, () => ++count === 1 ? old.promise : Promise.resolve(empty))
    const pending = page.loadContext(); await page.loadContext()
    old.resolve(available); await pending
    assert.equal(value(page).catalogState, 'NO_OPEN_CAMPAIGN'); assert.deepEqual(calls, [])
  })
  test(label + ': a context completing after unmount does not load catalog data', async () => {
    const old = deferred()
    const { page, calls, unload } = fixture(mobile, () => old.promise)
    const pending = page.loadContext(); unload(); old.resolve(available); await pending
    assert.deepEqual(calls, [])
  })
}

test('both API adapters preserve rejection instead of fabricating UNAVAILABLE', async () => {
  for (const path of ['../src/services/internshipSelectionApi.js', '../../miniapp/src/services/internshipSelectionApi.js']) {
    const source = stripImports(read(path)).replace(/export default internshipSelectionApi\s*/g, '').replace(/export /g, '')
    const fail = async () => { throw new Error('连接失败') }
    const deps = { ...scopeModel, baseRequest: fail, normalizeCatalogQuery: queryModel.normalizeCatalogQuery, latestProjectionRead }
    const api = new Function(...Object.keys(deps), source + '\nreturn internshipSelectionApi')(...Object.values(deps))
    await assert.rejects(api.context(), /连接失败/)
  }
})
