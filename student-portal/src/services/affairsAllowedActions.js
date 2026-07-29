import { portalApi } from './portalApi'

const has = (row, action, legacyKey = '') => {
  if (Array.isArray(row?.allowedActions)) return row.allowedActions.includes(action)
  return legacyKey ? !!row?.[legacyKey] : false
}

const hasAny = (row, actions, legacyKey = '') => {
  if (Array.isArray(row?.allowedActions)) return actions.some((action) => row.allowedActions.includes(action))
  return legacyKey ? !!row?.[legacyKey] : false
}

const project = (kind, data) => {
  const result = data && typeof data === 'object' ? data : {}
  const items = Array.isArray(result.items) ? result.items : []
  result.items = items.map((row) => {
    if (kind === 'leave') {
      return {
        ...row,
        canResubmit: hasAny(row, ['EDIT_RETURNED', 'RESUBMIT'], 'canResubmit'),
        canCancel: has(row, 'SUBMIT_CANCEL', 'canCancel'),
        canExtend: has(row, 'SUBMIT_EXTENSION', 'canExtend')
      }
    }
    if (kind === 'aid') {
      return {
        ...row,
        canResubmit: hasAny(row, ['EDIT_RETURNED', 'RESUBMIT'], 'canResubmit'),
        canObject: has(row, 'SUBMIT_OBJECTION', 'canObject')
      }
    }
    if (kind === 'funding') {
      return {
        ...row,
        canResubmit: hasAny(row, ['EDIT_RETURNED', 'RESUBMIT'], 'canResubmit'),
        canAppeal: has(row, 'SUBMIT_APPEAL', 'canAppeal')
      }
    }
    if (kind === 'discipline') {
      return { ...row, canAppeal: has(row, 'SUBMIT_APPEAL', 'canAppeal') }
    }
    return row
  })
  return result
}

const wrap = (name, kind) => {
  const original = portalApi[name]
  if (typeof original !== 'function' || original.__allowedActionsWrapped) return
  const wrapped = async (...args) => project(kind, await original(...args))
  wrapped.__allowedActionsWrapped = true
  portalApi[name] = wrapped
}

export function installAffairsAllowedActions() {
  wrap('affairsLeave', 'leave')
  wrap('affairsAid', 'aid')
  wrap('affairsFunding', 'funding')
  wrap('affairsDiscipline', 'discipline')
}

installAffairsAllowedActions()
