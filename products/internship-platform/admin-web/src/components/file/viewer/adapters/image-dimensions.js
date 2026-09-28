function asBytes(value) {
  if (value instanceof Uint8Array) return value
  if (value instanceof ArrayBuffer) return new Uint8Array(value)
  if (ArrayBuffer.isView(value)) return new Uint8Array(value.buffer, value.byteOffset, value.byteLength)
  return null
}

function ascii(bytes, offset, length) {
  if (offset < 0 || offset + length > bytes.byteLength) return ''
  let out = ''
  for (let i = 0; i < length; i += 1) out += String.fromCharCode(bytes[offset + i])
  return out
}

function be16(bytes, offset) {
  return (bytes[offset] << 8) | bytes[offset + 1]
}

function be32(bytes, offset) {
  return ((bytes[offset] * 0x1000000) + (bytes[offset + 1] << 16) + (bytes[offset + 2] << 8) + bytes[offset + 3]) >>> 0
}

function le16(bytes, offset) {
  return bytes[offset] | (bytes[offset + 1] << 8)
}

function le24(bytes, offset) {
  return bytes[offset] | (bytes[offset + 1] << 8) | (bytes[offset + 2] << 16)
}

function le32(bytes, offset) {
  return (bytes[offset] | (bytes[offset + 1] << 8) | (bytes[offset + 2] << 16) | (bytes[offset + 3] << 24)) >>> 0
}

function valid(width, height) {
  return Number.isFinite(width) && Number.isFinite(height) && width > 0 && height > 0
    ? { width, height, pixels: width * height }
    : null
}

function pngDimensions(bytes) {
  if (bytes.byteLength < 24) return null
  if (bytes[0] !== 0x89 || ascii(bytes, 1, 3) !== 'PNG') return null
  return valid(be32(bytes, 16), be32(bytes, 20))
}

function gifDimensions(bytes) {
  if (bytes.byteLength < 10 || !['GIF87a', 'GIF89a'].includes(ascii(bytes, 0, 6))) return null
  return valid(le16(bytes, 6), le16(bytes, 8))
}

function bmpDimensions(bytes) {
  if (bytes.byteLength < 26 || ascii(bytes, 0, 2) !== 'BM') return null
  const width = le32(bytes, 18)
  const rawHeight = le32(bytes, 22)
  const height = rawHeight > 0x7fffffff ? 0x100000000 - rawHeight : rawHeight
  return valid(width, Math.abs(height))
}

function webpDimensions(bytes) {
  if (bytes.byteLength < 30 || ascii(bytes, 0, 4) !== 'RIFF' || ascii(bytes, 8, 4) !== 'WEBP') return null
  const chunk = ascii(bytes, 12, 4)
  if (chunk === 'VP8X') return valid(le24(bytes, 24) + 1, le24(bytes, 27) + 1)
  if (chunk === 'VP8 ' && bytes.byteLength >= 30 && bytes[23] === 0x9d && bytes[24] === 0x01 && bytes[25] === 0x2a) {
    return valid(le16(bytes, 26) & 0x3fff, le16(bytes, 28) & 0x3fff)
  }
  if (chunk === 'VP8L' && bytes.byteLength >= 25 && bytes[20] === 0x2f) {
    const bits = (bytes[21] | (bytes[22] << 8) | (bytes[23] << 16) | (bytes[24] << 24)) >>> 0
    return valid((bits & 0x3fff) + 1, ((bits >>> 14) & 0x3fff) + 1)
  }
  return null
}

const JPEG_SOF = new Set([0xc0, 0xc1, 0xc2, 0xc3, 0xc5, 0xc6, 0xc7, 0xc9, 0xca, 0xcb, 0xcd, 0xce, 0xcf])

function jpegDimensions(bytes) {
  if (bytes.byteLength < 4 || bytes[0] !== 0xff || bytes[1] !== 0xd8) return null
  let offset = 2
  while (offset + 3 < bytes.byteLength) {
    while (offset < bytes.byteLength && bytes[offset] !== 0xff) offset += 1
    while (offset < bytes.byteLength && bytes[offset] === 0xff) offset += 1
    if (offset >= bytes.byteLength) break
    const marker = bytes[offset]
    offset += 1
    if (marker === 0xd9 || marker === 0xda) break
    if (marker === 0x01 || (marker >= 0xd0 && marker <= 0xd7)) continue
    if (offset + 2 > bytes.byteLength) break
    const length = be16(bytes, offset)
    if (length < 2 || offset + length > bytes.byteLength) break
    if (JPEG_SOF.has(marker) && length >= 7) {
      return valid(be16(bytes, offset + 5), be16(bytes, offset + 3))
    }
    offset += length
  }
  return null
}

export function detectImageDimensions(value) {
  const bytes = asBytes(value)
  if (!bytes || !bytes.byteLength) return null
  return pngDimensions(bytes) || jpegDimensions(bytes) || gifDimensions(bytes) || bmpDimensions(bytes) || webpDimensions(bytes)
}
