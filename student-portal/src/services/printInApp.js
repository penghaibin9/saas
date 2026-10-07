/**
 * Renders a short-lived printable document inside the current portal page.
 * The browser may still show its normal print sheet, but no new window/tab is
 * opened and the caller keeps one document lifecycle to clean up.
 */
export function createInAppPrintFrame(title = '打印文档') {
  const frame = document.createElement('iframe')
  frame.title = title
  frame.setAttribute('aria-hidden', 'true')
  Object.assign(frame.style, {
    position: 'fixed', width: '1px', height: '1px', right: '0', bottom: '0',
    border: '0', opacity: '0', pointerEvents: 'none'
  })
  document.body.appendChild(frame)
  const doc = frame.contentDocument
  const view = frame.contentWindow
  if (!doc || !view) {
    frame.remove()
    throw new Error('当前浏览器无法创建系统内打印文档')
  }
  doc.open()
  doc.write('<!doctype html><html><head></head><body></body></html>')
  doc.close()
  let closed = false
  let cleanupTimer = null
  const close = () => {
    if (closed) return
    closed = true
    if (cleanupTimer) clearTimeout(cleanupTimer)
    frame.remove()
  }
  view.addEventListener('afterprint', close, { once: true })
  return {
    document: doc,
    get closed() { return closed || !frame.isConnected },
    close,
    focus() { view.focus() },
    print() {
      view.focus()
      view.print()
      cleanupTimer = setTimeout(close, 60_000)
    }
  }
}
