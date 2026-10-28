import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'

const source = relative => fs.readFileSync(new URL('../' + relative, import.meta.url), 'utf8')

function realClient(request) {
  const executable = source('src/modules/internship/api/internship-student.api.js')
    .replace(/^import[^\n]*\n/gm, '')
    .replace('export const internStudentApi', 'const internStudentApi')
    .replace('export default internStudentApi', 'return internStudentApi')
  return new Function('request', 'requestBlob', 'requestUpload', executable)(request, () => {}, () => {})
}

function candidate(request) {
  const executable = source('src/modules/internship/pickerAdapters.js')
    .replace(/^import[^\n]*\n/gm, '')
    .replace('export async function loadInitialInternshipBatch', 'async function loadInitialInternshipBatch')
    .replace('export const internshipPickerAdapters', 'const internshipPickerAdapters')
  const adapters = new Function('internStudentApi', 'matchApi', 'positionApi', 'internshipApi', 'createOrgPickerAdapters',
    executable + '\nreturn internshipPickerAdapters')(realClient(request), {}, {}, {}, () => ({}))
  return adapters.candidateInternshipStudent
}

const largeId = '9007199254740993123'
const row = { id: largeId, name: '合成学生', studentNo: '00009007199254740993123' }

test('真实接口与搜索适配器请求主档目录，保留大编号和前导零学号', async () => {
  const calls = [], picker = candidate(async (url, options) => { calls.push({ url, options }); return { items: [row], total: 31 } })
  const options = await picker.search('合成 & 学生')
  assert.deepEqual(calls, [{ url: '/directory/student-options', options: { params: { page: 1, pageSize: 30, keyword: '合成 & 学生' } } }])
  assert.deepEqual(options, [{ value: largeId, label: row.name, desc: `学号 ${row.studentNo}`, raw: row }])
})

test('第31个已选主档按原编号回读，不用第一页或实习记录编号', async () => {
  const calls = [], picker = candidate(async (url, options) => {
    calls.push({ url, options })
    assert.equal(options.params.ids, largeId)
    return { items: [row], total: 1 }
  })
  const resolved = await picker.resolve(largeId)
  assert.equal(resolved.value, largeId)
  assert.equal(resolved.label, row.name)
  assert.deepEqual(calls, [{ url: '/directory/student-options', options: { params: { ids: largeId } } }])
})

test('多选回读按输入顺序返回，未知范围对象不伪造名称，输入不被改写', async () => {
  const selected = [largeId, '31', '99', largeId], original = [...selected]
  const calls = [], picker = candidate(async (_, { params }) => {
    calls.push(params.ids)
    return { items: [{ id: '31', name: '第三十一名', studentNo: '00031' }, row] }
  })
  const options = await picker.resolve(selected)
  assert.deepEqual(calls, [`${largeId},31,99`])
  assert.deepEqual(options.map(option => option.value), [largeId, '31', largeId])
  assert.deepEqual(selected, original)
})

test('超过100个已选编号分段读取，不扩大首次搜索上限', async () => {
  const selected = Array.from({ length: 101 }, (_, index) => String(index + 1)), calls = []
  const picker = candidate(async (_, { params }) => {
    calls.push(params)
    return { items: params.ids.split(',').reverse().map(id => ({ id, name: `合成学生${id}`, studentNo: `00${id}` })) }
  })
  assert.deepEqual((await picker.resolve(selected)).map(option => option.value), selected)
  assert.equal(calls.length, 2)
  assert.equal(calls[0].ids.split(',').length, 100)
  assert.equal(calls[1].ids, '101')
})

test('业务拒绝保留真实错误信息，搜索及回显不得伪装空结果', async () => {
  const error = Object.assign(new Error('当前身份无权读取该学生'), { biz: true, code: 1, bizCode: 'NO_PERMISSION', httpStatus: 403 })
  const request = async () => { throw error }, api = realClient(request), picker = candidate(request)
  assert.deepEqual(await api.getStudentOptionsByIds([largeId]), {
    code: 1, data: null, message: error.message, bizCode: 'NO_PERMISSION', httpStatus: 403
  })
  await assert.rejects(picker.search('合成'), { message: error.message })
  const selected = [largeId]
  await assert.rejects(picker.resolve(selected), { message: error.message })
  assert.deepEqual(selected, [largeId])
})

test('空选中值无需请求，单选与多选回显合同保持一致', async () => {
  let reads = 0
  const picker = candidate(async () => { reads++; return { items: [] } })
  assert.equal(await picker.resolve(''), undefined)
  assert.deepEqual(await picker.resolve([]), [])
  assert.equal(reads, 0)
})
