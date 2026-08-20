/**
 * V3 §4.4 LIST_FOCUS 落地工具（不依赖 @/ 别名与 uni 运行时的部分可直接 node 单测）。
 *
 * 后端把 focusMode=LIST_FOCUS 的 target 指向列表页并带上聚焦参数；页面必须真的读到它、
 * 在列表里定位到那条记录，否则用户点“去处理”后仍然要自己找——这正是 V3 深审 P0-03。
 *
 * 列表页只需要三步：
 *   1. onLoad 里 `this.focusId = readFocusId(query)`
 *   2. 数据就绪后 `this.focusMissing = !hasFocusRow(list, this.focusId, ['leaveId'])`
 *   3. `scrollToFocus('#leave-', this.focusId)`
 * 找不到对象时把 focusMissing 展示出来，不要假装已经定位到（fail-closed）。
 */

/** 从页面 query 读聚焦值；缺省参数名与 mobile_focus_contract.FOCUS_READY_PAGES 一致。 */
export function readFocusId(query, param = 'recordId') {
  const raw = query && typeof query === 'object' ? query[param] : ''
  const value = String(raw === null || raw === undefined ? '' : raw).trim()
  return value
}

/** 该聚焦值在当前列表里是否真的存在。 */
export function hasFocusRow(rows, focusId, idKeys = ['recordId']) {
  if (!focusId) return false
  if (!Array.isArray(rows) || !rows.length) return false
  const keys = Array.isArray(idKeys) ? idKeys : [idKeys]
  return rows.some((row) => keys.some((key) => String((row || {})[key] ?? '') === String(focusId)))
}

/** 该行是否就是被聚焦的对象（模板里高亮用）。 */
export function isFocusRow(row, focusId, idKeys = ['recordId']) {
  if (!focusId || !row) return false
  const keys = Array.isArray(idKeys) ? idKeys : [idKeys]
  return keys.some((key) => String(row[key] ?? '') === String(focusId))
}

/**
 * 滚动到被聚焦的行。selectorPrefix 需与模板里的 id 前缀一致，例如 '#leave-'。
 * 运行时不可用（H5/单测）时静默跳过，不抛错。
 */
export function scrollToFocus(selectorPrefix, focusId, { delay = 80 } = {}) {
  if (!focusId) return false
  const runtime = typeof uni !== 'undefined' ? uni : null
  if (!runtime || typeof runtime.pageScrollTo !== 'function') return false
  setTimeout(() => {
    try { runtime.pageScrollTo({ selector: `${selectorPrefix}${focusId}`, duration: 250 }) } catch (e) { /* 目标未渲染时忽略 */ }
  }, delay)
  return true
}
