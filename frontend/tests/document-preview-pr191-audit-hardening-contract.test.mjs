import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import test from 'node:test'
import {
  IMAGE_PREVIEW_MAX_PIXELS,
  IMAGE_PREVIEW_MAX_SOURCE_BYTES,
  PDF_PREVIEW_MAX_CANVAS_PIXELS,
  PDF_PREVIEW_MAX_PAGES,
  PDF_PREVIEW_MAX_SOURCE_BYTES
} from '../src/components/file/viewer/viewer-contract.js'

const root = path.resolve(new URL('..', import.meta.url).pathname)
const read = (relative) => fs.readFileSync(path.join(root, relative), 'utf8')

test('PR191 hostile PDF and image resources are bounded before browser decode', () => {
  const pdf = read('src/components/file/viewer/adapters/PdfViewerAdapter.vue')
  const image = read('src/components/file/viewer/adapters/ImageViewerAdapter.vue')
  const dimensions = read('src/components/file/viewer/adapters/image-dimensions.js')
  const session = read('src/components/file/viewer/usePreviewSession.js')

  assert.equal(PDF_PREVIEW_MAX_SOURCE_BYTES, 50 * 1024 * 1024)
  assert.equal(PDF_PREVIEW_MAX_PAGES, 500)
  assert.equal(PDF_PREVIEW_MAX_CANVAS_PIXELS, 12_000_000)
  assert.equal(IMAGE_PREVIEW_MAX_SOURCE_BYTES, 20 * 1024 * 1024)
  assert.equal(IMAGE_PREVIEW_MAX_PIXELS, 32_000_000)
  assert.match(pdf, /doc\.numPages > PDF_PREVIEW_MAX_PAGES/)
  assert.match(pdf, /pixelWidth \* pixelHeight > PDF_PREVIEW_MAX_CANVAS_PIXELS/)
  assert.match(pdf, /PDF_PREVIEW_MAX_CANVAS_DIMENSION/)
  assert.match(image, /detectImageDimensions/)
  assert.match(image, /dimensions\.pixels > IMAGE_PREVIEW_MAX_PIXELS/)
  assert.doesNotMatch(image + dimensions, /createImageBitmap\(|new Image\(/)
  assert.match(session, /previewSourceByteLimit\(descriptor\)/)
  assert.match(session, /sourceByteLength\(bytes\) > sourceLimit/)
})

test('PR191 preview AbortSignal reaches actual byte stream and byte budget cancels transport', () => {
  const source = read('src/modules/graduation/api/graduation-material-center.api.js')
  assert.match(source, /fetch\(`\$\{API_BASE_URL\}\$\{API_PREFIX\}\$\{path\}`,[\s\S]*signal/)
  assert.match(source, /response\.body\.getReader\(\)/)
  assert.match(source, /reader\.cancel\('preview aborted'\)/)
  assert.match(source, /reader\.cancel\('preview byte budget exceeded'\)/)
  assert.match(source, /previewSourceByteLimit\(descriptor\)/)
  assert.doesNotMatch(source, /raceAbort\(fileSdk\.blobFrom/)
})
