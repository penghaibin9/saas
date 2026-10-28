import assert from 'node:assert/strict'
import test from 'node:test'
import { fileURLToPath } from 'node:url'
import { build } from 'esbuild'
import { chromium } from '../../enterprise-web/node_modules/playwright/index.mjs'

function zip(entries) {
  const local = [], central = []
  let offset = 0
  for (const [name, data] of entries) {
    const n = Buffer.from(name), b = Buffer.from(data)
    const h = Buffer.alloc(30); h.writeUInt32LE(0x04034b50); h.writeUInt32LE(b.length, 18); h.writeUInt32LE(b.length, 22); h.writeUInt16LE(n.length, 26)
    const c = Buffer.alloc(46); c.writeUInt32LE(0x02014b50); c.writeUInt32LE(b.length, 20); c.writeUInt32LE(b.length, 24); c.writeUInt16LE(n.length, 28); c.writeUInt32LE(offset, 42)
    local.push(h, n, b); central.push(c, n); offset += h.length + n.length + b.length
  }
  const directory = Buffer.concat(central), end = Buffer.alloc(22)
  end.writeUInt32LE(0x06054b50); end.writeUInt16LE(entries.length, 10); end.writeUInt32LE(directory.length, 12); end.writeUInt32LE(offset, 16)
  return Buffer.concat([...local, directory, end])
}

function docx(width, height, repetitions = 1, external = false) {
  const png = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+j2QAAAABJRU5ErkJggg==', 'base64')
  if (width !== 1 || height !== 1) { png.writeUInt32BE(width, 16); png.writeUInt32BE(height, 20) }
  return Array.from(zip([
    ['word/document.xml', `<w:document xmlns:w="urn:w" xmlns:a="urn:a" xmlns:r="urn:r"><w:body><w:p>${'<w:r><w:drawing><a:blip r:embed="rId1"/></w:drawing></w:r>'.repeat(repetitions)}</w:p></w:body></w:document>`],
    ['word/_rels/document.xml.rels', `<Relationships><Relationship Id="rId1" Target="other/image.png"${external ? ' TargetMode="External"' : ''}/></Relationships>`],
    ['word/other/image.png', png]
  ]))
}

test('actual DOCX renderer checks every image before browser decode and recycles URLs', async () => {
  const bundle = await build({ entryPoints: [fileURLToPath(new URL('../src/components/file/viewer/adapters/docx-preview-renderer.js', import.meta.url))], bundle: true, write: false, format: 'iife', globalName: 'preview' })
  const browser = await chromium.launch({ headless: true })
  try {
    const page = await browser.newPage()
    await page.setContent('<main></main>')
    await page.addScriptTag({ content: bundle.outputFiles[0].text })
    const render = async (bytes) => page.evaluate(async (input) => {
      let created = 0, revoked = 0
      const create = URL.createObjectURL, revoke = URL.revokeObjectURL
      // Count the dangerous boundary without decoding hostile image bytes in the test.
      URL.createObjectURL = () => { created += 1; return 'blob:security-test' }
      URL.revokeObjectURL = () => { revoked += 1 }
      try {
        const result = await preview.buildDocxPreview(new Uint8Array(input))
        const images = result.element.querySelectorAll('img').length
        result.dispose()
        return { images, created, revoked }
      } catch (error) { return { code: error.code, message: error.message, created, revoked } }
      finally { URL.createObjectURL = create; URL.revokeObjectURL = revoke }
    }, bytes)
    assert.deepEqual(await render(docx(1, 1)), { images: 1, created: 1, revoked: 1 })
    const oversized = await render(docx(5000, 5000))
    assert.equal(oversized.code, 'PREVIEW_DOCX_TOO_COMPLEX'); assert.equal(oversized.created, 0)
    const cumulative = await render(docx(4000, 4000, 3))
    assert.equal(cumulative.code, 'PREVIEW_DOCX_TOO_COMPLEX'); assert.equal(cumulative.created, 2); assert.equal(cumulative.revoked, 2)
    assert.match(cumulative.message, /累计/)
    assert.deepEqual(await render(docx(5000, 5000, 1, true)), { images: 0, created: 0, revoked: 0 })
    // The legal image also passes the real browser image URL/decode path.
    const normal = await page.evaluate(async (input) => {
      const result = await preview.buildDocxPreview(new Uint8Array(input))
      document.querySelector('main').replaceChildren(result.element)
      const img = result.element.querySelector('img'); img.loading = 'eager'; await img.decode()
      const size = [img.naturalWidth, img.naturalHeight]; result.dispose(); return size
    }, docx(1, 1))
    assert.deepEqual(normal, [1, 1])
  } finally { await browser.close() }
})
