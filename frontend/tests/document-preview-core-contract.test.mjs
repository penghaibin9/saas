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
  assert.match(source, /pdf\.worker\.min\.mjs\?url/)
  assert.match(source, /IntersectionObserver/)
  assert.match(source, /rootMargin:\s*'900px 0px'/)
  assert.match(source, /pageNo - 2/)
  assert.match(source, /pageNo \+ 2/)
  assert.match(source, /task\.cancel\(\)/)
  assert.match(source, /doc\.destroy\(\)/)
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

test('W2 workspace does not own ticket or file transport', () => {
  const source = read('src/modules/graduation/components/GraduationDocumentReviewWorkspace.vue')
  assert.doesNotMatch(source, /issueMaterialTicket|fileSdk|material-center\/files/)
  assert.match(source, /AppDocumentViewer/)
  assert.match(source, /FileEvidencePanel/)
})
