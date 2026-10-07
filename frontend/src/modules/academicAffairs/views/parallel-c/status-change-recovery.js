const recoveryRefs = new Map()

const keyOf = (identity, studentId) => `${identity}\u0000${studentId}`
const text = value => value == null ? '' : String(value)

export function rememberStatusChangeRecovery(identity, command) {
  const studentId = text(command?.studentId)
  const idempotencyKey = text(command?.body?.idempotencyKey)
  if (!identity || !studentId || !idempotencyKey) return null
  const previous = recoveryRefs.get(keyOf(identity, studentId)) || {}
  const ref = {
    studentId,
    idempotencyKey,
    acceptedChangeId: text(command?.id ?? previous.acceptedChangeId),
    changeType: text(command?.body?.changeType),
    toMajorId: text(command?.body?.toMajorId),
    toClassId: text(command?.body?.toClassId),
    effectiveDate: text(command?.body?.effectiveDate),
    materialFileIds: Array.isArray(command?.body?.materialFileIds) ? command.body.materialFileIds.map(text) : [],
    verified: command?.verified === true || previous.verified === true,
    lookupPage: Number.isInteger(command?.lookupPage) && command.lookupPage > 0 ? command.lookupPage : (previous.lookupPage || 1)
  }
  recoveryRefs.set(keyOf(identity, studentId), ref)
  return {...ref, materialFileIds:[...ref.materialFileIds]}
}

export function getStatusChangeRecovery(identity, studentId) {
  const ref = recoveryRefs.get(keyOf(identity, text(studentId)))
  return ref ? {...ref, materialFileIds:[...ref.materialFileIds]} : null
}

export function clearStatusChangeRecovery(identity, studentId) {
  recoveryRefs.delete(keyOf(identity, text(studentId)))
}

export function clearStatusChangeRecoveryForTests() {
  recoveryRefs.clear()
}
