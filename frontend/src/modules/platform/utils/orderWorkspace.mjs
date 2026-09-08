/** Commercial UI contracts. The existing order service remains the only writer. */
import { wholeNumber } from './tenantWorkspace.mjs'

const ORDER_STATES = new Set(['unpaid', 'paid', 'cancelled', 'refunded'])
export const orderId = value => typeof value === 'string' && /^[1-9]\d*$/.test(value) ? value : null
export const orderNumber = value => typeof value === 'string' && /^[A-Za-z0-9_-]{1,100}$/.test(value) ? value : null
export const orderVersion = value => { const n = wholeNumber(value); return n !== null && n > 0 ? n : null }
export function orderScope(query = {}) {
  if (query.tenantId != null && query.tenantId !== '' && !orderId(query.tenantId)) throw new Error('学校标识无效，已停止读取，避免误查全部学校')
  if (query.status != null && query.status !== '' && !ORDER_STATES.has(query.status)) throw new Error('订单筛选条件无效')
  if (query.keyword != null && typeof query.keyword !== 'string') throw new Error('搜索词无效')
  return { tenantId: query.tenantId || '', status: query.status || '', keyword: (query.keyword || '').trim().slice(0, 100) }
}
export function orderRows(data, scope = {}) {
  if (!data || !Array.isArray(data.list)) throw new Error('订单清单未完整取得')
  const seen = new Set()
  for (const row of data.list) {
    if (!row || !orderId(row.tenantId) || !orderNumber(row.orderNo) || seen.has(row.orderNo)) throw new Error('订单或学校标识异常，已停止展示')
    if ((scope.tenantId && row.tenantId !== scope.tenantId) || (scope.status && row.status !== scope.status)) throw new Error('返回的订单不属于当前查询范围')
    seen.add(row.orderNo)
  }
  if (data.total != null && wholeNumber(data.total) !== data.list.length) throw new Error('订单清单尚未完整返回，不能据此统计')
  return data.list.map(row => ({ ...row }))
}
export function cents(value) {
  if (typeof value !== 'string' && typeof value !== 'number') return null
  const text = String(value)
  if (!/^\d{1,10}(\.\d{1,2})?$/.test(text)) return null
  const [whole, fraction = ''] = text.split('.')
  return Number(whole) * 100 + Number(fraction.padEnd(2, '0'))
}
export function moneyLabel(value) {
  const amount = cents(value)
  return amount === null ? '金额未取得' : `￥${(amount / 100).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
}
export function orderStatus(row) {
  if (row.status === 'paid') {
    if (row.repairTaskRequired === true) return { label: '已支付 · 激活待修复', tone: 'warning' }
    if (row.activationState === 'ACTIVE' && row.repairTaskRequired === false) return { label: '已支付 · 已激活', tone: 'success' }
    return { label: '已支付 · 激活待核验', tone: 'warning' }
  }
  return ({ unpaid: { label: '待支付', tone: 'warning' }, cancelled: { label: '已取消', tone: 'default' }, refunded: { label: '已退款', tone: 'default' } })[row.status] || { label: '状态待核验', tone: 'warning' }
}
export function orderActions(row) {
  if (!orderNumber(row?.orderNo) || !orderId(row?.tenantId) || orderVersion(row.version) === null) return []
  if (row.status === 'unpaid') return ['mark-paid', 'cancel']
  return row.status === 'paid' && row.repairTaskRequired === true ? ['repair-activation'] : []
}
export function createOrderDraft(form, tenants, packages) {
  const school = tenants.find(row => row.tenantId === form.tenantId)
  const plan = packages.find(row => row.packageCode === form.packageCode && row.packageCode !== 'trial' && row.enabled !== false)
  if (!orderId(form.tenantId) || !school || !plan) throw new Error('请选择已读取的学校与正式套餐')
  const amount = cents(form.amount), days = wholeNumber(form.durationDays)
  if (amount === null || amount < 1 || amount > 999999999999) throw new Error('订单金额需大于零，最多两位小数')
  if (days === null || days < 1 || days > 3650) throw new Error('服务期需为 1–3650 天的整数')
  if (!['NEW', 'RENEW', 'UPGRADE'].includes(form.orderType)) throw new Error('请选择有效的订单类型')
  if (typeof form.remark !== 'string' || form.remark.length > 500) throw new Error('订单备注不能超过 500 个字符')
  return Object.freeze({ tenantId: form.tenantId, packageCode: form.packageCode, orderType: form.orderType,
    durationDays: days, amount: `${Math.floor(amount / 100)}.${String(amount % 100).padStart(2, '0')}`, remark: form.remark.trim() })
}
export function actionDraft(row, action, reason) {
  if (!orderActions(row).includes(action)) throw new Error('订单当前状态或版本不支持此操作，请重新读取')
  if (typeof reason !== 'string' || reason.trim().length < 5 || reason.trim().length > 500) throw new Error('请填写 5–500 个字符的变更原因')
  return Object.freeze({ orderNo: row.orderNo, tenantId: row.tenantId, action,
    expectedVersion: orderVersion(row.version), reason: reason.trim() })
}
export function orderReceipt(data, prepared) {
  if (!data || !orderNumber(data.orderNo) || orderVersion(data.version) === null) throw new Error('未取得完整的订单回执')
  if (prepared.kind === 'create') {
    if (data.status !== 'unpaid' || !orderId(data.orderId)) throw new Error('新订单回执异常，请先核对订单清单')
    return { ...data, result: 'created' }
  }
  const request = prepared.request
  if (data.orderNo !== request.orderNo) throw new Error('返回订单与本次操作不一致')
  if (request.action === 'cancel') {
    if (data.status !== 'cancelled' || orderVersion(data.version) !== request.expectedVersion + 1) throw new Error('取消回执版本或状态不一致')
    return { ...data, result: 'cancelled' }
  }
  if (data.status !== 'paid' || typeof data.tenantActivated !== 'boolean' || typeof data.repairTaskRequired !== 'boolean' || data.tenantActivated === data.repairTaskRequired) throw new Error('支付与激活回执不完整')
  const increment = request.action === 'mark-paid' && data.tenantActivated ? 2 : 1
  if (orderVersion(data.version) !== request.expectedVersion + increment) throw new Error('订单回执版本与本次变更不一致')
  if (request.action === 'repair-activation' && !data.tenantActivated) throw new Error('尚未确认激活修复成功')
  return { ...data, result: data.tenantActivated ? 'activated' : 'paid-pending' }
}
