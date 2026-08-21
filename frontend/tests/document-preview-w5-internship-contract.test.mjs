import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'

const root = path.resolve(fileURLToPath(new URL('../', import.meta.url)))
const read = (relative) => fs.readFileSync(path.join(root, relative), 'utf8')

const api = read('src/modules/internship/api/material-center.api.js')
const center = read('src/modules/internship/views/InternshipMaterialCenterView.vue')
const student = read('src/modules/internship/views/InternshipStudentMaterialEntryView.vue')

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

for (const [label, source] of [['material center', center], ['student material page', student]]) {
  test(`W5 internship ${label} embeds the shared Reader without generic preview fallback`, () => {
    assert.match(source, /import AppDocumentViewer from '@\/components\/file\/viewer\/AppDocumentViewer\.vue'/)
    assert.match(source, /<AppDocumentViewer/)
    assert.match(source, /:descriptor="previewDescriptor"/)
    assert.match(source, /:provider="previewProvider"/)
    assert.match(source, /:files="previewFiles"/)
    assert.match(source, /:active-version-id="activePreviewFile\.versionId"/)
    assert.match(source, /previewProvider: internshipMaterialCenterApi\.createPreviewProvider\(\)/)
    assert.match(source, /this\.activePreviewFileId = String\(item\.fileId\)/)
    assert.match(source, /internshipMaterialCenterApi\.downloadMaterial\(item\)/)
    assert.match(source, /当前材料尚未通过安全门禁，不能预览/)
    assert.doesNotMatch(source, /fileSdk\.preview\(/)
    assert.doesNotMatch(source, /window\.open\(/)
  })
}
