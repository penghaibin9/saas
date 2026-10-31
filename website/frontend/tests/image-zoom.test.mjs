import test from 'node:test'
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'

const source = await readFile(new URL('../src/components/official-site/OfficialImageZoom.vue', import.meta.url), 'utf8')
const { default: component } = await import('data:text/javascript;base64,' + Buffer.from(source.match(/<script>([\s\S]*?)<\/script>/)[1].replace(/import sizes[^\n]+/, 'const sizes = {}')).toString('base64'))

test('image viewer fits the real image, magnifies it and restores its scroll position', () => {
  const scrolls = []
  const viewport = { clientWidth: 375, clientHeight: 620, scrollLeft: 0, scrollTop: 0, scrollTo: (...args) => scrolls.push(args) }
  const viewer = { ...component.data(), ...component.methods, open: true, $nextTick: fn => fn(), $refs: { viewport, image: { naturalWidth: 1672, naturalHeight: 941 } } }
  viewer.fitImage()
  assert.equal(viewer.fitWidth, 343)
  viewer.setZoom(2)
  assert.equal(viewer.zoom, 2)
  assert.ok(scrolls.at(-1)[0] > 0, 'the enlarged image can be panned horizontally')
  viewer.setZoom(99)
  assert.equal(viewer.zoom, 4)
  viewer.setZoom(NaN)
  assert.equal(viewer.zoom, 4)
  viewer.setZoom(0)
  assert.equal(viewer.zoom, 1)
  assert.deepEqual(scrolls.at(-1), [0, 0])
  viewer.$refs.image = { naturalWidth: 400, naturalHeight: 1600 }
  viewer.fitImage()
  assert.equal(viewer.fitWidth, 147, 'portrait images must initially fit vertically too')
})
