/**
 * SECURITY-P0 · 导出确认 / 危险操作确认统一口径文案。
 * 页面已有 AppConfirmDialog 的，仅需把 message 换成本工具生成的文案；
 * 新导出入口建议直接使用 <AppExportConfirm>（components/common）。
 */

/** 导出安全确认文案（四点提醒，等保口径） */
export function buildExportConfirmMessage({ module = '', rowCount = 0, scopeLabel = '' } = {}) {
  const head = [
    module ? `【${module}】` : '',
    rowCount ? `本次将导出 ${rowCount} 条记录` : '本次导出包含学生信息',
    scopeLabel ? `（数据范围：${scopeLabel}）` : ''
  ].join('')
  return (
    head +
    '。请确认：\n' +
    '1. 导出数据包含学生个人信息，仅限工作用途使用；\n' +
    '2. 导出文件将附带操作人与时间水印；\n' +
    '3. 本次导出将记录审计日志（含操作人 / 时间 / 数据范围 / 用途）；\n' +
    '4. 严禁通过微信 / QQ 等即时通讯工具随意转发导出文件。'
  )
}

/** 危险操作确认文案（作废 / 停用 / 删除 / 批量处理 / 批量审批） */
export function buildDangerConfirmMessage({ action = '该操作', target = '', count = 0, extra = '' } = {}) {
  const scope = count > 1 ? `所选 ${count} 条记录` : target || '该记录'
  return (
    `确认对${scope}执行「${action}」？\n` +
    '该操作将写入审计留痕，责任可追溯；' +
    (extra ? extra + '；' : '') +
    '如为作废/停用类操作，均为逻辑处理、档案保留可追溯，不做物理删除。'
  )
}
