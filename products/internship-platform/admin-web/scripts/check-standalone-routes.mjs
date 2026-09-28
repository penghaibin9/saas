import fs from 'node:fs'

const routes = fs.readFileSync(new URL('../src/modules/internship/routes.js', import.meta.url), 'utf8')
const nav = fs.readFileSync(new URL('../src/config/navPlan.js', import.meta.url), 'utf8')
const required = [
  "path: '/admin/internship'",
  "path: 'batches'",
  "path: 'students'",
  "path: 'enterprises'",
  "path: 'positions'",
  "path: 'attendance'",
  "path: 'reports'",
  "path: 'archive'",
  "path: 'stats'"
]
for (const token of required) {
  if (!routes.includes(token)) throw new Error(`standalone route missing: ${token}`)
}

const forbidden = [
  '/admin/employment',
  '@/modules/academicAffairs',
  '@/modules/studentAffairs',
  '@/modules/graduation',
  '@/modules/orientation',
  '@/modules/platform'
]
for (const token of forbidden) {
  if (nav.includes(token)) throw new Error(`forbidden cross-domain navigation found: ${token}`)
}

console.log('Standalone admin route surface: OK')
