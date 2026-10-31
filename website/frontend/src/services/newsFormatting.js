export function newsPictureTokens(body) {
  const entries = []
  const seen = new Set()
  for (const match of body.matchAll(/^!\[([^\]\n]*)\]\((assets\/[^\s)]+)\)[ \t\r]*$/gm)) {
    if (seen.has(match[0])) continue
    seen.add(match[0])
    let number = entries.length + 1
    let token = `【配图${number}：${match[1] || '未填写说明'}】`
    while (body.includes(token) || entries.some(entry => entry.token === token)) token = `【配图${++number}：${match[1] || '未填写说明'}】`
    entries.push({ raw: match[0], token })
  }
  return entries
}

export function pictureText(body, entries, restore = false) {
  for (const entry of entries) body = body.replaceAll(restore ? entry.token : entry.raw, restore ? entry.raw : entry.token)
  return body
}

export function formatNewsSelection(text, start, end, kind) {
  const prefixes = { heading: '# ', list: '- ', quote: '> ' }
  start = Math.max(0, Math.min(text.length, start))
  end = Math.max(start, Math.min(text.length, end))
  const pictures = [...text.matchAll(/^[ \t]*!\[[^\]\n]*\]\([^\s)]+\)[ \t\r]*$/gm), ...text.matchAll(/^【配图\d+：[^\n]*】$/gm)]
  if (kind === 'bold' && pictures.some(image => start < image.index + image[0].length && end > image.index)) throw new Error('配图请在文章工作区管理，格式工具只用于文字。')
  if (kind !== 'bold') {
    if (!prefixes[kind]) throw new Error('不支持的正文格式')
    const boundary = text.indexOf('\n', end > start && text[end - 1] === '\n' ? end - 1 : end)
    start = start === 0 ? 0 : text.lastIndexOf('\n', start - 1) + 1
    end = boundary === -1 ? text.length : boundary
  }
  const selected = text.slice(start, end) || ({ heading: '小标题', list: '列表内容', quote: '引用内容', bold: '重点内容' }[kind])
  if (!selected) throw new Error('不支持的正文格式')
  const lines = selected.split('\n')
  const prefix = prefixes[kind]
  const pictureLine = line => /^!\[[^\]]*\]\([^\s)]+\)$/.test(line.trim()) || /^【配图\d+：[^\n]*】$/.test(line.trim())
  const remove = kind === 'bold' ? lines.every(line => !line || /^\*\*.+\*\*$/.test(line)) : lines.every(line => !line || pictureLine(line) || line.startsWith(prefix))
  const formatted = lines.map(line => !line || pictureLine(line) ? line : kind === 'bold' ? remove ? line.slice(2, -2) : `**${line}**` : remove ? line.slice(prefix.length) : prefix + line).join('\n')
  return { text: text.slice(0, start) + formatted + text.slice(end), start, end: start + formatted.length }
}
