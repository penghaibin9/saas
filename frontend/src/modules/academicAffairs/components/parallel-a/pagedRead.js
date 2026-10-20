// Reads a scoped paginated endpoint to completion. It never treats a truncated first page as the full domain.
export async function readAllPages(fetchPage, options = {}) {
  const pageSize = Number(options.pageSize || 100)
  const maxPages = Number(options.maxPages || 200)
  const rows = []
  const identities = new Set()
  let expectedTotal = null

  for (let page = 1; page <= maxPages; page += 1) {
    const result = await fetchPage(page, pageSize)
    if (result?.code !== 0) return result
    const list = result.data?.list || result.data?.items || []
    const total = Number(result.data?.total)
    if (Number.isFinite(total)) expectedTotal = total
    if (!list.length) break

    let added = 0
    for (const row of list) {
      const key = String(options.identity?.(row) ?? `${page}:${rows.length}`)
      if (identities.has(key)) continue
      identities.add(key); rows.push(row); added += 1
    }
    if (!added) return { code: 'PAGINATION_STALLED', message: '分页结果重复，无法确认完整数据范围' }
    if (expectedTotal != null && rows.length >= expectedTotal) break
    if (list.length < pageSize) break
  }

  if (expectedTotal != null && rows.length < expectedTotal) {
    return { code: 'PAGINATION_INCOMPLETE', message: `分页读取不完整：应有 ${expectedTotal} 条，实际读取 ${rows.length} 条` }
  }
  return { code: 0, data: { list: rows, total: expectedTotal ?? rows.length } }
}
