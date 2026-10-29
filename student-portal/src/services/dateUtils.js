// Shared student-facing formatter, extracted without changing the existing leave-date rules.
export function portalDate(value, withTime = false) {
  if (!value) return '—'
  const raw = String(value).trim()
  const d = new Date(/^\d{4}-\d{2}-\d{2}$/.test(raw) ? raw + 'T00:00:00' : raw.replace(' ', 'T'))
  if (Number.isNaN(d.getTime())) return '—'
  const pad = (v) => String(v).padStart(2, '0')
  const date = d.getFullYear() + '-' + pad(d.getMonth() + 1) + '-' + pad(d.getDate())
  return withTime ? date + ' ' + pad(d.getHours()) + ':' + pad(d.getMinutes()) : date
}
