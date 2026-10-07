import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'
import test from 'node:test'

test('已授权文本附件正文按原文显示，关闭可重入，拒绝下载不留下预览；图片仍释放对象地址', async () => {
  const nodes = [], keys = new Map(), calls = [], revoked = []
  const element = tag => {
    const node = { tag, style: {}, children: [], listeners: new Map(), textContent: '',
      setAttribute() {}, append(...children) { this.children.push(...children) },
      appendChild(child) { this.children.push(child) },
      addEventListener(name, fn) { this.listeners.set(name, fn) },
      remove() { this.removed = true }, focus() {} }
    Object.defineProperty(node, 'innerHTML', { set() { throw new Error('附件内容不得作为网页执行') } })
    nodes.push(node)
    return node
  }
  const document = { createElement: element, body: element('body'),
    addEventListener(name, fn) { keys.set(name, fn) }, removeEventListener(name) { keys.delete(name) } }
  const material = '本日追加确认\n固定行政班\n<script>不执行</script>'
  let blob = new Blob([material], { type: 'text/plain;charset=utf-8' }), rejectDownload = false
  const context = { document, URL: { createObjectURL() { calls.push('object-url'); return 'blob:image' }, revokeObjectURL(url) { revoked.push(url) } },
    request: async () => { calls.push('authorization'); return { fileName: '追加确认.txt' } },
    requestBlob: async () => { calls.push('authorized-download'); if (rejectDownload) throw new Error('无权读取'); return blob } }
  const source = readFileSync(new URL('../src/services/file/fileSdk.js', import.meta.url), 'utf8')
    .replace(/^import .*$/gm, '').replace(/^export default .*$/gm, '').replace(/^export /gm, '')
  vm.runInNewContext(source + '\nglobalThis.sdk = fileSdk', context)
  for (const closeWith of ['button', 'escape', 'overlay']) {
    blob = new Blob([material], { type: closeWith === 'overlay' ? 'application/octet-stream' : 'text/plain;charset=utf-8' })
    const preview = await context.sdk.preview('123')
    const content = nodes.findLast(node => node.tag === 'pre')
    assert.equal(content.textContent, material)
    assert.equal(preview.opened, true)
    assert.equal(calls.includes('object-url'), false)
    const overlay = document.body.children.at(-1)
    if (closeWith === 'button') nodes.findLast(node => node.tag === 'button').listeners.get('click')()
    if (closeWith === 'escape') keys.get('keydown')({ key: 'Escape' })
    if (closeWith === 'overlay') overlay.listeners.get('click')({ target: overlay })
    preview.close()
    assert.equal(overlay.removed, true)
    assert.equal(keys.size, 0)
  }
  rejectDownload = true
  const before = document.body.children.length
  await assert.rejects(context.sdk.preview('123'), /无权读取/)
  assert.equal(document.body.children.length, before)
  rejectDownload = false
  blob = new Blob(['image'], { type: 'image/png' })
  const image = await context.sdk.previewFrom('/authorized/image')
  assert.equal(nodes.findLast(node => node.tag === 'iframe').src, 'blob:image')
  image.close(); image.close()
  assert.deepEqual(revoked, ['blob:image'])
  assert.equal(calls[0], 'authorization')
  assert.equal(calls[1], 'authorized-download')
})
