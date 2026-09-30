import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import { parse } from '@vue/compiler-sfc'
import { computed, reactive, ref } from 'vue'
import * as profileModel from '../src/modules/internshipRecruitment/profileModel.js'
import * as materialModel from '../src/modules/internshipRecruitment/materialPreviewModel.js'

const source = parse(fs.readFileSync(new URL('../src/views/internship/InternshipProfileView.vue', import.meta.url), 'utf8')).descriptor.scriptSetup.content.replace(/^import[\s\S]*?from\s*['"][^'"]+['"]\s*$/gm, '')
function fixture(apis) {
  const route = reactive({ query: { campaignId: '1' } })
  let dispose
  const deps = { ...profileModel, ...materialModel, ref, computed, useRoute: () => route,
    useRouter: () => ({}), watch() {}, onMounted() {}, onBeforeUnmount: fn => { dispose = fn },
    internshipSelectionApi: { forScope: scope => apis[scope.campaignId] } }
  const page = new Function(...Object.keys(deps), source+'\nreturn {load,generatePdfPreview,pdfUrl,preview,profile,previewError}')(...Object.values(deps))
  return { page, route, dispose: () => dispose() }
}
const deferred = () => { let resolve; const promise = new Promise(r => { resolve = r }); return { promise, resolve } }
const api = (label) => ({ profile: async () => ({ selfIntro: label }), profileCompleteness: async () => ({}), profileItems: async () => [], profilePreview: async () => ({ previewHash: label }), profilePdfPreview: async () => ({ url: label }) })

test('new round replaces preview and old PDF response cannot cross the route', async () => {
  const pending = deferred()
  const a = { ...api('old'), profilePdfPreview: () => pending.promise }
  const { page, route } = fixture({ '1': a, '2': api('new') })
  await page.load(); const oldPdf = page.generatePdfPreview()
  route.query.campaignId = '2'; await page.load()
  pending.resolve({ url: 'old-private-file' }); await oldPdf
  assert.equal(page.preview.value.previewHash, 'new'); assert.equal(page.pdfUrl.value, '')
})
test('disposed profile page ignores a pending PDF', async () => {
  const pending = deferred()
  const { page, dispose } = fixture({ '1': { ...api('old'), profilePdfPreview: () => pending.promise } })
  await page.load(); const oldPdf = page.generatePdfPreview(); dispose()
  pending.resolve({ url: 'old-private-file' }); await oldPdf
  assert.equal(page.pdfUrl.value, '')
})
