import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import test from 'node:test'
import {
  buildPreviewDescriptorFromFile,
  DOCX_PREVIEW_MAX_IMAGE_PIXELS,
  DOCX_PREVIEW_MAX_TOTAL_IMAGE_PIXELS
} from '../src/components/file/viewer/viewer-contract.js'

const root = path.resolve(new URL('..', import.meta.url).pathname)
const read = (relative) => fs.readFileSync(path.join(root, relative), 'utf8')

const viewer = read('src/components/file/viewer/AppDocumentViewer.vue')
const renderer = read('src/components/file/viewer/adapters/docx-preview-renderer.js')
const adapter = read('src/components/file/viewer/adapters/DocxViewerAdapter.vue')
const imageBudget = read('src/components/file/viewer/adapters/docx-image-budget.js')
const imageDimensions = read('src/components/file/viewer/adapters/image-dimensions.js')
const session = read('src/components/file/viewer/usePreviewSession.js')

test('W6 PreviewDescriptor recognizes DOCX without widening other Office formats', () => {
  const docx = buildPreviewDescriptorFromFile({ fileId: 9, fileVersionId: 42, sourceSha256: 'sha-docx', fileName: '毕业设计说明书.docx', mimeType: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', allowedActions: ['preview'] })
  assert.equal(docx.previewKind, 'DOCX')
  assert.equal(docx.preview.kind, 'DOCX')
  assert.equal(buildPreviewDescriptorFromFile({ fileName: '成绩表.xlsx', allowedActions: ['preview'] }).previewKind, 'UNSUPPORTED')
  assert.equal(buildPreviewDescriptorFromFile({ fileName: '答辩.pptx', allowedActions: ['preview'] }).previewKind, 'UNSUPPORTED')
})

test('W6 PC DOCX renderer is local, bounded, read-only and never opens a public Office URL', () => {
  assert.match(viewer, /DocxViewerAdapter/)
  assert.match(viewer, /previewKind === 'DOCX'/)
  assert.match(renderer, /DecompressionStream\('deflate-raw'\)/)
  assert.match(renderer, /const reader = stream\.getReader\(\)/)
  assert.match(renderer, /reader\.cancel\(/)
  assert.match(renderer, /maxOutputBytes/)
  assert.match(renderer, /MAX_SOURCE_BYTES = 25 \* 1024 \* 1024/)
  assert.match(renderer, /MAX_TOTAL_UNCOMPRESSED = 80 \* 1024 \* 1024/)
  assert.match(renderer, /MAX_RENDER_NODES = 50000/)
  assert.match(renderer, /actualDecodedTotal/)
  assert.match(renderer, /this\.cache = new Map\(\)/)
  assert.match(renderer, /this\.entries\.has\(name\)/)
  assert.match(renderer, /TargetMode/)
  assert.match(renderer, /relation\.external/)
  assert.match(renderer, /if \(!mime\) continue/)
  assert.doesNotMatch(renderer, /image\/svg\+xml/)
  assert.doesNotMatch(renderer, /innerHTML\s*=/)
  assert.doesNotMatch(renderer, /window\.open|officeapps\.live|docs\.google|fetch\(/i)
  assert.match(adapter, /activeRender/)
  assert.match(adapter, /result\.dispose\(\)/)
})

test('W6 DOCX rejects decompression-safe but decode-hostile embedded images before renderer URLs', () => {
  assert.equal(DOCX_PREVIEW_MAX_IMAGE_PIXELS, 16_000_000)
  assert.equal(DOCX_PREVIEW_MAX_TOTAL_IMAGE_PIXELS, 32_000_000)
  assert.match(adapter, /await validateDocxImageBudget\(props\.source\)/)
  assert.match(imageBudget, /word\/media\//)
  assert.match(imageBudget, /MAX_MEDIA_ENTRIES = 128/)
  assert.match(imageBudget, /reader\.cancel\('DOCX embedded image exceeds preview byte budget'\)/)
  assert.match(imageBudget, /detectImageDimensions\(image\)/)
  assert.match(imageBudget, /dimensions\.pixels > DOCX_PREVIEW_MAX_IMAGE_PIXELS/)
  assert.match(imageBudget, /totalPixels > DOCX_PREVIEW_MAX_TOTAL_IMAGE_PIXELS/)
  assert.match(imageDimensions, /JPEG_SOF/)
  assert.match(imageDimensions, /VP8X/)
  assert.doesNotMatch(imageBudget + imageDimensions, /createImageBitmap\(|new Image\(/)
})

test('W6 DOCX keeps annotation PDF-first and fails large documents before byte fetch', () => {
  assert.match(session, /previewSourceByteLimit\(descriptor\)/)
  assert.match(session, /sourceByteLength\(bytes\) > sourceLimit/)
  assert.match(session, /PREVIEW_TOO_LARGE/)
  const combined = viewer + renderer + adapter
  assert.doesNotMatch(combined, /annotation|批注|comment-layer|saveComment/i)
})
