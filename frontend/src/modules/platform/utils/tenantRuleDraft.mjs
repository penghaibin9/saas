/** RULES draft/receipt contracts. No authority, storage, or automatic write retries. */
const own = (value, key) => Object.hasOwn(value, key)
const record = value => value !== null && typeof value === 'object' && !Array.isArray(value)
const safeKey = key => !['__proto__', 'prototype', 'constructor'].includes(key)
export const cloneRules = value => JSON.parse(JSON.stringify(value))
export const equalRuleValue = (a, b) => JSON.stringify(a) === JSON.stringify(b)
function freeze(value) {
  if (value && typeof value === 'object') { Object.values(value).forEach(freeze); Object.freeze(value) }
  return value
}
export function ruleVersion(value) {
  if (typeof value !== 'number' && !(typeof value === 'string' && /^\d+$/.test(value))) return null
  const number = Number(value)
  return Number.isSafeInteger(number) && number >= 0 ? number : null
}
export function ruleKind(value) {
  if (typeof value === 'boolean') return 'boolean'
  if (typeof value === 'number' && Number.isSafeInteger(value) && value >= 0 && value <= 1000000) return 'integer'
  if (typeof value === 'string') return 'text'
  if (Array.isArray(value) && value.every(item => typeof item === 'string')) return 'list'
  return 'readonly'
}
export function rulesSnapshot(data, tenantId) {
  if (!/^[1-9]\d*$/.test(tenantId) || typeof data?.tenantId !== 'string' || data.tenantId !== tenantId) throw new Error('学校标识与当前对象不一致')
  if (ruleVersion(data.overrideVersion) === null || !record(data.rules) || !record(data.override)) throw new Error('规则、覆盖来源或版本未取得')
  for (const document of [data.rules, data.override]) {
    for (const [group, fields] of Object.entries(document)) {
      if (!safeKey(group) || !record(fields) || Object.keys(fields).some(key => !safeKey(key))) throw new Error('规则分组格式异常')
    }
  }
  return { tenantId, rules: cloneRules(data.rules), override: cloneRules(data.override), overrideVersion: ruleVersion(data.overrideVersion) }
}
export function editableDraft(rules) {
  const draft = cloneRules(rules)
  for (const fields of Object.values(draft)) {
    for (const [key, value] of Object.entries(fields)) if (ruleKind(value) === 'list') fields[key] = value.join('\n')
  }
  return draft
}
function typedValue(original, input) {
  switch (ruleKind(original)) {
    case 'boolean': if (typeof input === 'boolean') return input; break
    case 'integer': {
      const value = ruleVersion(input)
      if (value !== null && value <= 1000000) return value
      throw new Error('请输入 0–1000000 的整数，不能留空')
    }
    case 'text': if (typeof input === 'string') return input; break
    case 'list':
      // Do not normalize an untouched inherited list into a tenant override.
      if (input === original.join('\n')) return original
      if (typeof input === 'string') return input.split(/[,，\n]/).map(value => value.trim()).filter(Boolean)
      break
    case 'readonly': if (equalRuleValue(original, input)) return input; break
  }
  throw new Error('值的类型发生变化，不能提交')
}
export function ruleChanges(base, draft) {
  const patch = {}, changes = [], errors = {}
  if (!record(base) || !record(draft) || Object.keys(base).length !== Object.keys(draft).length) return { patch, changes, errors: { document: '规则结构已变化，请重新读取' } }
  for (const [group, fields] of Object.entries(base)) {
    if (!safeKey(group) || !record(fields) || !record(draft[group]) || Object.keys(fields).length !== Object.keys(draft[group]).length) { errors[group] = '规则分组已变化'; continue }
    for (const [key, before] of Object.entries(fields)) {
      const path = `${group}.${key}`
      try {
        if (!safeKey(key) || !own(draft[group], key)) throw new Error('规则项缺失')
        const after = typedValue(before, draft[group][key])
        if (!equalRuleValue(before, after)) {
          if (!own(patch, group)) patch[group] = {}
          patch[group][key] = after
          changes.push({ group, key, before: cloneRules(before), after: cloneRules(after) })
        }
      } catch (error) { errors[path] = error.message }
    }
  }
  return { patch, changes, errors }
}
export function prepareRules(snapshot, draft, reason) {
  const delta = ruleChanges(snapshot.rules, draft)
  if (Object.keys(delta.errors).length) throw new Error('请先修正规则中的输入错误')
  if (!delta.changes.length) throw new Error('没有需要提交的规则修改')
  if (typeof reason !== 'string' || reason.trim().length < 5 || reason.trim().length > 500) throw new Error('变更原因需为 5–500 个字符')
  return freeze(cloneRules({ tenantId: snapshot.tenantId, rules: delta.patch, expectedVersion: snapshot.overrideVersion, reason: reason.trim(), changes: delta.changes }))
}
export function compareRuleReadback(request, snapshot) {
  return request.changes.map(change => ({ ...change,
    current: snapshot.rules[change.group]?.[change.key],
    matches: own(snapshot.override[change.group] || {}, change.key) && equalRuleValue(snapshot.rules[change.group]?.[change.key], change.after) && equalRuleValue(snapshot.override[change.group]?.[change.key], change.after)
  }))
}
export function verifiedRulesReceipt(data, request) {
  const snapshot = rulesSnapshot(data, request.tenantId)
  if (snapshot.overrideVersion !== request.expectedVersion + 1 || compareRuleReadback(request, snapshot).some(item => !item.matches)) throw new Error('保存回执与本次修改不一致，请先核对当前配置')
  return snapshot
}
export function ruleValueLabel(value) {
  if (value === undefined) return '当前配置未包含此项'
  if (typeof value === 'boolean') return value ? '开启' : '关闭'
  if (Array.isArray(value)) return value.length ? value.join('、') : '空列表'
  if (value === '') return '空文本'
  return typeof value === 'object' ? '结构化配置（只读）' : String(value)
}
