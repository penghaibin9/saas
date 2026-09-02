import { execFileSync } from 'node:child_process'
import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'

const root = resolve(dirname(fileURLToPath(import.meta.url)), '../..')
const git = (...args) => execFileSync('git', args, { cwd: root, encoding: 'utf8' }).trim()
const navPlanUrl = pathToFileURL(resolve(root, 'frontend/src/config/navPlan.js')).href
const { navPlanStats } = await import(navPlanUrl)

const groups = navPlanStats()

const hygienePath = resolve(root, 'artifacts/release-seals/repo-hygiene.json')
const verificationPath = resolve(root, 'artifacts/release-seals/main-candidate.json')
let repositoryHygiene = 'pending'
if (existsSync(hygienePath)) {
  try {
    repositoryHygiene = JSON.parse(readFileSync(hygienePath, 'utf8')).passed ? 'passed' : 'failed'
  } catch {
    repositoryHygiene = 'failed'
  }
}

const defaultReleaseGates = {
  repositoryHygiene,
  mysqlMigrations: 'pending',
  backendMatrix: 'pending',
  frontendApps: 'pending',
  browserJourneys: 'pending',
  securityAndDependencies: 'pending',
  backupRestore: 'pending',
  capacitySmoke: 'pending'
}

let verification = null
let releaseGates = defaultReleaseGates
if (existsSync(verificationPath)) {
  try {
    verification = JSON.parse(readFileSync(verificationPath, 'utf8'))
    releaseGates = { ...defaultReleaseGates, ...(verification.releaseGates || {}) }
  } catch {
    verification = { status: 'invalid', path: 'artifacts/release-seals/main-candidate.json' }
  }
}

const deliverable = Object.values(releaseGates).every((value) => value === 'passed')

let originMainCommit = null
let containsOriginMain = false
try {
  originMainCommit = git('rev-parse', 'origin/main')
  execFileSync('git', ['merge-base', '--is-ancestor', 'origin/main', 'HEAD'], { cwd: root })
  containsOriginMain = true
} catch {}

const registeredWorktrees = git('worktree', 'list', '--porcelain')
  .split('\n')
  .filter((line) => line.startsWith('worktree '))
  .map((line) => line.slice('worktree '.length))
const currentWorktree = git('rev-parse', '--show-toplevel').replaceAll('\\', '/')
const nonMainWorktrees = registeredWorktrees.filter((path) => path.replaceAll('\\', '/') !== currentWorktree)

const status = {
  schemaVersion: 1,
  baselineCommit: git('rev-parse', 'HEAD'),
  branch: git('branch', '--show-current'),
  generatedAt: git('show', '-s', '--format=%cI', 'HEAD'),
  deliveryStatus: deliverable ? 'deliverable' : 'integration_candidate',
  statusSemantics: {
    implemented: '代码能力存在，不代表已通过交付门禁',
    verified: '已在 baselineCommit 上通过对应自动化门禁',
    deliverable: '所有 releaseGates 通过后才可设为 true'
  },
  sourceConvergence: {
    originMainCommit,
    containsOriginMain,
    registeredWorktrees,
    nonMainWorktrees,
    pendingIntegratedBranches: []
  },
  navigation: groups,
  verification,
  releaseGates,
  deliverable
}

const output = resolve(root, 'docs/00-项目入口与总控/project-status.json')
mkdirSync(dirname(output), { recursive: true })
writeFileSync(output, `${JSON.stringify(status, null, 2)}\n`, 'utf8')
console.log(`wrote ${output}`)
