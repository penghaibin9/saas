import assert from 'node:assert/strict'
import test from 'node:test'
import fs from 'node:fs'

const source = fs.readFileSync(new URL('../src/modules/system/api/implementation.api.js', import.meta.url), 'utf8')
const createApi = new Function('request', 'requestUpload', source
  .replace(/^import .* from .*\r?\n/, '')
  .replace('export const implementationApi =', 'const implementationApi =') + '\nreturn implementationApi')

test('absent implementation projects normalize to null and cannot trigger dependent reads', async () => {
  for (const response of [{}, null]) {
    const calls = []
    const api = createApi(async path => { calls.push(path); return response })
    const project = await api.current()
    if (project) await api.relationBatches(project.id)
    assert.equal(project, null)
    assert.deepEqual(calls, ['/system/implementation/projects/current'])
  }
})

test('existing implementation project keeps its full payload and string ID', async () => {
  const project = { id: '9007199254740993', projectName: '学校首次实施', sections: [] }
  const calls = []
  const api = createApi(async path => { calls.push(path); return project })
  assert.equal(await api.current(), project)
  await api.relationBatches(project.id)
  assert.equal(calls[1], '/system/implementation/projects/9007199254740993/relations/batches')
})

test('failed project reads remain errors rather than appearing as an empty school', async () => {
  const error = new Error('实施项目加载失败')
  const api = createApi(async () => { throw error })
  await assert.rejects(api.current(), error)
})
