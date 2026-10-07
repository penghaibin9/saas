import assert from 'node:assert/strict'
import { register } from 'node:module'
import test from 'node:test'

// form-state 依赖 '@/' 别名；node 原生测试没有 vite 别名，这里注册一个最小解析钩子。
const srcRoot = new URL('../../../../', import.meta.url).href
register('data:text/javascript,' + encodeURIComponent(`
export async function resolve(specifier, context, nextResolve) {
  if (specifier.startsWith('@/')) {
    const rest = specifier.slice(2)
    return nextResolve(${JSON.stringify(srcRoot)} + (/\\.[a-z]+$/.test(rest) ? rest : rest + '.js'), context)
  }
  return nextResolve(specifier, context)
}
`))

const { graduationConflictMessage, isGraduationConflictResponse } = await import('../form-state.js')

test('业务规则拒绝（如答辩阶段未开放）直接显示真实原因，不说“记录已变化”', () => {
  const res = { code: 409001, status: 409, bizCode: 'DATA_CONFLICT', message: '当前批次答辩阶段未开放' }
  assert.equal(isGraduationConflictResponse(res), true)
  const text = graduationConflictMessage(res)
  assert.match(text, /答辩阶段未开放/)
  assert.doesNotMatch(text, /记录已发生变化/)
})

test('评委未全部评分时把未评分的人名带给秘书', () => {
  const text = graduationConflictMessage({ code: 409001, bizCode: 'DATA_CONFLICT', message: '答辩组评委尚未全部评分：张可欣' })
  assert.match(text, /张可欣/)
})

test('真正的版本冲突仍提示记录已变化并保留填写内容', () => {
  const text = graduationConflictMessage({ code: 409001, bizCode: 'VERSION_CONFLICT', message: '记录已被其他人更新' })
  assert.match(text, /记录已发生变化/)
  assert.match(text, /内容已保留/)
})
