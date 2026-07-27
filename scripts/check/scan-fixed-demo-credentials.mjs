#!/usr/bin/env node
import fs from 'node:fs'
import path from 'node:path'

const roots = process.argv.slice(2)
if (!roots.length) {
  console.error('用法：node scripts/check/scan-fixed-demo-credentials.mjs <构建目录> [...]')
  process.exit(2)
}

const rules = [
  { name: '固定中文密码', pattern: /密码\s*123456/u },
  { name: '演示账号常量', pattern: /ROLE_DEMO_ACCOUNT/u },
  { name: '演示密码常量', pattern: /DEMO_PASSWORD/u },
  { name: '固定 password 字面量', pattern: /password["':=\s]+123456/iu }
]

const matches = []

function scanFile(file) {
  const buffer = fs.readFileSync(file)
  if (buffer.includes(0)) return
  const text = buffer.toString('utf8')
  text.split(/\r?\n/u).forEach((line, index) => {
    for (const rule of rules) {
      if (rule.pattern.test(line)) {
        matches.push(`${file}:${index + 1}: ${rule.name}: ${line.trim().slice(0, 240)}`)
      }
    }
  })
}

function walk(target) {
  if (!fs.existsSync(target)) {
    console.error(`构建目录不存在：${target}`)
    process.exitCode = 2
    return
  }
  const stat = fs.statSync(target)
  if (stat.isFile()) return scanFile(target)
  for (const entry of fs.readdirSync(target, { withFileTypes: true })) {
    const child = path.join(target, entry.name)
    if (entry.isDirectory()) walk(child)
    else if (entry.isFile()) scanFile(child)
  }
}

for (const root of roots) walk(root)
if (process.exitCode) process.exit(process.exitCode)

if (matches.length) {
  console.error(matches.join('\n'))
  console.error(`❌ 生产构建发现 ${matches.length} 处固定演示凭据`)
  process.exit(1)
}

console.log('✅ 生产构建未发现固定演示凭据')
