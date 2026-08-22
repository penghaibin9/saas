import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import test from 'node:test'
import { buildPreviewDescriptorFromFile, previewIdentity } from '../src/components/file/viewer/viewer-contract.js'

const root = path.resolve(new URL('..', import.meta.url).pathname)
const read = (relative) => fs.readFileSync(path.join(root, relative), 'utf8')

test('W1 descriptor locks fileVersion and source SHA independently from renderer', () => {
  const pdf = buildPreviewDescriptorFromFile({ fileId: 7, versionId: 31, sha256: 'abc', fileName: 'paper.pdf', allowedActions: ['preview'] })
  assert.equal(pdf.previewKind, 'PDF')
  assert.equal(pdf.fileVersionId, 31)
  assert.equal(pdf.sourceSha256, 'abc')
  assert.equal(pdf.canDownload, false)
  assert.notEqual(previewIdentity(pdf), previewIdentity({ ...pdf, sourceSha256: 'def' }))
})

test('W1 PDF renderer is local-worker lazy rendering with cancellable resources', () => {
  const source = read('src/components/file/viewer/adapters/PdfViewerAdapter.vue')
  assert.match(source, /pdfjs-dist\/legacy\/build\/pdf\.mjs/)
  assert.match(source, /pdfjs-dist\/legacy\/build\/pdf\.worker\.min\.mjs\?url/)
  assert.doesNotMatch(source, /from 'pdfjs-dist\/build\/pdf\.mjs'/)
  assert.match(source, /IntersectionObserver/)
  assert.match(source, /root:\s*null/)
  assert.doesNotMatch(source, /root:\s*root\.value/)
  assert.match(source, /rootMargin:\s*'900px 0px'/)
  assert.match(source, /pageNo - 2/)
  assert.match(source, /pageNo \+ 2/)
  assert.match(source, /task\.cancel\(\)/)
  assert.match(source, /doc\.destroy\(\)/)
  assert.match(source, /renderReservations\.has\(pageNo\)/)
  assert.match(source, /renderReservations\.set\(pageNo, reservation\)/)
  assert.match(source, /renderReservations\.get\(pageNo\) !== reservation/)
  assert.match(source, /token === loadToken &&[\s\S]*renderReservations\.get\(pageNo\) === reservation[\s\S]*emit\('error', error\)/)
})

test('W1 PDF generation reset preserves the canonical page before observation', () => {
  const source = read('src/components/file/viewer/adapters/PdfViewerAdapter.vue')
  assert.match(source, /function resetInitialPosition\(pageNo\)/)
  assert.match(source, /viewer\.scrollTop = 0/)
  assert.match(source, /viewer\.scrollLeft = 0/)
  assert.match(source, /resetInitialPosition\(initialPage\)\s*\n\s*observePages\(\)/)
  assert.match(source, /renderPage\(initialPage\)/)
})

test('W1 preview session changes generation, aborts old work and bounds ticket refresh to one', () => {
  const source = read('src/components/file/viewer/usePreviewSession.js')
  assert.match(source, /state\.generation = generation/)
  assert.match(source, /controller\?\.abort\(\)/)
  assert.match(source, /ticketRefreshCount = 1/)
  assert.equal((source.match(/refresh:\s*true/g) || []).length, 1)
})

test('W1 Viewer is presentation-only and never owns approve/reject', () => {
  const dir = path.join(root, 'src/components/file/viewer')
  const stack = [dir]
  let combined = ''
  while (stack.length) {
    const current = stack.pop()
    for (const entry of fs.readdirSync(current, { withFileTypes: true })) {
      const full = path.join(current, entry.name)
      if (entry.isDirectory()) stack.push(full)
      else if (/\.(?:js|vue)$/.test(entry.name)) combined += fs.readFileSync(full, 'utf8')
    }
  }
  assert.doesNotMatch(combined, /submitReview|reviewProposal|reviewFinal|@approve|@reject/)
})

test('W1 legacy FilePreviewer can delegate inline rendering without owning transport', () => {
  const source = read('src/components/file/FilePreviewer.vue')
  assert.match(source, /AppDocumentViewer/)
  assert.match(source, /provider:/)
  assert.match(source, /canInlinePreview/)
  assert.match(source, /buildPreviewDescriptorFromFile/)
  assert.doesNotMatch(source, /window\.open\(|URL\.createObjectURL\(|request\('\/files/)
})

test('W2 graduation provider sends ticket action as the actual HTTP request body', () => {
  const source = read('src/modules/graduation/api/graduation-material-center.api.js')
  assert.match(source, /files\/\$\{encodeURIComponent\(fileId\)\}\/ticket[\s\S]*method:\s*'POST',\s*body:\s*\{ action \}/)
  assert.doesNotMatch(source, /files\/\$\{encodeURIComponent\(fileId\)\}\/ticket[^\n]*data:\s*\{ action \}/)
})

test('W2 preview cancellation uses a mutable AbortError instead of writing DOMException code', () => {
  const source = read('src/modules/graduation/api/graduation-material-center.api.js')
  assert.match(source, /const error = new Error\('预览已切换'\)/)
  assert.match(source, /error\.name = 'AbortError'/)
  assert.match(source, /error\.code = 'PREVIEW_ABORTED'/)
  assert.doesNotMatch(source, /new DOMException\('预览已切换', 'AbortError'\)/)
})

test('W2 workspace keeps transport outside and renderer failures inside the Viewer', () => {
  const workspace = read('src/modules/graduation/components/GraduationDocumentReviewWorkspace.vue')
  const viewer = read('src/components/file/viewer/AppDocumentViewer.vue')
  assert.doesNotMatch(workspace, /issueMaterialTicket|fileSdk|material-center\/files/)
  assert.match(workspace, /AppDocumentViewer/)
  assert.match(workspace, /FileEvidencePanel/)
  assert.doesNotMatch(workspace, /@preview-error=[^\n]*reload/)
  assert.match(viewer, /AppDocumentState[\s\S]*@retry="retry"/)
})