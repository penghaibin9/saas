// Store only an unresolved-operation marker, never credentials or business drafts.
// It survives page reloads; only a definitive API outcome can remove it.
const prefix = 'aa-pc-b-unconfirmed:'
export function readUnconfirmedWrite(key) {
  const value = sessionStorage.getItem(prefix + key)
  return value ? JSON.parse(value) : null
}
export function markUnconfirmedWrite(key, marker) {
  sessionStorage.setItem(prefix + key, JSON.stringify(marker))
}
export function clearUnconfirmedWrite(key) {
  sessionStorage.removeItem(prefix + key)
}
export function isDefiniteWriteRejection(result) {
  const code = Number(result?.code)
  // The adapter preserves business codes but discards transport metadata.
  // Timeouts, malformed envelopes and server failures cannot prove rollback.
  return (code >= 400 && code < 500 && code !== 408) ||
    (code >= 400000 && code < 500000 && Math.floor(code / 1000) !== 408)
}
