/**
 * 光标处插入文本（供 AppQuickPhrases 快捷用语插入使用，不覆盖已有内容）。
 * 插入内容若含【占位符】，插入后自动选中第一个占位符（含中括号），方便直接打字替换。
 */

const PLACEHOLDER_RE = /【[^】]*】/

export function insertAtCursor(el, currentValue, insertText) {
  const value = currentValue || ''
  const hasSelection = el && typeof el.selectionStart === 'number'
  const start = hasSelection ? el.selectionStart : value.length
  const end = hasSelection ? el.selectionEnd : value.length
  const before = value.slice(0, start)
  const after = value.slice(end)
  const next = before + insertText + after

  const placeholderMatch = PLACEHOLDER_RE.exec(insertText)
  let selStart
  let selEnd
  if (placeholderMatch) {
    selStart = before.length + placeholderMatch.index
    selEnd = selStart + placeholderMatch[0].length
  } else {
    selStart = selEnd = before.length + insertText.length
  }
  return { value: next, selStart, selEnd }
}

/** 供 textarea/input 组件调用：插入后重新聚焦并定位/选中光标 */
export function applyInsertion(el, selStart, selEnd) {
  if (!el || typeof el.focus !== 'function') return
  el.focus()
  if (typeof el.setSelectionRange === 'function') el.setSelectionRange(selStart, selEnd)
}
