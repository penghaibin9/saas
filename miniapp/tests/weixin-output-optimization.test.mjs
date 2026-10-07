import test from 'node:test'
import assert from 'node:assert/strict'
import { mkdtempSync, mkdirSync, writeFileSync, readFileSync, existsSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import path from 'node:path'
import { createRequire } from 'node:module'
import { optimizeWeixin } from '../scripts/optimize-mp-weixin.mjs'
const fixture = () => {
  const dir = mkdtempSync(path.join(tmpdir(), 'weixin-opt-'))
  const put = (name, value) => { mkdirSync(path.dirname(path.join(dir, name)), { recursive: true }); writeFileSync(path.join(dir, name), value) }
  put('app.json', JSON.stringify({ pages: ['login'], subPackages: [{ root: 'pages/teacher', pages: ['home'] }] }, null, 2))
  put('app.js', 'exports.ready=true;exports.home="/pages/teacher/home";')
  put('login.js', 'exports.value=require("./services/shared.js").value;')
  put('services/shared.js', 'exports.value=7;')
  put('services/teacher.js', 'exports.read=()=>require("./shared.js").value+1;')
  put('pages/teacher/home.js', 'exports.read=()=>require("../../services/teacher.js").read();exports.scope="data-v-ab123456";')
  put('pages/teacher/home.wxml', '<view class="data-v-ab123456"><widget/></view>')
  put('pages/teacher/home.json', '{"usingComponents":{"widget":"../../components/Widget"}}')
  put('components/Widget.js', 'exports.value=42;exports.scope="data-v-ff123456";')
  put('components/Widget.json', '{"component":true}')
  put('components/Widget.wxss', '.x.data-v-ff123456{color:red}')
  put('components/Widget.wxml', '<view class="x data-v-ff123456">42</view>')
  return { dir, put }
}
test('private dependencies move as a complete component family and execute identically', () => {
  const { dir } = fixture()
  try {
    const result = optimizeWeixin(dir)
    const req = createRequire(path.join(dir, 'app.js'))
    assert.equal(req('./pages/teacher/home.js').read(), 8)
    assert.equal(req('./login.js').value, 7)
    assert.ok(existsSync(path.join(dir, 'services/shared.js')))
    assert.ok(!existsSync(path.join(dir, 'services/teacher.js')))
    assert.equal(result.movedFiles['components/Widget.js'], 'pages/teacher/_shared/components/Widget.js')
    for (const ext of ['js', 'json', 'wxml', 'wxss']) assert.ok(existsSync(path.join(dir, 'pages/teacher/_shared/components/Widget.' + ext)))
    const component = req('./pages/teacher/_shared/components/Widget.js')
    assert.ok(readFileSync(path.join(dir, 'pages/teacher/_shared/components/Widget.wxss'), 'utf8').includes(component.scope))
    assert.ok(readFileSync(path.join(dir, 'pages/teacher/_shared/components/Widget.wxml'), 'utf8').includes(component.scope))
    assert.notEqual(component.scope, req('./pages/teacher/home.js').scope)
    const page = JSON.parse(readFileSync(path.join(dir, 'pages/teacher/home.json'), 'utf8'))
    assert.equal(page.usingComponents.widget, './_shared/components/Widget')
    assert.ok(result.afterBytes < result.beforeBytes)
    assert.equal(Object.keys(optimizeWeixin(dir).movedFiles).length, 0)
  } finally { rmSync(dir, { recursive: true, force: true }) }
})
test('a component referenced by login never moves into a subpackage', () => {
  const { dir, put } = fixture()
  try { put('login.json', '{"usingComponents":{"widget":"./components/Widget"}}'); const r = optimizeWeixin(dir); assert.ok(!r.movedFiles['components/Widget.js']) }
  finally { rmSync(dir, { recursive: true, force: true }) }
})

test('student-only dependencies leave the main package too', () => {
  const { dir, put } = fixture()
  try {
    put('app.json', JSON.stringify({ pages: ['login'], subPackages: [{ root: 'pages/student', pages: ['home'] }] }))
    put('pages/student/home.js', 'exports.read=()=>require("../../services/student.js").value')
    put('services/student.js', 'exports.value=9')
    const result = optimizeWeixin(dir)
    const req = createRequire(path.join(dir, 'app.js'))
    assert.equal(req('./pages/student/home.js').read(), 9)
    assert.ok(!existsSync(path.join(dir, 'services/student.js')))
    assert.equal(result.movedFiles['services/student.js'], 'pages/student/_shared/services/student.js')
  } finally { rmSync(dir, { recursive: true, force: true }) }
})
