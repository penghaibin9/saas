import fs from 'node:fs'

const stub = 'data:text/javascript,' + encodeURIComponent('export const ENV={}; export const markMobileViewsDirty=()=>{}; export const relaunch=()=>true;')
const generationUrl = new URL('../src/services/sessionGeneration.mjs', import.meta.url).href
const source = fs.readFileSync(new URL('../src/services/request.js', import.meta.url), 'utf8')
  .replace(/from '@\/[^']+'/g, `from '${stub}'`)
  .replace("from './sessionGeneration.mjs'", `from '${generationUrl}'`)
export const request = await import('data:text/javascript,' + encodeURIComponent(source))
export const { normalizeError } = request
