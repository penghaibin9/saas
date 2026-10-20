// A QR/link school code only pre-fills an input. Authentication remains server-authoritative.
export function normalizeLoginTenantHint(value) {
  if (typeof value !== 'string') return ''
  const code = value.trim()
  return /^[A-Za-z0-9][A-Za-z0-9_-]{0,99}$/.test(code) ? code : ''
}
