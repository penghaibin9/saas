import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import test from 'node:test'
import { buildPreviewDescriptorFromFile } from '../src/components/file/viewer/viewer-contract.js'

const root = path.resolve(new URL('..', import.meta.url).pathname)
const read = (relative) => fs.readFileSync(path.join(root, relative), 'utf8')

const viewer = read('src/components/file/viewer/AppDocumentViewer.vue')
const renderer = read('src/components/file/viewer/adapters/docx-preview-renderer.js')
const adapter = read('src/components/file/viewer/adapters/DocxViewerAdapter.vue')
const session = read('src/components/file/viewer/usePreviewSession.js')

test('W6 PreviewDescriptor recognizes DOCX without widening other Office formats', () => {
  const docx = buildPreviewDescriptorFromFile({
    fileId: 9,
    fileVersionId: 42,
    sourceSha256: 'sha-docx',
    fileName: '毕业设计说明书.docx',
    mimeType: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    allowedActions: ['preview']
  })
  assert.equal(docx.previewKind, 'DOCX')
  assert.equal(docx.preview.kind, 'DOCX')
  assert.equal(buildPreviewDescriptorFromFile({ fileName: '成绩表.xlsx', allowedActions: ['preview'] }).previewKind, 'UNSUPPORTED')
  assert.equal(buildPreviewDescriptorFromFile({ fileName: '答辩.pptx', allowedActions: ['preview'] }).previewKind, 'UNSUPPORTED')
})

test('W6 PC DOCX renderer is local, bounded, read-only and never opens a public Office URL', () => {
  assert.match(viewer, /DocxViewerAdapter/)
  assert.match(viewer, /previewKind === 'DOCX'/)
  assert.match(renderer, /DecompressionStream\('deflate-raw'\)/)
  assert.match(renderer, /MAX_SOURCE_BYTES = 25 \* 1024 \* 1024/)
  assert.match(renderer, /MAX_TOTAL_UNCOMPRESSED = 80 \* 1024 \* 1024/)
  assert.match(renderer, /DOMParser/)
  assert.match(renderer, /TargetMode/)
  assert.match(renderer, /relation\.external/)
  assert.doesNotMatch(renderer, /innerHTML\s*=/)
  assert.doesNotMatch(renderer, /window\.open|officeapps\.live|docs\.google|fetch\(/i)
  assert.match(adapter, /activeRender/)
  assert.match(adapter, /result\.dispose\(\)/)
})

test('W6 DOCX keeps annotation PDF-first and fails large documents before byte fetch', () => {
  assert.match(session, /descriptor\.previewKind === PREVIEW_KIND\.DOCX/)
  assert.match(session, /DOCX_PREVIEW_MAX_SOURCE_BYTES/)
  assert.match(session, /PREVIEW_TOO_LARGE/)
  const combined = viewer + renderer + adapter
  assert.doesNotMatch(combined, /annotation|批注|comment-layer|saveComment/i)
})
