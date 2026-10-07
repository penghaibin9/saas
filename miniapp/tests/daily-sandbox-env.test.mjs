import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
const source=readFileSync(new URL('../src/config/env.js',import.meta.url),'utf8').replaceAll('import.meta.env.','build.').replace('export const ENV','const ENV').replace('export default ENV','return ENV')
const env=build=>new Function('build',source)({DEV:true,PROD:false,VITE_API_BASE_URL:'http://127.0.0.1:8000',VITE_USE_MOCK:'false',...build})
test('daily sandbox disables mock fallback while keeping the real backend',()=>{const value=env({VITE_ALLOW_MOCK_FALLBACK:'false'});assert.equal(value.useMock,false);assert.equal(value.allowMockFallback,false)})
test('production cannot opt into mock fallback',()=>{const value=env({DEV:false,PROD:true,VITE_ALLOW_MOCK_FALLBACK:'true',VITE_USE_MOCK:'true'});assert.equal(value.useMock,false);assert.equal(value.allowMockFallback,false)})
