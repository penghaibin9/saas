#!/usr/bin/env node

import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import process from 'node:process'
import { spawnSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'

const TOOL_DIR = path.dirname(fileURLToPath(import.meta.url))
const ROOT = path.resolve(TOOL_DIR, '..')
const args = process.argv.slice(2)
const listOnly = args.includes('--list-only')
const keepTemp = args.includes('--keep-temp')

const FAMILY_PARTS = {
  'student-affairs-key': ['manifest-parts/300-student-affairs-key.json'],
  'student-affairs-all': [
    'manifest-parts/300-student-affairs-key.json',
    'manifest-parts/330-student-affairs-extension.json'
  ],
  graduation: ['manifest-parts/320-graduation.json']
}

const FAMILY_EXPECTED = {
  'student-affairs-key': 11,
  'student-affairs-all': 15,
  graduation: 8
}

function readArg(name) {
  const inline = args.find((arg) => arg.startsWith(`${name}=`))
  if (inline) return inline.slice(name.length + 1)
  const index = args.indexOf(name)
  return index >= 0 ? args[index + 1] : ''
}

function stripSelectionArgs(values) {
  const namesWithValue = new Set(['--family', '--prefix', '--html'])
  const flags = new Set(['--list-only', '--keep-temp'])
  const output = []
  for (let index = 0; index < values.length; index += 1) {
    const value = values[index]
    if (flags.has(value)) continue
    if ([...namesWithValue].some((name) => value.startsWith(`${name}=`))) continue
    if (namesWithValue.has(value)) {
      index += 1
      continue
    }
    output.push(value)
  }
  return output
}

function safeJson(abs) {
  return JSON.parse(fs.readFileSync(abs, 'utf8'))
}

function rowsOf(part) {
  return Array.isArray(part?.entries) ? part.entries : Array.isArray(part?.routes) ? part.routes : []
}

function allManifestHtml() {
  const manifest = safeJson(path.join(ROOT, 'prototype-manifest.json'))
  const rows = []
  for (const partRef of manifest?.aggregation?.parts || []) {
    const part = safeJson(path.resolve(ROOT, partRef))
    rows.push(...rowsOf(part))
  }
  return [...new Set(rows.map((row) => row?.html).filter(Boolean))].sort()
}

function htmlFromParts(partRefs) {
  const rows = []
  for (const partRef of partRefs) {
    const part = safeJson(path.resolve(ROOT, partRef))
    rows.push(...rowsOf(part))
  }
  return rows.map((row) => row?.html).filter(Boolean)
}

function splitCsv(raw) {
  return String(raw || '').split(',').map((value) => value.trim()).filter(Boolean)
}

function selectHtml() {
  const family = readArg('--family')
  const prefixes = splitCsv(readArg('--prefix'))
  const exact = splitCsv(readArg('--html'))
  const selected = new Set()
  const all = allManifestHtml()

  if (family) {
    const partRefs = FAMILY_PARTS[family]
    if (!partRefs) {
      throw new Error(`未知页面族：${family}。可用值：${Object.keys(FAMILY_PARTS).join(', ')}`)
    }
    for (const html of htmlFromParts(partRefs)) selected.add(html)
    const expected = FAMILY_EXPECTED[family]
    if (typeof expected === 'number' && selected.size !== expected) {
      throw new Error(`页面族 ${family} 聚合得到 ${selected.size} 个 HTML，期望 ${expected}；先修复 Manifest 口径`)
    }
  }

  for (const prefix of prefixes) {
    for (const html of all) if (html.startsWith(prefix)) selected.add(html)
  }

  for (const html of exact) {
    if (!all.includes(html)) throw new Error(`指定 HTML 不在总 Manifest：${html}`)
    selected.add(html)
  }

  if (!family && !prefixes.length && !exact.length) {
    throw new Error('必须提供 --family、--prefix 或 --html；全库回归请直接运行 run-browser-regression.mjs')
  }

  const missing = [...selected].filter((html) => !fs.existsSync(path.resolve(ROOT, html)))
  if (missing.length) throw new Error(`选中 HTML 不存在：${missing.join(', ')}`)
  if (!selected.size) throw new Error('筛选结果为 0 个 HTML')
  return [...selected].sort()
}

function prepareTempRoot(selected) {
  const tempParent = fs.mkdtempSync(path.join(os.tmpdir(), 'teacher-pc-v2-family-'))
  const tempRoot = path.join(tempParent, 'teacher-pc-v2-html')
  fs.cpSync(ROOT, tempRoot, {
    recursive: true,
    filter: (source) => !source.includes(`${path.sep}node_modules${path.sep}`)
  })

  const generatedPart = 'manifest-parts/__selected-regression.json'
  fs.writeFileSync(path.join(tempRoot, generatedPart), `${JSON.stringify({
    moduleKey: 'selected-regression',
    moduleLabel: 'Selected browser regression pages',
    entries: selected.map((html, index) => ({
      route: `/__selected_regression__/${index + 1}`,
      html
    }))
  }, null, 2)}\n`)

  const manifestPath = path.join(tempRoot, 'prototype-manifest.json')
  const manifest = safeJson(manifestPath)
  manifest.aggregation.parts = [generatedPart]
  manifest.coverage.uniqueHtmlFiles = selected.length
  manifest.validation = {
    ...(manifest.validation || {}),
    selectedRegression: {
      generatedAt: new Date().toISOString(),
      selectedHtmlCount: selected.length,
      sourceRoot: ROOT
    }
  }
  fs.writeFileSync(manifestPath, `${JSON.stringify(manifest, null, 2)}\n`)
  return { tempParent, tempRoot }
}

function main() {
  const selected = selectHtml()
  console.log(`选中 ${selected.length} 个 HTML：`)
  for (const html of selected) console.log(`- ${html}`)
  if (listOnly) return

  const { tempParent, tempRoot } = prepareTempRoot(selected)
  const runner = path.join(tempRoot, 'tools', 'run-browser-regression.mjs')
  const forwarded = stripSelectionArgs(args)
  let exitCode = 2
  try {
    const result = spawnSync(process.execPath, [runner, ...forwarded], {
      cwd: ROOT,
      stdio: 'inherit',
      env: process.env
    })
    if (result.error) throw result.error
    exitCode = result.status ?? 2
  } finally {
    if (keepTemp) console.log(`保留临时页面族快照：${tempRoot}`)
    else fs.rmSync(tempParent, { recursive: true, force: true })
  }
  process.exit(exitCode)
}

try {
  main()
} catch (error) {
  console.error(error.stack || error.message)
  process.exit(2)
}
