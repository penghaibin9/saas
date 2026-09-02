import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'

const layout = fs.readFileSync(new URL('../src/modules/graduation/views/AdminGraduationLayout.vue', import.meta.url), 'utf8')
const batchStrip = fs.readFileSync(new URL('../src/modules/graduation/views/_shared/GraduationBatchStrip.vue', import.meta.url), 'utf8')

test('G10 graduation module shell removes repeated intro without hiding valid business tabs', () => {
  assert.doesNotMatch(layout, /gd-page-intro/)
  assert.doesNotMatch(layout, /mp-tabs \.mp-tab:nth-child\(8\)/)
  assert.match(layout, /class="gd-batch-context"/)
  assert.match(layout, /<GraduationBatchStrip class="gd-batch-bar" \/>/)
  assert.match(layout, /class="gd-business-view"/)
})

test('G10 keeps fail-closed permission and data-scope projection', () => {
  assert.match(layout, /permissionReady/)
  assert.match(layout, /scopeReady/)
  assert.match(layout, /writeEnabled: this\.permissionReady && !this\.ctx\.readonlyTenant && studentListWrite/)
  assert.match(layout, /GraduationExtensionAdminPanel/)
  assert.match(layout, /<router-view v-else :key="businessViewKey" :ctx="businessCtx" \/>/)
})

test('G10 visually compresses but does not replace batch store, URL or validation semantics', () => {
  assert.match(layout, /useGraduationBatchStore/)
  assert.match(layout, /store\.ensureLoaded\(\{ batchIdFromUrl: id \|\| '', force: !store\.initialized \}\)/)
  assert.match(layout, /syncBatchToUrl\(\)/)
  assert.match(layout, /batchId=/)

  assert.match(batchStrip, /useGraduationBatchStore/)
  assert.match(batchStrip, /this\.store\.selectBatch\(id\)/)
  assert.match(batchStrip, /q\.batchId = id/)
  assert.match(batchStrip, /this\.\$router\.replace\(\{ query: q \}\)/)
  assert.match(batchStrip, /store\.needsExplicitSelect/)
})

test('G10 remains inside the graduation module and keeps BasePortalLayout unchanged', () => {
  assert.match(layout, /import BasePortalLayout from '@\/layouts\/BasePortalLayout\.vue'/)
  assert.match(layout, /import \{ graduationPickerAdapters \}/)
  assert.match(layout, /provide\(\) \{ return \{ appPickerAdapters: graduationPickerAdapters \} \}/)
  assert.match(layout, /@menu-select="onMenuSelect"/)
})
