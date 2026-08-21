import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'

const root = path.resolve(fileURLToPath(new URL('../', import.meta.url)))
const read = (relative) => fs.readFileSync(path.join(root, relative), 'utf8')

const api = read('src/modules/internship/api/material-center.api.js')
const view = read('src/modules/internship/views/InternshipMaterialCenterView.vue')

test('W5 internship material API uses business tickets and Viewer Blob provider', () => {
  assert.match(api, /issueMaterialTicket\(fileId, action = 'preview'\)/)
  assert.match(api, /`\$\{BASE\}\/files\/\$\{encodeURIComponent\(fileId\)\}\/ticket`/)
  assert.match(api, /buildPreviewDescriptorFromFile/)
  assert.match(api, /fileVersionId: item\.fileVersionId \?\? item\.versionId/)
  assert.match(api, /sourceSha256: item\.sourceSha256 \|\| item\.sha256/)
  assert.match(api, /createPreviewProvider\(\)/)
  assert.match(api, /issueMaterialTicket\(descriptor\.fileId, 'preview'\)/)
  assert.match(api, /fileSdk\.blobFrom\(ticketPath\(ticket\)\)/)
  assert.match(api, /issueMaterialTicket\(item\.fileId, 'download'\)/)
  assert.match(api, /fileSdk\.downloadFrom\(ticketPath\(ticket\)/)
  assert.doesNotMatch(api, /fileSdk\.preview\(/)
})

test('W5 internship material center embeds the shared Reader without generic preview fallback', () => {
  assert.match(view, /import AppDocumentViewer from '@\/components\/file\/viewer\/AppDocumentViewer\.vue'/)
  assert.match(view, /<AppDocumentViewer/)
  assert.match(view, /:descriptor="previewDescriptor"/)
  assert.match(view, /:provider="previewProvider"/)
  assert.match(view, /:files="previewFiles"/)
  assert.match(view, /:active-version-id="activePreviewFile\.versionId"/)
  assert.match(view, /previewProvider: internshipMaterialCenterApi\.createPreviewProvider\(\)/)
  assert.match(view, /previewFile\(item\)/)
  assert.match(view, /this\.activePreviewFileId = String\(item\.fileId\)/)
  assert.match(view, /internshipMaterialCenterApi\.downloadMaterial\(item\)/)
  assert.match(view, /当前材料尚未通过安全门禁，不能预览/)
  assert.doesNotMatch(view, /fileSdk\.preview\(/)
  assert.doesNotMatch(view, /window\.open\(/)
})
