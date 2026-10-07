const MAX_SELECTION = 100
const MIME = { pdf: 'application/pdf', xlsx: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' }
const idOf = value => String(value ?? '')

export function createPlanBulkExport({ reactive = value => value, loadPage, exportFile, download, canExport }) {
  const state = reactive({ rows: [], selected: [], page: 1, pageSize: 20, hasMore: false,
    keyword: '', searchTerm: '', loading: false, exporting: '', error: '', exportError: '', receipt: null })
  let epoch = 0, requestId = 0, disposed = false
  const current = token => !disposed && token === epoch && canExport()
  function reset() {
    epoch++; requestId++
    Object.assign(state, { rows: [], selected: [], page: 1, hasMore: false, keyword: '', searchTerm: '',
      loading: false, exporting: '', error: '', exportError: '', receipt: null })
  }
  async function load(page = state.page) {
    if (disposed || !canExport()) { reset(); return }
    const token = epoch, ticket = ++requestId
    state.loading = true; state.error = ''; state.rows = []; state.hasMore = false; state.page = page
    try {
      const res = await loadPage({ page, pageSize: state.pageSize, keyword: state.searchTerm })
      if (!current(token) || ticket !== requestId) return
      if (res?.code !== 0) throw new Error(res?.message || '计划列表加载失败')
      if (!Array.isArray(res.data?.items) || typeof res.data.hasMore !== 'boolean') throw new Error('计划列表返回格式异常')
      const rows = res.data.items
      if (rows.some(row => !/^[1-9][0-9]{0,18}$/.test(idOf(row.id)))) throw new Error('计划标识无效，请重试')
      state.rows = rows.map(row => ({ ...row, id: idOf(row.id) }))
      state.hasMore = res.data.hasMore
    } catch (error) {
      if (current(token) && ticket === requestId) state.error = error.message || '计划列表加载失败'
    } finally {
      if (token === epoch && ticket === requestId) state.loading = false
    }
  }
  const selected = id => state.selected.some(row => row.id === idOf(id))
  function toggle(row) {
    if (disposed || !canExport() || state.exporting || state.loading || state.error) return
    const id = idOf(row.id)
    if (selected(id)) state.selected = state.selected.filter(item => item.id !== id)
    else if (state.selected.length >= MAX_SELECTION) state.exportError = '单次最多选择100份计划，请先移除部分选择'
    else if (state.rows.some(item => item.id === id)) state.selected.push({ ...row, id })
    state.receipt = null
  }
  function remove(id) {
    if (!state.exporting) { state.selected = state.selected.filter(row => row.id !== idOf(id)); state.receipt = null }
  }
  function togglePage() {
    if (!state.rows.length || state.exporting || state.loading || state.error || !canExport()) return
    if (state.rows.every(row => selected(row.id))) {
      const ids = new Set(state.rows.map(row => row.id))
      state.selected = state.selected.filter(row => !ids.has(row.id))
    } else {
      const added = state.rows.filter(row => !selected(row.id))
      if (state.selected.length + added.length > MAX_SELECTION) { state.exportError = '本页加入后将超过100份，请逐项选择'; return }
      state.selected = [...state.selected, ...added.map(row => ({ ...row }))]
    }
    state.receipt = null; state.exportError = ''
  }
  async function search() {
    if (state.exporting) return
    state.searchTerm = state.keyword.trim(); await load(1)
  }
  async function exportSelected(format) {
    if (disposed || !canExport() || state.exporting || state.loading || state.error || !state.selected.length) return
    if (!Object.hasOwn(MIME, format)) return
    const token = epoch, ids = state.selected.map(row => row.id)
    state.exporting = format; state.exportError = ''; state.receipt = null
    try {
      const res = await exportFile(format, ids)
      if (!current(token)) return
      if (res?.code !== 0) throw new Error(res?.message || '导出未完成，选择已保留')
      const data = res.data
      if (!data?.contentBase64 || !data.filename || data.mediaType !== MIME[format] || data.url || data.downloadUrl) {
        throw new Error('导出文件返回异常，未触发下载；请重试')
      }
      await download(data)
      if (current(token)) state.receipt = { count: ids.length, filename: data.filename, format: format.toUpperCase() }
    } catch (error) {
      if (current(token)) state.exportError = error.message || '导出失败，选择已保留'
    } finally {
      if (token === epoch) state.exporting = ''
    }
  }
  function clear() { if (!state.exporting) { state.selected = []; state.receipt = null; state.exportError = '' } }
  function destroy() { reset(); disposed = true }
  return { state, selected, toggle, togglePage, remove, clear, search, load, reset, exportSelected, destroy }
}
