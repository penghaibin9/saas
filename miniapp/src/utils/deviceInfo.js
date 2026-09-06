/**
 * 微信已将 getSystemInfoSync 拆分为更小的同步 API。集中封装避免页面重复调用
 * 已弃用接口，也让 H5/旧运行时在能力缺失时安全降级。
 */
export function getStatusBarHeight(fallback = 20) {
  try {
    if (typeof uni.getWindowInfo !== 'function') return fallback
    return Number(uni.getWindowInfo().statusBarHeight || fallback)
  } catch (error) {
    return fallback
  }
}

export function getDeviceDigest() {
  try {
    const device = typeof uni.getDeviceInfo === 'function' ? uni.getDeviceInfo() : {}
    const app = typeof uni.getAppBaseInfo === 'function' ? uni.getAppBaseInfo() : {}
    return [device.platform, device.model, device.system, app.appVersion]
      .filter(Boolean)
      .join('|') || 'miniapp-device'
  } catch (error) {
    return 'miniapp-device'
  }
}
