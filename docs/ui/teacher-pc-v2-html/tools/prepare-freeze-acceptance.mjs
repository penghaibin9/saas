#!/usr/bin/env node

import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const toolDir = path.dirname(fileURLToPath(import.meta.url))
const runnerPath = path.join(toolDir, 'run-freeze-acceptance.mjs')
let source = fs.readFileSync(runnerPath, 'utf8')

const legacyChord = "          await page.keyboard.press(index % 3 === 0 ? 'Shift+Tab' : 'Tab')"
const repairedChord = `          if (index % 3 === 0) {
            await page.keyboard.down('Shift')
            await page.keyboard.press('Tab')
            await page.keyboard.up('Shift')
          } else {
            await page.keyboard.press('Tab')
          }`
if (source.includes(legacyChord)) source = source.replace(legacyChord, repairedChord)

const legacyServer = "    const raw = decodeURIComponent(String(request.url || '/').split('?')[0]).replace(/^\\/+/, '')\n    const target = path.resolve(ROOT, raw || 'index.html')"
const repairedServer = `    const raw = decodeURIComponent(String(request.url || '/').split('?')[0]).replace(/^\\/+/, '')
    if (raw === 'favicon.ico') {
      response.writeHead(204)
      response.end()
      return
    }
    const target = path.resolve(ROOT, raw || 'index.html')`
if (source.includes(legacyServer)) source = source.replace(legacyServer, repairedServer)

if (source.includes("keyboard.press(index % 3 === 0 ? 'Shift+Tab'")) {
  throw new Error('legacy Shift+Tab chord remains')
}
if (!source.includes("await page.keyboard.down('Shift')")) {
  throw new Error('repaired Shift+Tab chord is missing')
}
if (!source.includes("raw === 'favicon.ico'")) {
  throw new Error('favicon 204 handling is missing')
}

fs.writeFileSync(runnerPath, source)
console.log('freeze acceptance runner prepared')
