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
let repositoryHygiene = 'pending'
if (existsSync(hygienePath)) {
  try {
    repositoryHygiene = JSON.parse(readFileSync(hygienePath, 'utf8')).passed ? 'passed' : 'failed'
  } catch {
    repositoryHygiene = 'failed'
  }
}

const integratedBranches = [
  'codex/control-plane-iam-menu-v1',
  'codex/academic-main-chain-data-closure-20260830',
  'codex/academic-v81-experience',
  'codex/student-affairs-delight-20260830'
].map((branch) => {
  let integrated = false
  try {
    execFileSync('git', ['merge-base', '--is-ancestor', branch, 'HEAD'], { cwd: root })
    integrated = true
  } catch {}
  return { branch, integrated }
})

const status = {
  schemaVersion: 1,
  baselineCommit: git('rev-parse', 'HEAD'),
  branch: git('branch', '--show-current'),
  generatedAt: git('show', '-s', '--format=%cI', 'HEAD'),
  deliveryStatus: 'integration_candidate',
  statusSemantics: {
    implemented: '代码能力存在，不代表已通过交付门禁',
    verified: '已在 baselineCommit 上通过对应自动化门禁',
    deliverable: '所有 releaseGates 通过后才可设为 true'
  },
  integratedBranches,
  navigation: groups,
  releaseGates: {
    repositoryHygiene,
    mysqlMigrations: 'pending',
    backendMatrix: 'pending',
    frontendApps: 'pending',
    browserJourneys: 'pending',
    securityAndDependencies: 'pending',
    backupRestore: 'pending',
    capacitySmoke: 'pending'
  },
  deliverable: false
}

const output = resolve(root, 'docs/00-项目入口与总控/project-status.json')
mkdirSync(dirname(output), { recursive: true })
writeFileSync(output, `${JSON.stringify(status, null, 2)}\n`, 'utf8')
console.log(`wrote ${output}`)
