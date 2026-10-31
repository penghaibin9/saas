import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'

function exporter() {
  const allocated = []
  const source = fs.readFileSync(new URL('../src/utils/xlsxDownload.js', import.meta.url), 'utf8')
    .replace(/^import[^\n]+\n/gm, '').replace(/^export default[^\n]+/gm, '').replace(/export function/g, 'function')
  const prepare = new Function('URL', source + '\nreturn prepareXlsxDownload')({ createObjectURL: blob => { allocated.push(blob); return 'blob:synthetic-export' } })
  return { prepare, allocated }
}

test('可下载导出快照保留真实字节、文件名与完整行数', async () => {
  const { prepare, allocated } = exporter()
  const output = prepare({ filename: '工资台账.xlsx', contentBase64: Buffer.from('synthetic-file-bytes').toString('base64'), rowCount: '25' })
  assert.deepEqual(output, { url: 'blob:synthetic-export', filename: '工资台账.xlsx', rowCount: 25 })
  assert.equal(await allocated[0].text(), 'synthetic-file-bytes')
})

test('不完整字节、非表格文件和错误行数不产生对象地址', () => {
  const { prepare, allocated } = exporter()
  const valid = { filename: '工资台账.xlsx', contentBase64: 'YQ==', rowCount: 1 }
  for (const change of [{ contentBase64: '' }, { contentBase64: 'not-base64!' }, { filename: '工资台账.txt' }, { rowCount: -1 }, { rowCount: 1.5 }, { rowCount: '内部字段' }]) {
    assert.throws(() => prepare({ ...valid, ...change }))
  }
  assert.equal(allocated.length, 0)
})
