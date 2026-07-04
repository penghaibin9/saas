// 自动探测 dev 端口(5173-5177)，逐个请求 vite 按需编译的模块 URL，捕获编译错误。
import fs from 'fs'
import path from 'path'

async function detectBase() {
  if (process.env.BASE) return process.env.BASE
  for (const p of [5188, 5173, 5174, 5175, 5176, 5177]) {
    const base = 'http://localhost:' + p
    try {
      const r = await fetch(base + '/', { headers: { Accept: 'text/html' } })
      if (r.status < 500) return base
    } catch (e) { /* try next */ }
  }
  return null
}

const BASE = await detectBase()
if (!BASE) { console.log('未发现运行中的 dev server（5173-5177 均无响应）'); process.exit(2) }

const src = path.join(process.cwd(), 'src')
function walk(dir, acc = []) {
  for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
    const fp = path.join(dir, e.name)
    if (e.isDirectory()) walk(fp, acc)
    else acc.push(fp)
  }
  return acc
}

const targets = ['/src/main.js', '/src/App.vue']
for (const f of walk(src)) {
  if (f.endsWith('.vue') || (f.endsWith('.js') && (f.includes('config') || f.includes('mock') || f.includes('services') || f.includes('stores') || f.includes('utils')))) {
    targets.push('/' + path.relative(process.cwd(), f).split(path.sep).join('/'))
  }
}

let ok = 0, bad = 0
const fails = []
for (const t of targets) {
  try {
    const res = await fetch(BASE + t, { headers: { Accept: '*/*' } })
    const txt = await res.text()
    const isErr = res.status >= 400 || /Internal Server Error|Transform failed|Parse failure|\[vite\].*error|SyntaxError|Failed to resolve import/i.test(txt.slice(0, 500))
    if (isErr) { bad++; fails.push({ t, status: res.status, msg: txt.slice(0, 300).replace(/\s+/g, ' ') }) }
    else ok++
  } catch (e) {
    bad++; fails.push({ t, status: 'FETCH_ERR', msg: String(e.message || e) })
  }
}

console.log('BASE=' + BASE)
console.log('模块编译检查：OK ' + ok + ' / 失败 ' + bad + ' / 共 ' + targets.length)
if (fails.length) {
  console.log('\n--- 失败明细 ---')
  for (const f of fails) console.log('[' + f.status + '] ' + f.t + '\n    ' + f.msg + '\n')
  process.exit(1)
} else {
  console.log('✅ 全部模块编译通过，无红色报错')
}
