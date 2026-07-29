const SENSITIVE_PREFIXES = [
  'aa-grade-entry-draft:'
]

export function clearSensitiveLocalDrafts() {
  try {
    const info = uni.getStorageInfoSync()
    const keys = Array.isArray(info && info.keys) ? info.keys : []
    keys.forEach((key) => {
      if (SENSITIVE_PREFIXES.some((prefix) => String(key).startsWith(prefix))) {
        uni.removeStorageSync(key)
      }
    })
  } catch (e) {
    // 退出登录继续执行；下一次进入敏感页面仍会以服务器数据为准。
  }
}

export { SENSITIVE_PREFIXES }
