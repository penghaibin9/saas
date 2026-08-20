#!/usr/bin/env node
/**
 * V3 §S9 / 深审 P1-15：生成并校验 miniapp-v3-handoff.json。
 *
 * studentMergeSha 不是“JSON 自己所在提交”的不可实现自指，而是 handoff seal 覆盖的
 * 实现提交。最终 seal 使用专用 commit subject；校验器直接读取当前 commit object 的
 * parent SHA，因此在 actions/checkout 默认 fetch-depth=1 下也无需父提交/父树对象。
 */
import { createHash } from 'node:crypto'
import { execFileSync } from 'node:child_process'
import { existsSync, readFileSync, writeFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, resolve } from 'node:path'

const here = dirname(fileURLToPath(import.meta.url))
const MINIAPP = resolve(here, '..')
const REPO = resolve(MINIAPP, '..')
const OUTPUT = resolve(REPO, 'miniapp-v3-handoff.json')
const SEAL_SUBJECT = 'chore(miniapp-v3): seal exact-head handoff'

const sha256 = (value) => createHash('sha256').update(value).digest('hex')
const read = (path) => readFileSync(path, 'utf8')

function git(...args) {
  try {
    return execFileSync('git', args, { cwd: REPO }).toString().trim()
  } catch (error) {
    return ''
  }
}

function gitSha() {
  return git('rev-parse', 'HEAD')
}

/**
 * 当前 HEAD 若是专用 handoff seal，则从 raw commit object 读取第一父 SHA；`cat-file`
 * 只需要 HEAD 自身对象，在 shallow checkout 下也可靠。普通业务提交直接返回 HEAD，
 * 因而 seal 后任何正常代码提交都会与落盘 studentMergeSha 不一致并 fail-closed。
 * “seal commit 只能改 JSON”由生成 seal 时的 GitHub compare 独立验收，不把父树依赖塞进
 * 运行时验证器。
 */
function implementationSha() {
  const head = gitSha()
  if (!head) return ''
  const raw = git('cat-file', '-p', 'HEAD')
  if (!raw) return head
  const [headers = '', ...messageParts] = raw.split('\n\n')
  const subject = messageParts.join('\n\n').split('\n', 1)[0].trim()
  if (subject !== SEAL_SUBJECT) return head
  const parentLine = headers.split('\n').find((line) => line.startsWith('parent '))
  const parent = parentLine ? parentLine.slice('parent '.length).trim() : ''
  return parent || head
}

/** pages.json 还原成完整 URL 集合 —— 教师端据此确认路由面没有被学生端改动。 */
function routeInventory() {
  const manifest = JSON.parse(read(resolve(MINIAPP, 'src/pages.json')))
  const routes = (manifest.pages || []).map((page) => page.path)
  const packages = []
  for (const pkg of manifest.subPackages || []) {
    const root = String(pkg.root || '').replace(/\/+$/, '')
    packages.push({ root, pages: (pkg.pages || []).length })
    for (const page of pkg.pages || []) routes.push(`${root}/${page.path}`)
  }
  routes.sort()
  return { routes, packages }
}

/** 从模块源码里抽取契约版本号，避免手写版本与代码漂移。 */
function contractVersion(file, marker) {
  const source = read(resolve(MINIAPP, file))
  const match = new RegExp(`${marker}\\s*=\\s*['"]?([\\w.-]+)`).exec(source)
  return match ? match[1] : sha256(source).slice(0, 12)
}

function alembicHead() {
  const dir = resolve(REPO, 'backend/alembic/versions')
  if (!existsSync(dir)) return ''
  try {
    return execFileSync('python3', ['-c', `
import ast, os
d = ${JSON.stringify(dir)}
revs, downs = {}, {}
for f in sorted(os.listdir(d)):
    if not f.endswith('.py'): continue
    tree = ast.parse(open(os.path.join(d, f), encoding='utf-8').read())
    rev = down = None
    for node in tree.body:
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            tgt = node.targets[0] if isinstance(node, ast.Assign) else node.target
            if isinstance(tgt, ast.Name):
                try: value = ast.literal_eval(node.value)
                except Exception: continue
                if tgt.id == 'revision': rev = value
                if tgt.id == 'down_revision': down = value
    if rev: revs[rev] = f; downs[rev] = down
parents = set()
for r, p in downs.items():
    if isinstance(p, str): parents.add(p)
    elif p: parents.update(p)
heads = sorted(r for r in revs if r not in parents)
print(','.join(heads))
`], { cwd: REPO }).toString().trim()
  } catch (error) {
    return ''
  }
}

function packageReportSha() {
  const report = resolve(MINIAPP, 'dist/build/mp-weixin/miniapp-package-report.json')
  if (!existsSync(report)) return ''
  return sha256(read(report))
}

export function buildHandoff() {
  const inventory = routeInventory()
  return {
    schema: 'miniapp-v3-handoff/1',
    generatedAt: new Date().toISOString(),
    studentMergeSha: implementationSha(),
    actionSchemaVersion: contractVersion('src/services/actionRouterCore.mjs', 'ACTION_SCHEMA_VERSION'),
    routeInventoryHash: sha256(inventory.routes.join('\n')),
    routeCount: inventory.routes.length,
    subpackageHash: sha256(JSON.stringify(inventory.packages)),
    subpackages: inventory.packages,
    networkPagerVersion: contractVersion('src/utils/networkPager.js', 'NETWORK_PAGER_VERSION'),
    attachmentPickerVersion: contractVersion('src/components/MobileAttachmentPicker.vue', 'ATTACHMENT_PICKER_VERSION'),
    alembicHead: alembicHead(),
    packageReportSha: packageReportSha()
  }
}

const REQUIRED_FIELDS = [
  'studentMergeSha', 'actionSchemaVersion', 'routeInventoryHash',
  'subpackageHash', 'networkPagerVersion', 'attachmentPickerVersion', 'alembicHead',
  'packageReportSha'
]

function verify() {
  if (!existsSync(OUTPUT)) {
    console.error('[handoff] 缺少 miniapp-v3-handoff.json，先运行生成命令')
    return 1
  }
  const stored = JSON.parse(read(OUTPUT))
  const current = buildHandoff()
  const drift = []
  for (const field of REQUIRED_FIELDS) {
    if (!stored[field]) {
      drift.push(`${field} 为空：交付物不完整`)
      continue
    }
    // packageReportSha 只有 release build 后本地才可重算；有报告时必须一致。
    if (field === 'packageReportSha' && !current[field]) continue
    if (stored[field] !== current[field]) {
      drift.push(`${field} 漂移：交付=${stored[field]} 实际=${current[field]}`)
    }
  }
  if (drift.length) {
    console.error('[handoff] 共享契约已漂移，Teacher T8 不得据此接线：')
    for (const line of drift) console.error('  -', line)
    return 1
  }
  console.log(`[handoff] OK impl=${current.studentMergeSha} routes=${current.routeCount} alembicHead=${current.alembicHead}`)
  return 0
}

const isVerify = process.argv.includes('--verify')
if (isVerify) {
  process.exit(verify())
} else {
  const handoff = buildHandoff()
  writeFileSync(OUTPUT, `${JSON.stringify(handoff, null, 2)}\n`, 'utf8')
  console.log(`[handoff] 已生成 ${OUTPUT}`)
  console.log(`  implementationSha=${handoff.studentMergeSha}`)
  console.log(`  routes=${handoff.routeCount} subpackages=${handoff.subpackages.map((p) => `${p.root}:${p.pages}`).join(' ')}`)
  console.log(`  alembicHead=${handoff.alembicHead}`)
  console.log(`  packageReportSha=${handoff.packageReportSha || '(需先执行 release 构建)'}`)
}
