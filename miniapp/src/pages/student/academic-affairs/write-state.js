export function isUncertainWriteError(error) {
  if (!error) return true
  const code = String(error.code || error.errorCode || error.statusCode || '').trim().toUpperCase()
  const httpStatus = Number(error.httpStatus || error.statusCode || error.code)
  if (httpStatus >= 500 || httpStatus === 408 || httpStatus === 429) return true
  const message = String(error.message || error.errMsg || '').toLowerCase()
  if (['408', '429', 'TIMEOUT', 'NETWORK_ERROR', 'REQUEST_TIMEOUT'].includes(code)) return true
  if (/timeout|timed out|network|连接|超时|断开|request:fail/.test(message)) return true
  return !error.biz
}

export function modalConfirm(options) {
  return new Promise((resolve) => {
    uni.showModal({
      ...options,
      success: (result) => resolve(result || { confirm: false }),
      fail: () => resolve({ confirm: false })
    })
  })
}
