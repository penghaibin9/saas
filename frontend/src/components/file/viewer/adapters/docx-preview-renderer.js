const MAX_SOURCE_BYTES = 25 * 1024 * 1024
const MAX_ENTRY_BYTES = 32 * 1024 * 1024
const MAX_TOTAL_UNCOMPRESSED = 80 * 1024 * 1024
const MAX_ENTRIES = 2048
const XML_MAX_BYTES = 6 * 1024 * 1024
const MAX_RENDER_NODES = 50000

class DocxPreviewError extends Error {
  constructor(code, message) {
    super(message)
    this.name = 'DocxPreviewError'
    this.code = code
    this.retryable = false
  }
}

function fail(code, message) { throw new DocxPreviewError(code, message) }
function u16(view, offset) { return view.getUint16(offset, true) }
function u32(view, offset) { return view.getUint32(offset, true) }

async function sourceBytes(source) {
  let buffer
  if (source instanceof Blob) {
    if (source.size > MAX_SOURCE_BYTES) fail('PREVIEW_TOO_LARGE', 'DOCX 超过 25MB 站内阅读上限，请下载原文查看')
    buffer = await source.arrayBuffer()
  } else if (source instanceof ArrayBuffer) {
    buffer = source
  } else if (ArrayBuffer.isView(source)) {
    buffer = source.buffer.slice(source.byteOffset, source.byteOffset + source.byteLength)
  } else {
    fail('PREVIEW_DOCX_MALFORMED', 'DOCX 预览源格式无效')
  }
  if (buffer.byteLength > MAX_SOURCE_BYTES) fail('PREVIEW_TOO_LARGE', 'DOCX 超过 25MB 站内阅读上限，请下载原文查看')
  return new Uint8Array(buffer)
}

function findEocd(bytes) {
  const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength)
  const floor = Math.max(0, bytes.byteLength - 65557)
  for (let offset = bytes.byteLength - 22; offset >= floor; offset -= 1) {
    if (offset + 4 <= bytes.byteLength && u32(view, offset) === 0x06054b50) return offset
  }
  fail('PREVIEW_DOCX_MALFORMED', 'DOCX 压缩目录无效')
}

class DocxArchive {
  constructor(bytes) {
    this.bytes = bytes
    this.view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength)
    this.entries = new Map()
    this.cache = new Map()
    this.actualDecodedTotal = 0
    this.parseDirectory()
  }

  parseDirectory() {
    const eocd = findEocd(this.bytes)
    const count = u16(this.view, eocd + 10)
    const centralOffset = u32(this.view, eocd + 16)
    if (!count || count > MAX_ENTRIES) fail('PREVIEW_DOCX_TOO_COMPLEX', 'DOCX 文件结构过于复杂，无法安全站内预览')
    let offset = centralOffset
    let declaredTotal = 0
    const decoder = new TextDecoder('utf-8')
    for (let index = 0; index < count; index += 1) {
      if (offset + 46 > this.bytes.byteLength || u32(this.view, offset) !== 0x02014b50) fail('PREVIEW_DOCX_MALFORMED', 'DOCX 中央目录损坏')
      const flags = u16(this.view, offset + 8)
      const method = u16(this.view, offset + 10)
      const compressedSize = u32(this.view, offset + 20)
      const uncompressedSize = u32(this.view, offset + 24)
      const nameLength = u16(this.view, offset + 28)
      const extraLength = u16(this.view, offset + 30)
      const commentLength = u16(this.view, offset + 32)
      const localOffset = u32(this.view, offset + 42)
      if (flags & 0x1) fail('PREVIEW_DOCX_MALFORMED', '加密 DOCX 不支持站内预览')
      if (uncompressedSize > MAX_ENTRY_BYTES) fail('PREVIEW_DOCX_TOO_COMPLEX', 'DOCX 单个内容块超过安全渲染上限')
      declaredTotal += uncompressedSize
      if (declaredTotal > MAX_TOTAL_UNCOMPRESSED) fail('PREVIEW_DOCX_TOO_COMPLEX', 'DOCX 解压后内容超过安全渲染上限')
      const nameStart = offset + 46
      const nameEnd = nameStart + nameLength
      const nextOffset = nameEnd + extraLength + commentLength
      if (nameEnd > this.bytes.byteLength || nextOffset > this.bytes.byteLength) fail('PREVIEW_DOCX_MALFORMED', 'DOCX 文件目录越界')
      const name = decoder.decode(this.bytes.subarray(nameStart, nameEnd)).replace(/\\/g, '/')
      if (!name || this.entries.has(name)) fail('PREVIEW_DOCX_MALFORMED', 'DOCX 包含重复或空文件项')
      this.entries.set(name, { method, compressedSize, uncompressedSize, localOffset })
      offset = nextOffset
    }
  }

  track(name, bytes) {
    if (bytes.byteLength > MAX_ENTRY_BYTES) fail('PREVIEW_DOCX_TOO_COMPLEX', 'DOCX 单个内容块超过安全渲染上限')
    this.actualDecodedTotal += bytes.byteLength
    if (this.actualDecodedTotal > MAX_TOTAL_UNCOMPRESSED) fail('PREVIEW_DOCX_TOO_COMPLEX', 'DOCX 实际解压内容超过安全渲染上限')
    this.cache.set(name, bytes)
    return bytes
  }

  async read(name) {
    if (this.cache.has(name)) return this.cache.get(name)
    const entry = this.entries.get(name)
    if (!entry) return null
    const offset = entry.localOffset
    if (offset + 30 > this.bytes.byteLength || u32(this.view, offset) !== 0x04034b50) fail('PREVIEW_DOCX_MALFORMED', 'DOCX 本地文件头损坏')
    const nameLength = u16(this.view, offset + 26)
    const extraLength = u16(this.view, offset + 28)
    const start = offset + 30 + nameLength + extraLength
    const end = start + entry.compressedSize
    if (start > this.bytes.byteLength || end > this.bytes.byteLength) fail('PREVIEW_DOCX_MALFORMED', 'DOCX 内容块越界')
    const compressed = this.bytes.subarray(start, end)
    if (entry.method === 0) return this.track(name, compressed.slice())
    if (entry.method !== 8) fail('PREVIEW_DOCX_MALFORMED', 'DOCX 使用了不支持的压缩方式')
    if (typeof DecompressionStream !== 'function') fail('PREVIEW_DOCX_DECOMPRESSION_UNSUPPORTED', '当前浏览器不支持安全 DOCX 解压，请升级 Chrome/Edge 后重试')
    let output
    try {
      const stream = new Blob([compressed]).stream().pipeThrough(new DecompressionStream('deflate-raw'))
      output = new Uint8Array(await new Response(stream).arrayBuffer())
    } catch {
      fail('PREVIEW_DOCX_MALFORMED', 'DOCX 内容解压失败')
    }
    if (output.byteLength > Math.max(entry.uncompressedSize * 2 + 4096, entry.uncompressedSize + 4096)) fail('PREVIEW_DOCX_TOO_COMPLEX', 'DOCX 解压内容与目录声明不一致')
    return this.track(name, output)
  }

  async text(name) {
    const bytes = await this.read(name)
    if (!bytes) return ''
    if (bytes.byteLength > XML_MAX_BYTES) fail('PREVIEW_DOCX_TOO_COMPLEX', 'DOCX XML 内容超过安全渲染上限')
    return new TextDecoder('utf-8').decode(bytes)
  }
}

function parseXml(text, label) {
  if (!text) return null
  if (/<!DOCTYPE/i.test(text)) fail('PREVIEW_DOCX_MALFORMED', `${label} 含不允许的外部文档声明`)
  const xml = new DOMParser().parseFromString(text, 'application/xml')
  if (xml.getElementsByTagName('parsererror').length) fail('PREVIEW_DOCX_MALFORMED', `${label} XML 损坏`)
  return xml
}

function attr(node, localName) { return Array.from(node?.attributes || []).find((item) => item.localName === localName)?.value || '' }
function first(node, localName) { return node?.getElementsByTagNameNS?.('*', localName)?.[0] || null }
function direct(node, localName) { return Array.from(node?.children || []).filter((item) => item.localName === localName) }
function countNode(context, amount = 1) {
  context.renderedNodes += amount
  if (context.renderedNodes > MAX_RENDER_NODES) fail('PREVIEW_DOCX_TOO_COMPLEX', 'DOCX 可视内容节点过多，已停止渲染')
}

function normalizeWordTarget(target) {
  const raw = String(target || '').replace(/\\/g, '/').replace(/^\/+/, '')
  const parts = raw.startsWith('word/') ? [] : ['word']
  for (const part of raw.split('/')) {
    if (!part || part === '.') continue
    if (part === '..') {
      if (!parts.length || (parts.length === 1 && parts[0] === 'word')) return ''
      parts.pop()
    } else parts.push(part)
  }
  const value = parts.join('/')
  return value.startsWith('word/') ? value : ''
}

function relationships(xml) {
  const map = new Map()
  if (!xml) return map
  for (const rel of Array.from(xml.getElementsByTagNameNS('*', 'Relationship'))) {
    const id = attr(rel, 'Id')
    if (!id) continue
    const external = String(attr(rel, 'TargetMode')).toLowerCase() === 'external'
    map.set(id, { external, target: external ? '' : normalizeWordTarget(attr(rel, 'Target')) })
  }
  return map
}

function paragraphStyles(xml) {
  const map = new Map()
  if (!xml) return map
  for (const style of Array.from(xml.getElementsByTagNameNS('*', 'style'))) {
    if (String(attr(style, 'type')).toLowerCase() !== 'paragraph') continue
    const id = attr(style, 'styleId')
    const name = attr(first(style, 'name'), 'val')
    if (id) map.set(id, name || id)
  }
  return map
}

function headingLevel(paragraph, styles) {
  const styleId = attr(first(first(paragraph, 'pPr'), 'pStyle'), 'val')
  const label = styles.get(styleId) || styleId
  const match = String(label || '').match(/(?:heading|标题)\s*([1-6])/i)
  return match ? Number(match[1]) : 0
}

function applyRunStyle(run, element) {
  const props = first(run, 'rPr')
  if (!props) return
  if (first(props, 'b')) element.style.fontWeight = '700'
  if (first(props, 'i')) element.style.fontStyle = 'italic'
  if (first(props, 'u')) element.style.textDecoration = 'underline'
  if (first(props, 'strike')) element.style.textDecoration = `${element.style.textDecoration} line-through`.trim()
  const color = attr(first(props, 'color'), 'val')
  if (/^[0-9a-f]{6}$/i.test(color)) element.style.color = `#${color}`
  const size = Number(attr(first(props, 'sz'), 'val')) / 2
  if (Number.isFinite(size) && size >= 7 && size <= 48) element.style.fontSize = `${size}pt`
  const vert = attr(first(props, 'vertAlign'), 'val')
  if (vert === 'superscript') element.style.verticalAlign = 'super'
  if (vert === 'subscript') element.style.verticalAlign = 'sub'
}

function imageMime(path) {
  const ext = String(path || '').split('.').pop().toLowerCase()
  return ({ png: 'image/png', jpg: 'image/jpeg', jpeg: 'image/jpeg', gif: 'image/gif', webp: 'image/webp', bmp: 'image/bmp' })[ext] || ''
}

async function appendRunContent(node, target, context) {
  for (const child of Array.from(node.childNodes || [])) {
    const name = child.localName
    if (!name) continue
    if (name === 't') target.append(document.createTextNode(child.textContent || ''))
    else if (name === 'tab') target.append(document.createTextNode('\t'))
    else if (name === 'br' || name === 'cr') target.append(document.createElement('br'))
    else if (name === 'drawing' || name === 'pict') {
      const blip = first(child, 'blip')
      const relation = context.rels.get(attr(blip, 'embed'))
      if (!relation || relation.external || !relation.target) continue
      const mime = imageMime(relation.target)
      if (!mime) continue
      const bytes = await context.archive.read(relation.target)
      if (!bytes) continue
      countNode(context)
      const url = URL.createObjectURL(new Blob([bytes], { type: mime }))
      context.objectUrls.push(url)
      const img = document.createElement('img')
      img.src = url
      img.alt = 'DOCX 内嵌图片'
      img.loading = 'lazy'
      img.className = 'docx-local-preview__image'
      target.append(img)
    } else await appendRunContent(child, target, context)
  }
}

async function renderParagraph(paragraph, context) {
  countNode(context)
  const level = headingLevel(paragraph, context.styles)
  const element = document.createElement(level ? `h${level}` : 'p')
  element.className = level ? `docx-local-preview__heading is-h${level}` : 'docx-local-preview__paragraph'
  const props = first(paragraph, 'pPr')
  const align = attr(first(props, 'jc'), 'val')
  if (['left', 'center', 'right', 'justify'].includes(align)) element.style.textAlign = align
  if (first(props, 'numPr')) {
    const marker = document.createElement('span')
    marker.className = 'docx-local-preview__list-marker'
    marker.textContent = '• '
    element.append(marker)
  }
  for (const child of Array.from(paragraph.children || [])) {
    if (child.localName === 'r') {
      countNode(context)
      const span = document.createElement('span')
      applyRunStyle(child, span)
      await appendRunContent(child, span, context)
      element.append(span)
    } else if (child.localName === 'hyperlink') {
      countNode(context)
      const span = document.createElement('span')
      span.className = 'docx-local-preview__hyperlink-text'
      await appendRunContent(child, span, context)
      element.append(span)
    }
  }
  if (!element.childNodes.length) element.append(document.createElement('br'))
  return element
}

async function renderTable(tableNode, context) {
  countNode(context)
  const table = document.createElement('table')
  table.className = 'docx-local-preview__table'
  const body = document.createElement('tbody')
  for (const rowNode of direct(tableNode, 'tr')) {
    countNode(context)
    const row = document.createElement('tr')
    for (const cellNode of direct(rowNode, 'tc')) {
      countNode(context)
      const cell = document.createElement('td')
      for (const child of Array.from(cellNode.children || [])) {
        if (child.localName === 'p') cell.append(await renderParagraph(child, context))
        else if (child.localName === 'tbl') cell.append(await renderTable(child, context))
      }
      row.append(cell)
    }
    body.append(row)
  }
  table.append(body)
  return table
}

function revokeUrls(urls) { urls.splice(0).forEach((url) => URL.revokeObjectURL(url)) }

export async function buildDocxPreview(source) {
  const bytes = await sourceBytes(source)
  const archive = new DocxArchive(bytes)
  const documentXml = parseXml(await archive.text('word/document.xml'), 'word/document.xml')
  if (!documentXml) fail('PREVIEW_DOCX_MALFORMED', 'DOCX 缺少主文档内容')
  const relsXml = parseXml(await archive.text('word/_rels/document.xml.rels'), 'document relationships')
  const stylesXml = parseXml(await archive.text('word/styles.xml'), 'word/styles.xml')
  const objectUrls = []
  const context = { archive, objectUrls, rels: relationships(relsXml), styles: paragraphStyles(stylesXml), renderedNodes: 0 }
  try {
    const shell = document.createElement('article')
    shell.className = 'docx-local-preview'
    const page = document.createElement('section')
    page.className = 'docx-local-preview__page'
    shell.append(page)
    const body = first(documentXml, 'body')
    if (!body) fail('PREVIEW_DOCX_MALFORMED', 'DOCX 缺少正文节点')
    for (const child of Array.from(body.children || [])) {
      if (child.localName === 'p') page.append(await renderParagraph(child, context))
      else if (child.localName === 'tbl') page.append(await renderTable(child, context))
    }
    return { element: shell, dispose() { revokeUrls(objectUrls) } }
  } catch (error) {
    revokeUrls(objectUrls)
    throw error
  }
}

export const DOCX_PREVIEW_LIMITS = Object.freeze({
  maxSourceBytes: MAX_SOURCE_BYTES,
  maxEntryBytes: MAX_ENTRY_BYTES,
  maxTotalUncompressed: MAX_TOTAL_UNCOMPRESSED,
  maxEntries: MAX_ENTRIES,
  maxRenderNodes: MAX_RENDER_NODES
})
