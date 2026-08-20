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
import { existsSync, readFileSync, renameSync, writeFileSync } from 'node:fs'
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

/** 读一个 commit object，拆出 subject 与全部父 SHA；对象取不到时返回 null。 */
function commitObject(ref) {
  const raw = git('cat-file', '-p', ref)
  if (!raw) return null
  const [headers = '', ...messageParts] = raw.split('\n\n')
  const subject = messageParts.join('\n\n').split('\n', 1)[0].trim()
  const parents = headers.split('\n')
    .filter((line) => line.startsWith('parent '))
    .map((line) => line.slice('parent '.length).trim())
    .filter(Boolean)
  return { subject, parents }
}

/**
 * 解析「这份 handoff 封住的实现提交」。
 *
 * 手册 §13.1 要求 Teacher T8 **从合入后的 main 上**机器校验，所以三种 HEAD 都要能解析：
 *
 *   1. 分支上的 seal 提交本身 → 被封存的实现提交是它的第一父；
 *   2. main 上把该分支并进来的 merge 提交 → 第二父是被并入的分支尖端，
 *      若尖端正是 seal 就再取一次它的第一父；
 *   3. 其他普通提交 → 就是它自己，于是 seal 之后任何业务提交都会漂移并 fail-closed。
 *
 * 情况 2 需要读第二父的 commit object。actions/checkout 默认 fetch-depth=1 时该对象不
 * 存在——那时返回 unresolved 而不是硬套 HEAD：把“看不到”说成“漂移了”是假警报，会让
 * T8 以为学生端契约变了。校验器据此给出可执行的提示（用完整历史重跑），而不是误判。
 */
export function resolveSealedSha(readCommit, head) {
  if (!head) return { sha: '', unresolved: false }
  const commit = readCommit(head)
  if (!commit) return { sha: head, unresolved: false }
  if (commit.subject === SEAL_SUBJECT) {
    return { sha: commit.parents[0] || head, unresolved: false }
  }
  if ((commit.parents || []).length < 2) return { sha: head, unresolved: false }

  const mergedTip = commit.parents[1]
  const tip = readCommit(mergedTip)
  if (!tip) return { sha: '', unresolved: true, reason: `无法读取被并入的分支尖端 ${mergedTip}` }
  if (tip.subject === SEAL_SUBJECT) {
    return { sha: tip.parents[0] || mergedTip, unresolved: false }
  }
  return { sha: mergedTip, unresolved: false }
}

function implementationSha() {
  return resolveSealedSha((ref) => commitObject(ref), gitSha())
}

/**
 * 落盘用的实现 SHA。解析不出来时回落到 HEAD，绝不写空串——交接物里一个空的
 * studentMergeSha 比一个"不够精确但真实存在"的提交更糟：它看起来像字段缺失，
 * 下游无从判断到底是没封还是封坏了。真正该报「解析不出来」的地方是 verify()，
 * 它会明确说是历史深度不够并给出处置。
 */
function sealedShaOrHead() {
  const resolved = implementationSha()
  return resolved.sha || gitSha()
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

/**
 * 包体报告的内容哈希——必须只反映**包本身**，不能反映"什么时候构建的"。
 *
 * 报告里带 generatedAt，直接哈希整份文件的话，同一份产物每构建一次就换一个值，
 * 这个字段就永远无法被独立复现，T8 拿它比不出任何东西。所以剔掉易变字段并按
 * 键排序后再哈希：同样的包 → 同样的哈希，包变了才变。
 */
const VOLATILE_REPORT_FIELDS = new Set(['generatedAt'])

export function canonicalize(value) {
  if (Array.isArray(value)) return value.map(canonicalize)
  if (value && typeof value === 'object') {
    return Object.keys(value).sort().reduce((acc, key) => {
      if (!VOLATILE_REPORT_FIELDS.has(key)) acc[key] = canonicalize(value[key])
      return acc
    }, {})
  }
  return value
}

function packageReportSha() {
  const report = resolve(MINIAPP, 'dist/build/mp-weixin/miniapp-package-report.json')
  if (!existsSync(report)) return ''
  try {
    return sha256(JSON.stringify(canonicalize(JSON.parse(read(report)))))
  } catch (error) {
    // 报告解析不了就别假装算得出稳定哈希——当作没有报告，由调用方跳过比对。
    return ''
  }
}

export function buildHandoff() {
  const inventory = routeInventory()
  return {
    schema: 'miniapp-v3-handoff/1',
    generatedAt: new Date().toISOString(),
    studentMergeSha: sealedShaOrHead(),
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

  // 先把「解析不出来」和「真的漂移了」分开报。两者都 fail-closed（T8 不能在无法校验的
  // 检出上接线），但原因不能说反：浅克隆读不到被并入的分支尖端时说“契约漂移”，
  // 会让 T8 以为学生端改了东西，实际只是历史深度不够。
  const resolved = implementationSha()
  if (resolved.unresolved) {
    console.error('[handoff] 无法解析被封存的实现提交，因此不能判定契约是否漂移：')
    console.error(`  - ${resolved.reason}`)
    console.error('  - 这通常是 actions/checkout 默认 fetch-depth=1 的浅克隆；')
    console.error('    请用完整历史（fetch-depth: 0）或 git fetch --unshallow 后重跑本校验。')
    return 1
  }

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

/**
 * 只有「直接执行本脚本」才允许产生副作用。
 *
 * handoff-contract.test.mjs 会 `import { buildHandoff }`，而 ESM 的 import 会执行整个模块
 * 顶层。少了这道判断，`npm test` 本身就会把 miniapp-v3-handoff.json 重写一遍：跑完测试
 * 工作区凭空变脏，更糟的是在 main 上它会把封存的实现 SHA 覆盖成 merge 提交的 SHA，
 * 等于测试顺手毁掉交付物。生成/校验只能由命令行触发。
 */
const invokedDirectly = process.argv[1]
  ? resolve(process.argv[1]) === fileURLToPath(import.meta.url)
  : false

function writeHandoffAtomically(handoff) {
  const temp = `${OUTPUT}.${process.pid}.${Date.now()}.tmp`
  writeFileSync(temp, `${JSON.stringify(handoff, null, 2)}\n`, 'utf8')
  renameSync(temp, OUTPUT)
}

const isVerify = process.argv.includes('--verify')
if (!invokedDirectly) {
  // 被 import：只提供 buildHandoff 等纯函数，不读写任何文件。
} else if (isVerify) {
  process.exit(verify())
} else {
  const handoff = buildHandoff()
  writeHandoffAtomically(handoff)
  console.log(`[handoff] 已生成 ${OUTPUT}`)
  console.log(`  implementationSha=${handoff.studentMergeSha}`)
  console.log(`  routes=${handoff.routeCount} subpackages=${handoff.subpackages.map((p) => `${p.root}:${p.pages}`).join(' ')}`)
  console.log(`  alembicHead=${handoff.alembicHead}`)
  console.log(`  packageReportSha=${handoff.packageReportSha || '(需先执行 release 构建)'}`)
}
