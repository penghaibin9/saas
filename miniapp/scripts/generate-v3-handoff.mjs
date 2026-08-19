#!/usr/bin/env node
/**
 * V3 §S9 / 深审 P1-15：生成并校验 miniapp-v3-handoff.json。
 *
 * 只交一个 merge SHA 是不够的——Teacher V3 的 Agent 拿到之后仍然要靠猜共享 schema
 * 与组件版本。本脚本把"学生端交出去的到底是什么"固化成机器可校验的合同：
 *
 *   studentMergeSha        本次交付所在的 commit
 *   actionSchemaVersion    MobileAction DTO 形状版本
 *   routeInventoryHash     pages.json 还原出的完整 URL 集合哈希
 *   subpackageHash         分包结构哈希（root + 页数）
 *   networkPagerVersion    共享分页器契约版本
 *   attachmentPickerVersion 共享附件组件契约版本
 *   alembicHead            后端迁移单头
 *   packageReportSha       三包体积报告哈希（需先跑 release 构建）
 *
 * 用法：
 *   node scripts/generate-v3-handoff.mjs            # 生成
 *   node scripts/generate-v3-handoff.mjs --verify   # 机器校验（T8 用）
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

const sha256 = (value) => createHash('sha256').update(value).digest('hex')
const read = (path) => readFileSync(path, 'utf8')

function gitSha() {
  try {
    return execFileSync('git', ['rev-parse', 'HEAD'], { cwd: REPO }).toString().trim()
  } catch (error) {
    return ''
  }
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
  // 单头由 CI 的 `alembic heads | wc -l` 保证；这里只记录当前 head 文件名哈希的来源。
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
    studentMergeSha: gitSha(),
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
  'subpackageHash', 'networkPagerVersion', 'attachmentPickerVersion', 'alembicHead'
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
    // studentMergeSha 与 packageReportSha 依赖具体构建，不参与漂移比对。
    if (field === 'studentMergeSha') continue
    if (stored[field] !== current[field]) {
      drift.push(`${field} 漂移：交付=${stored[field]} 实际=${current[field]}`)
    }
  }
  if (drift.length) {
    console.error('[handoff] 共享契约已漂移，Teacher T8 不得据此接线：')
    for (const line of drift) console.error('  -', line)
    return 1
  }
  console.log(`[handoff] OK routes=${current.routeCount} alembicHead=${current.alembicHead}`)
  return 0
}

const isVerify = process.argv.includes('--verify')
if (isVerify) {
  process.exit(verify())
} else {
  const handoff = buildHandoff()
  writeFileSync(OUTPUT, `${JSON.stringify(handoff, null, 2)}\n`, 'utf8')
  console.log(`[handoff] 已生成 ${OUTPUT}`)
  console.log(`  routes=${handoff.routeCount} subpackages=${handoff.subpackages.map((p) => `${p.root}:${p.pages}`).join(' ')}`)
  console.log(`  alembicHead=${handoff.alembicHead}`)
  console.log(`  packageReportSha=${handoff.packageReportSha || '(需先执行 release 构建)'}`)
}
