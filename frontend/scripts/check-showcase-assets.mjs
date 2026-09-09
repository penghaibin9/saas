import fs from 'node:fs'
import path from 'node:path'
import crypto from 'node:crypto'
import { fileURLToPath } from 'node:url'
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
export function checkShowcaseAssets(frontendRoot = root) {
  const manifest = JSON.parse(fs.readFileSync(path.join(frontendRoot, 'scripts/showcase-assets.json'), 'utf8'))
  const assets = path.join(frontendRoot, 'public/official-site/showcase-20260909')
  const errors = []
  if (manifest.count !== 143 || Object.keys(manifest.assets).length !== 143) errors.push('Expected 143 approved images')
  for (const [name, sha] of Object.entries(manifest.assets)) {
    if (!/^(screens|scenes|boards)\/[a-z0-9-]+\.webp$/.test(name)) { errors.push(`Invalid asset path: ${name}`); continue }
    const file = path.join(assets, name)
    if (!fs.existsSync(file)) { errors.push(`Missing: ${name}`); continue }
    if (crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex') !== sha) errors.push(`SHA256 mismatch: ${name}`)
  }
  const releaseFile = path.join(assets, 'release.json')
  if (!fs.existsSync(releaseFile)) errors.push('Missing release.json; the working legacy homepage remains active')
  else {
    const release = JSON.parse(fs.readFileSync(releaseFile, 'utf8'))
    if (release.version !== manifest.version || release.assetCount !== 143 || release.businessCount !== 67 || release.expandedCount !== 60) errors.push('Invalid release.json')
  }
  return { ready: errors.length === 0, expected: 143, errors }
}
if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const result = checkShowcaseAssets()
  console.log(JSON.stringify(result, null, 2))
  if (!result.ready && process.argv.includes('--required')) process.exitCode = 1
}
