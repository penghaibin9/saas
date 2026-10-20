/**
 * H5 端不使用浏览器原生 confirm/prompt/action sheet。
 *
 * 业务页面仍可保留 uni.showModal / uni.showActionSheet 的跨端调用约定；
 * 在 H5 中由这里统一转换为当前应用文档内的对话层，避免远程页或浏览器级
 * 弹窗打断用户，也不会改变原生 App/小程序运行时的实现。
 */
const INSTALL_FLAG = '__schoolInAppDialogInstalled__'

function text(value) {
  return String(value == null ? '' : value)
}

function call(fn, payload) {
  if (typeof fn === 'function') fn(payload)
}

function mountOverlay(className) {
  const overlay = document.createElement('div')
  overlay.className = className
  overlay.setAttribute('role', 'presentation')
  Object.assign(overlay.style, {
    position: 'fixed', inset: '0', zIndex: '2147483000', display: 'flex',
    alignItems: 'center', justifyContent: 'center', padding: '24px',
    background: 'rgba(15, 23, 42, .46)', boxSizing: 'border-box'
  })
  document.body.appendChild(overlay)
  return overlay
}

function dialogPanel() {
  const panel = document.createElement('section')
  panel.setAttribute('role', 'dialog')
  panel.setAttribute('aria-modal', 'true')
  Object.assign(panel.style, {
    width: 'min(100%, 420px)', maxHeight: 'calc(100vh - 48px)', overflow: 'auto',
    background: '#fff', borderRadius: '16px', boxShadow: '0 24px 64px rgba(15,23,42,.25)',
    color: '#172b4d', boxSizing: 'border-box'
  })
  return panel
}

function makeText(tag, value, style) {
  const node = document.createElement(tag)
  node.textContent = text(value)
  Object.assign(node.style, style)
  return node
}

function button(label, primary) {
  const node = document.createElement('button')
  node.type = 'button'
  node.textContent = text(label)
  Object.assign(node.style, {
    minWidth: '86px', minHeight: '40px', padding: '0 16px', borderRadius: '8px',
    border: primary ? '1px solid #2563c9' : '1px solid #d8e1ef',
    background: primary ? '#2563c9' : '#fff', color: primary ? '#fff' : '#334155',
    font: 'inherit', cursor: 'pointer'
  })
  return node
}

function closeOverlay(overlay) {
  overlay.remove()
}

function showModal(options = {}) {
  const overlay = mountOverlay('school-in-app-dialog')
  const panel = dialogPanel()
  const body = document.createElement('div')
  Object.assign(body.style, { padding: '22px 22px 16px' })
  const heading = makeText('h2', options.title || '提示', { margin: '0 0 12px', fontSize: '18px', lineHeight: '1.5' })
  body.appendChild(heading)
  if (options.content) body.appendChild(makeText('p', options.content, { margin: '0', whiteSpace: 'pre-wrap', color: '#52657e', lineHeight: '1.65' }))

  let input = null
  if (options.editable) {
    input = document.createElement('textarea')
    input.value = text(options.content)
    input.placeholder = text(options.placeholderText)
    input.maxLength = Number.isFinite(options.editableMaxLength) ? options.editableMaxLength : 1000
    Object.assign(input.style, {
      display: 'block', width: '100%', minHeight: '86px', marginTop: '16px', padding: '10px',
      resize: 'vertical', boxSizing: 'border-box', borderRadius: '8px', border: '1px solid #cbd5e1',
      color: '#172b4d', font: 'inherit', lineHeight: '1.5'
    })
    body.appendChild(input)
  }

  const footer = document.createElement('footer')
  Object.assign(footer.style, { display: 'flex', justifyContent: 'flex-end', gap: '10px', padding: '0 22px 20px' })
  const finish = (confirmed) => {
    closeOverlay(overlay)
    call(options.success, { confirm: confirmed, cancel: !confirmed, content: input ? input.value : '' })
    call(options.complete, { confirm: confirmed, cancel: !confirmed, content: input ? input.value : '' })
  }
  if (options.showCancel !== false) {
    const cancel = button(options.cancelText || '取消', false)
    cancel.addEventListener('click', () => finish(false))
    footer.appendChild(cancel)
  }
  const confirm = button(options.confirmText || '确定', true)
  confirm.addEventListener('click', () => finish(true))
  footer.appendChild(confirm)
  panel.append(body, footer)
  overlay.appendChild(panel)
  overlay.addEventListener('click', (event) => { if (event.target === overlay && options.maskClosable !== false) finish(false) })
  requestAnimationFrame(() => (input || confirm).focus())
  return { close: () => closeOverlay(overlay) }
}

function showActionSheet(options = {}) {
  const overlay = mountOverlay('school-in-app-action-sheet')
  const panel = dialogPanel()
  panel.setAttribute('aria-label', text(options.title || '请选择操作'))
  const items = Array.isArray(options.itemList) ? options.itemList : []
  const heading = makeText('h2', options.title || '请选择操作', { margin: '0', padding: '20px 22px 12px', fontSize: '17px' })
  const list = document.createElement('div')
  const finish = (tapIndex) => {
    closeOverlay(overlay)
    if (tapIndex >= 0) call(options.success, { tapIndex })
    else call(options.fail, { errMsg: 'showActionSheet:fail cancel' })
    call(options.complete, tapIndex >= 0 ? { tapIndex } : { errMsg: 'showActionSheet:fail cancel' })
  }
  items.forEach((item, tapIndex) => {
    const choice = button(item, false)
    Object.assign(choice.style, { display: 'block', width: '100%', borderRadius: '0', border: '0', borderTop: '1px solid #edf2f7', textAlign: 'left' })
    choice.addEventListener('click', () => finish(tapIndex))
    list.appendChild(choice)
  })
  const cancel = button(options.cancelButtonText || '取消', false)
  Object.assign(cancel.style, { width: '100%', marginTop: '10px' })
  cancel.addEventListener('click', () => finish(-1))
  panel.append(heading, list, cancel)
  overlay.appendChild(panel)
  overlay.addEventListener('click', (event) => { if (event.target === overlay) finish(-1) })
  return { close: () => closeOverlay(overlay) }
}

export function installH5InAppDialogs() {
  // vite 的 H5/小程序构建都会经过转换插件；因此 invoker 必须先在所有运行时
  // 可用。原生微信没有 window 时，它原样返回 uni 的原生 API，绝不让一个 H5
  // 体验优化改变 mp-weixin 的业务按钮行为。
  const runtime = typeof globalThis === 'undefined' ? null : globalThis
  if (runtime && typeof runtime.__schoolInAppModalInvoker !== 'function') {
    runtime.__schoolInAppModalInvoker = (fallback) => runtime.__schoolInAppModal || fallback
  }
  if (runtime && typeof runtime.__schoolInAppActionSheetInvoker !== 'function') {
    runtime.__schoolInAppActionSheetInvoker = (fallback) => runtime.__schoolInAppActionSheet || fallback
  }
  if (typeof window === 'undefined' || typeof document === 'undefined' || window[INSTALL_FLAG]) return
  window[INSTALL_FLAG] = true
  // uni-app 会把 `uni` 编译为模块级绑定，并不总是挂在 window 上；
  // H5 Vite transform 通过 invoker 取得这两个显式全局钩子。invoker 自身以
  // 标识符开头，避免在没有分号的业务语句后被解析为上一表达式的调用。
  window.__schoolInAppModal = showModal
  window.__schoolInAppActionSheet = showActionSheet
}
