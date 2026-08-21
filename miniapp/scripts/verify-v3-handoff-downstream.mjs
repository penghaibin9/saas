#!/usr/bin/env node
/**
 * Teacher V3 T8 downstream handoff verifier.
 *
 * Student V3 seal is an immutable baseline, not the Teacher branch's current HEAD.
 * Downstream is valid only when:
 *   1) the sealed Student implementation is an ancestor of current HEAD;
 *   2) shared mobile contracts Teacher consumes have not drifted;
 *   3) the current repository still has exactly one Alembic head.
 *
 * This verifier never rewrites miniapp-v3-handoff.json.
 */
import { execFileSync } from 'node:child_process'
import { existsSync, readFileSync } from 'node:fs'
import { fileURLToPath, pathToFileURL } from 'node:url'
import { dirname, resolve } from 'node:path'
import { buildHandoff } from './generate-v3-handoff.mjs'

const here = dirname(fileURLToPath(import.meta.url))
const MINIAPP = resolve(here, '..')
const REPO = resolve(MINIAPP, '..')
const HANDOFF = resolve(REPO, 'miniapp-v3-handoff.json')

export const SHARED_FIELDS = Object.freeze([
  'actionSchemaVersion',
  'routeInventoryHash',
  'subpackageHash',
  'networkPagerVersion',
  'attachmentPickerVersion'
])

function git(...args) {
  return execFileSync('git', args, { cwd: REPO, stdio: ['ignore', 'pipe', 'pipe'] }).toString().trim()
}

function assertAncestor(sha) {
  try {
    execFileSync('git', ['merge-base', '--is-ancestor', sha, 'HEAD'], {
      cwd: REPO,
      stdio: ['ignore', 'ignore', 'pipe']
    })
  } catch (error) {
    const shallow = git('rev-parse', '--is-shallow-repository')
    throw new Error(
      shallow === 'true'
        ? 'Teacher T8 handoff 需要完整 Git 历史；CI checkout 必须 fetch-depth: 0'
        : `Student V3 seal ${sha} 不是当前 HEAD 的祖先`
    )
  }
}

export function verifyDownstreamHandoff() {
  if (!existsSync(HANDOFF)) throw new Error('缺少 miniapp-v3-handoff.json')
  const stored = JSON.parse(readFileSync(HANDOFF, 'utf8'))
  if (stored.schema !== 'miniapp-v3-handoff/1') throw new Error(`不支持的 handoff schema: ${stored.schema || '(empty)'}`)
  if (!/^[0-9a-f]{40}$/.test(String(stored.studentMergeSha || ''))) throw new Error('studentMergeSha 不是完整 SHA')

  assertAncestor(stored.studentMergeSha)

  const current = buildHandoff()
  const drift = []
  for (const field of SHARED_FIELDS) {
    if (!stored[field] || stored[field] !== current[field]) {
      drift.push(`${field}: sealed=${stored[field] || '(empty)'} current=${current[field] || '(empty)'}`)
    }
  }
  if (drift.length) throw new Error(`Teacher T8 共享合同漂移:\n${drift.map((line) => `  - ${line}`).join('\n')}`)

  const alembicHead = String(current.alembicHead || '')
  if (!alembicHead || alembicHead.includes(',')) {
    throw new Error(`当前 Alembic 不是单 head: ${alembicHead || '(empty)'}`)
  }

  return {
    studentMergeSha: stored.studentMergeSha,
    currentHead: git('rev-parse', 'HEAD'),
    alembicHead,
    routeCount: current.routeCount,
    shared: Object.fromEntries(SHARED_FIELDS.map((field) => [field, current[field]]))
  }
}

function isCliEntry() {
  const entry = process.argv[1]
  return !!entry && import.meta.url === pathToFileURL(resolve(entry)).href
}

if (isCliEntry()) {
  try {
    const result = verifyDownstreamHandoff()
    console.log(`[teacher-t8-handoff] OK student=${result.studentMergeSha.slice(0, 12)} current=${result.currentHead.slice(0, 12)} alembic=${result.alembicHead} routes=${result.routeCount}`)
  } catch (error) {
    console.error(`[teacher-t8-handoff] FAIL ${error && error.message ? error.message : error}`)
    process.exit(1)
  }
}
