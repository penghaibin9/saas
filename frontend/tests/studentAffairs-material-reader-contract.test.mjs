import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'

const root = path.resolve(fileURLToPath(new URL('../', import.meta.url)))
const read = (relative) => fs.readFileSync(path.join(root, relative), 'utf8')

const api = read('src/modules/studentAffairs/api/operations.api.js')
const view = read('src/modules/studentAffairs/views/MaterialOperationsView.vue')

test('student affairs material API signs version-bound business tickets', () => {
  assert.match(api, /issueMaterialTicket\(version = \{\}, action = 'preview'\)/)
  assert.match(api, /fileVersionId: version\.fileVersionId/)
  assert.match(api, /`\$\{MATERIAL_BASE\}\/files\/\$\{enc\(version\.fileId\)\}\/ticket`/)
  assert.match(api, /buildPreviewDescriptorFromFile/)
  assert.match(api, /createPreviewProvider\(\)/)
  assert.match(api, /affairsOperationsApi\.issueMaterialTicket\(descriptor, 'preview'\)/)
  assert.match(api, /fileSdk\.blobFrom\(ticketPath\(ticket\)\)/)
  assert.match(api, /this\.issueMaterialTicket\(version, 'download'\)/)
  assert.match(api, /fileSdk\.downloadFrom\(ticketPath\(ticket\)/)
  assert.doesNotMatch(api, /fileSdk\.preview\(/)
  assert.doesNotMatch(api, /fileSdk\.download\(fileId/)
})

test('student affairs material center embeds shared Reader for current and historical versions', () => {
  assert.match(view, /import AppDocumentViewer from '@\/components\/file\/viewer\/AppDocumentViewer\.vue'/)
  assert.match(view, /<AppDocumentViewer/)
  assert.match(view, /:descriptor="previewDescriptor"/)
  assert.match(view, /:provider="previewProvider"/)
  assert.match(view, /activePreviewVersion\.current \? '当前公共版本' : '历史不可变版本'/)
  assert.match(view, /previewProvider: affairsOperationsApi\.createPreviewProvider\(\)/)
  assert.match(view, /previewIdentity\(version\)/)
  assert.match(view, /this\.activePreviewVersion = \{ \.\.\.version \}/)
  assert.match(view, /affairsOperationsApi\.downloadMaterial\(version\)/)
  assert.match(view, /该材料尚未建立不可变 FileVersion，不能站内预览/)
  assert.doesNotMatch(view, /previewMaterial\(/)
  assert.doesNotMatch(view, /fileSdk\.preview\(/)
  assert.doesNotMatch(view, /window\.open\(/)
})
