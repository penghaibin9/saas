import { spawn } from 'node:child_process'
import { mkdirSync, createWriteStream } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import process from 'node:process'

const args = ['--test', ...process.argv.slice(2)]
const evidenceDir = join(tmpdir(), 'student-affairs-build-evidence')
const evidencePath = join(evidenceDir, 'frontend-node-tests.tap')
let evidence = null

if (process.env.CI) {
  mkdirSync(evidenceDir, { recursive: true })
  evidence = createWriteStream(evidencePath, { flags: 'w' })
  evidence.write(`# command: ${process.execPath} ${args.join(' ')}\n`)
  evidence.write(`# cwd: ${process.cwd()}\n`)
}

const child = spawn(process.execPath, args, {
  cwd: process.cwd(),
  env: process.env,
  stdio: ['inherit', 'pipe', 'pipe']
})

for (const [stream, target] of [[child.stdout, process.stdout], [child.stderr, process.stderr]]) {
  stream.on('data', (chunk) => {
    target.write(chunk)
    evidence?.write(chunk)
  })
}

child.on('error', (error) => {
  const line = `\n# test runner error: ${error.stack || error.message}\n`
  process.stderr.write(line)
  evidence?.end(line)
  process.exitCode = 1
})

child.on('close', (code, signal) => {
  const exitCode = Number.isInteger(code) ? code : 1
  const footer = `\n# exitCode: ${exitCode}\n# signal: ${signal || ''}\n`
  if (evidence) {
    evidence.end(footer, () => {
      process.exit(exitCode)
    })
    return
  }
  process.exit(exitCode)
})
