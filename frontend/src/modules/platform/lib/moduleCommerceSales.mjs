// Commercial amounts never pass through binary floating point arithmetic.
const MONEY = /^(?:0|[1-9]\d{0,9})(?:\.\d{1,2})?$/
const MAX_CENTS = 999999999999n
export function moneyCents(value) {
  if (typeof value !== 'string') throw new Error('金额必须使用十进制文本')
  const text = value
  if (!MONEY.test(text)) throw new Error('金额须为非负数，最多两位小数，不接受空值或科学计数法')
  const [whole, fraction = ''] = text.split('.')
  const cents = BigInt(whole) * 100n + BigInt(fraction.padEnd(2, '0'))
  if (cents > MAX_CENTS) throw new Error('金额超过合同字段上限')
  return cents
}
export function lineAmount(unitPrice, quantity, discount) {
  if (!Number.isSafeInteger(quantity) || quantity < 1 || quantity > 1000000) throw new Error('数量须为1至1000000的整数')
  const gross = moneyCents(unitPrice) * BigInt(quantity)
  const reduction = moneyCents(discount)
  if (gross > MAX_CENTS || reduction > gross) throw new Error('金额超限或优惠超过原价')
  const net = gross - reduction
  return `${net / 100n}.${String(net % 100n).padStart(2, '0')}`
}
export function localInputToUtc(value) {
  if (!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2})?$/.test(value || '')) throw new Error('请填写完整服务时间（北京时间）')
  const normalized = value.length === 16 ? `${value}:00` : value
  const date = new Date(`${normalized}+08:00`)
  if (!Number.isFinite(date.getTime()) || utcToLocalInput(date.toISOString()) !== normalized) throw new Error('服务时间不是有效日期')
  return date.toISOString().replace('.000Z', 'Z')
}
export function utcToLocalInput(value) {
  if (!value) return ''
  const ms = Date.parse(value)
  if (!Number.isFinite(ms)) throw new Error('服务截止时间无效，请刷新')
  return new Date(ms + 8 * 3600000).toISOString().slice(0, 19)
}
export function renewalInputFromUtc(value) {
  // MySQL legacy sources can retain microseconds; a second-resolution input must
  // round UP at a half-open renewal boundary, never overlap the already paid term.
  const ms = Date.parse(value)
  if (!Number.isFinite(ms)) throw new Error('续费截止时间无效')
  const fraction = /\.(\d+)(?:Z|[+-]\d{2}:\d{2})$/.exec(value)?.[1] || ''
  const ceiling = Math.floor(ms / 1000) * 1000 + (/[1-9]/.test(fraction) ? 1000 : 0)
  return utcToLocalInput(new Date(ceiling).toISOString())
}
export function newOrderAttempt(order, randomUUID = () => globalThis.crypto.randomUUID()) {
  return { key: `module-sale-${randomUUID()}`, order: JSON.parse(JSON.stringify(order)) }
}
export function restoreOrderAttempt(raw, tenantId) {
  if (!raw) return null
  const attempt = JSON.parse(raw)
  if (typeof attempt.key !== 'string' || attempt.key.length < 8 || attempt.key.length > 200 ||
      !attempt.order || attempt.order.tenantId !== tenantId || !Array.isArray(attempt.order.items)) {
    throw new Error('待核对订单记录无效，请先到订单台账人工核对；不要重复建单')
  }
  return attempt
}
export function isDefinitiveRejection(error) {
  // A 409 may describe a processing receipt, not a rejected creation.
  return error?.details?.salesCommandNotCommitted === true
}
