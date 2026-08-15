import fs from 'node:fs'
import process from 'node:process'

const [, , reportPath, appName, waiverPath] = process.argv
if (!reportPath || !appName || !waiverPath) {
  console.error('usage: node check-npm-production-audit.mjs <audit.json> <app> <waivers.json>')
  process.exit(2)
}

const report = JSON.parse(fs.readFileSync(reportPath, 'utf8'))
const policy = JSON.parse(fs.readFileSync(waiverPath, 'utf8'))
const waivers = Array.isArray(policy.waivers) ? policy.waivers : []
const now = Date.now()

function activeWaiver(pkg, severity) {
  return waivers.find((row) => {
    if (!row || row.app !== appName || row.package !== pkg) return false
    if (!['high', 'critical'].includes(String(row.severity || '').toLowerCase())) return false
    if (String(row.severity).toLowerCase() !== severity) return false
    if (!row.reason || String(row.reason).trim().length < 12) return false
    const expires = Date.parse(row.expires || '')
    return Number.isFinite(expires) && expires >= now
  })
}

const vulnerabilities = Object.entries(report.vulnerabilities || {})
  .map(([pkg, value]) => ({ pkg, severity: String(value?.severity || '').toLowerCase(), value }))
  .filter((row) => ['high', 'critical'].includes(row.severity))

const blocked = []
const waived = []
for (const row of vulnerabilities) {
  const waiver = activeWaiver(row.pkg, row.severity)
  if (waiver) waived.push({ ...row, waiver })
  else blocked.push(row)
}

const metadata = report.metadata?.vulnerabilities || {}
console.log(`[${appName}] production audit totals: high=${metadata.high || 0}, critical=${metadata.critical || 0}`)
for (const row of waived) {
  console.log(`[${appName}] WAIVED ${row.severity} ${row.pkg} until ${row.waiver.expires}: ${row.waiver.reason}`)
}
if (blocked.length) {
  for (const row of blocked) {
    const via = Array.isArray(row.value?.via) ? row.value.via : []
    const sources = via
      .map((item) => typeof item === 'object' ? (item.source || item.title || item.name) : item)
      .filter(Boolean)
      .join(', ')
    console.error(`[${appName}] BLOCKED ${row.severity} ${row.pkg}${sources ? ` (${sources})` : ''}`)
  }
  console.error(`[${appName}] production runtime dependencies contain unwaived high/critical vulnerabilities`)
  process.exit(1)
}
console.log(`[${appName}] production runtime dependency gate passed`)
