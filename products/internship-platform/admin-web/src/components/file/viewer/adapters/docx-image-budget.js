import {
  DOCX_PREVIEW_MAX_IMAGE_PIXELS,
  DOCX_PREVIEW_MAX_SOURCE_BYTES,
  DOCX_PREVIEW_MAX_TOTAL_IMAGE_PIXELS
} from '../viewer-contract'
import { detectImageDimensions } from './image-dimensions'

const MAX_IMAGE_BYTES = 16 * 1024 * 1024
const MAX_MEDIA_ENTRIES = 128
const SUPPORTED_IMAGE_EXT = new Set(['png', 'jpg', 'jpeg', 'gif', 'webp', 'bmp'])

function fail(code, message) {
  const error = new Error(message)
  error.name = 'DocxPreviewError'
  error.code = code
  error.retryable = false
  throw error
}

function u16(view, offset) { return view.getUint16(offset, true) }
function u32(view, offset) { return view.getUint32(offset, true) }

async function sourceBytes(source) {
  let bytes
  if (source instanceof Blob) {
    if (source.size > DOCX_PREVIEW_MAX_SOURCE_BYTES) fail('PREVIEW_TOO_LARGE', 'DOCX 超过 25MB 站内阅读上限，请下载原文查看')
    bytes = new Uint8Array(await source.arrayBuffer())
  } else if (source instanceof ArrayBuffer) {
    bytes = new Uint8Array(source)
  } else if (ArrayBuffer.isView(source)) {
    bytes = new Uint8Array(source.buffer, source.byteOffset, source.byteLength)
  } else {
    fail('PREVIEW_DOCX_MALFORMED', 'DOCX 预览源格式无效')
  }
  if (bytes.byteLength > DOCX_PREVIEW_MAX_SOURCE_BYTES) fail('PREVIEW_TOO_LARGE', 'DOCX 超过 25MB 站内阅读上限，请下载原文查看')
  return bytes
}

function findEocd(bytes, view) {
  const floor = Math.max(0, bytes.byteLength - 65557)
  for (let offset = bytes.byteLength - 22; offset >= floor; offset -= 1) {
    if (offset + 4 <= bytes.byteLength && u32(view, offset) === 0x06054b50) return offset
  }
  fail('PREVIEW_DOCX_MALFORMED', 'DOCX 压缩目录无效')
}

function imageExtension(name) {
  return String(name || '').split('.').pop().toLowerCase()
}

function mediaEntries(bytes) {
  const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength)
  const eocd = findEocd(bytes, view)
  const count = u16(view, eocd + 10)
  const centralOffset = u32(view, eocd + 16)
  if (!count || count > 2048 || centralOffset >= bytes.byteLength) fail('PREVIEW_DOCX_TOO_COMPLEX', 'DOCX 文件结构过于复杂，无法安全站内预览')
  const decoder = new TextDecoder('utf-8')
  const seen = new Set()
  const media = []
  let offset = centralOffset
  for (let index = 0; index < count; index += 1) {
    if (offset + 46 > bytes.byteLength || u32(view, offset) !== 0x02014b50) fail('PREVIEW_DOCX_MALFORMED', 'DOCX 中央目录损坏')
    const flags = u16(view, offset + 8)
    const method = u16(view, offset + 10)
    const compressedSize = u32(view, offset + 20)
    const uncompressedSize = u32(view, offset + 24)
    const nameLength = u16(view, offset + 28)
    const extraLength = u16(view, offset + 30)
    const commentLength = u16(view, offset + 32)
    const localOffset = u32(view, offset + 42)
    const nameStart = offset + 46
    const nameEnd = nameStart + nameLength
    const nextOffset = nameEnd + extraLength + commentLength
    if (nameEnd > bytes.byteLength || nextOffset > bytes.byteLength) fail('PREVIEW_DOCX_MALFORMED', 'DOCX 文件目录越界')
    const name = decoder.decode(bytes.subarray(nameStart, nameEnd)).replace(/\\/g, '/')
    if (!name || seen.has(name)) fail('PREVIEW_DOCX_MALFORMED', 'DOCX 包含重复或空文件项')
    seen.add(name)
    const lowerName = name.toLowerCase()
    if (lowerName.startsWith('word/media/') && SUPPORTED_IMAGE_EXT.has(imageExtension(lowerName))) {
      if (flags & 0x1) fail('PREVIEW_DOCX_MALFORMED', '加密 DOCX 不支持站内预览')
      if (method !== 0 && method !== 8) fail('PREVIEW_DOCX_MALFORMED', 'DOCX 图片使用了不支持的压缩方式')
      if (uncompressedSize > MAX_IMAGE_BYTES) fail('PREVIEW_DOCX_TOO_COMPLEX', 'DOCX 单张内嵌图片超过安全字节上限')
      media.push({ name, method, compressedSize, uncompressedSize, localOffset })
      if (media.length > MAX_MEDIA_ENTRIES) fail('PREVIEW_DOCX_TOO_COMPLEX', 'DOCX 内嵌图片数量过多，已停止预览')
    }
    offset = nextOffset
  }
  return { view, media }
}

async function inflateBounded(compressed, maxBytes) {
  if (typeof DecompressionStream !== 'function') fail('PREVIEW_DOCX_DECOMPRESSION_UNSUPPORTED', '当前浏览器不支持安全 DOCX 解压，请升级 Chrome/Edge 后重试')
  const reader = new Blob([compressed]).stream().pipeThrough(new DecompressionStream('deflate-raw')).getReader()
  const chunks = []
  let total = 0
  try {
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      if (!value?.byteLength) continue
      total += value.byteLength
      if (total > maxBytes) {
        await reader.cancel('DOCX embedded image exceeds preview byte budget').catch(() => {})
        fail('PREVIEW_DOCX_TOO_COMPLEX', 'DOCX 单张内嵌图片超过安全字节上限')
      }
      chunks.push(value)
    }
  } catch (error) {
    if (error?.code) throw error
    fail('PREVIEW_DOCX_MALFORMED', 'DOCX 内嵌图片解压失败')
  } finally {
    try { reader.releaseLock() } catch { /* stream already closed */ }
  }
  const out = new Uint8Array(total)
  let offset = 0
  for (const chunk of chunks) {
    out.set(chunk, offset)
    offset += chunk.byteLength
  }
  return out
}

async function readEntry(bytes, view, entry) {
  const offset = entry.localOffset
  if (offset + 30 > bytes.byteLength || u32(view, offset) !== 0x04034b50) fail('PREVIEW_DOCX_MALFORMED', 'DOCX 图片本地文件头损坏')
  const nameLength = u16(view, offset + 26)
  const extraLength = u16(view, offset + 28)
  const start = offset + 30 + nameLength + extraLength
  const end = start + entry.compressedSize
  if (start > bytes.byteLength || end > bytes.byteLength) fail('PREVIEW_DOCX_MALFORMED', 'DOCX 图片内容块越界')
  const compressed = bytes.subarray(start, end)
  if (entry.method === 0) {
    if (compressed.byteLength > MAX_IMAGE_BYTES) fail('PREVIEW_DOCX_TOO_COMPLEX', 'DOCX 单张内嵌图片超过安全字节上限')
    return compressed
  }
  return inflateBounded(compressed, Math.min(MAX_IMAGE_BYTES, Math.max(entry.uncompressedSize + 4096, entry.uncompressedSize * 2 + 4096)))
}

export async function validateDocxImageBudget(source) {
  const bytes = await sourceBytes(source)
  const { view, media } = mediaEntries(bytes)
  let totalPixels = 0
  for (const entry of media) {
    const image = await readEntry(bytes, view, entry)
    const dimensions = detectImageDimensions(image)
    if (!dimensions) fail('PREVIEW_DOCX_MALFORMED', `DOCX 内嵌图片尺寸无法安全解析：${entry.name}`)
    if (dimensions.pixels > DOCX_PREVIEW_MAX_IMAGE_PIXELS) {
      fail('PREVIEW_DOCX_TOO_COMPLEX', 'DOCX 单张内嵌图片解码像素超过安全上限')
    }
    totalPixels += dimensions.pixels
    if (totalPixels > DOCX_PREVIEW_MAX_TOTAL_IMAGE_PIXELS) {
      fail('PREVIEW_DOCX_TOO_COMPLEX', 'DOCX 内嵌图片累计解码像素超过安全上限')
    }
  }
  return { imageCount: media.length, totalPixels }
}
