import assert from 'node:assert/strict'
import test from 'node:test'
import { graduationTemplateCopy } from './graduation-template-copy.mjs'

const sfc = (template) => `<template>${template}</template>`

test('graduation copy inspection keeps internal version and read-only bindings out of displayed copy', () => {
  const result = graduationTemplateCopy(sfc('<section><span>文件核对</span><Viewer :canonical-version-id="canonicalFileVersionId" :read-only="Boolean(readerFile?.peerId)" :data-file-version-id="canonicalFileVersionId" /></section>'))
  assert.equal(result.text, '文件核对')
  assert.deepEqual(result.directOutputs, [])
})

test('graduation copy inspection rejects actual technical copy in interpolation branches', () => {
  const result = graduationTemplateCopy(sfc('<span>{{ ready ? "FileVersion 已锁定" : "等待文件" }}</span>'))
  assert.match(result.text, /FileVersion 已锁定/)
  assert.match(result.text, /等待文件/)
})

test('graduation copy inspection records direct identifier rendering separately from safe bindings', () => {
  const result = graduationTemplateCopy(sfc('<span>{{ canonicalFileVersionId }}</span><span>{{ readerFile?.peerId }}</span>'))
  assert.deepEqual(result.directOutputs, ['canonicalFileVersionId', 'readerFile?.peerId'])
})

test('graduation copy inspection keeps collapsed evidence secondary but does not hide an open evidence panel', () => {
  const closed = graduationTemplateCopy(sfc('<details><summary>文件检查</summary><code>FileVersion</code></details>'))
  assert.equal(closed.text, '文件检查')
  const open = graduationTemplateCopy(sfc('<details open><summary>文件检查</summary><code>FileVersion</code></details>'))
  assert.match(open.text, /FileVersion/)
})

test('graduation copy inspection includes accessible labels and literal dynamic titles', () => {
  const result = graduationTemplateCopy(sfc('<button aria-label="FileVersion 操作" :title="ready ? \'允许审核\' : \'等待检查\'">通过</button>'))
  assert.match(result.text, /FileVersion 操作/)
  assert.match(result.text, /允许审核/)
  assert.match(result.text, /等待检查/)
  assert.match(result.text, /通过/)
})

test('graduation copy inspection does not treat comments and script variable names as visible copy', () => {
  const result = graduationTemplateCopy('<template><p>在线查看</p><!-- canonical FileVersion --></template><script setup>const peerId = 1</script>')
  assert.equal(result.text, '在线查看')
})

test('graduation copy inspection fails instead of accepting an unparseable expression', () => {
  assert.throws(() => graduationTemplateCopy(sfc('<p>{{ ready ? }}</p>')))
})
