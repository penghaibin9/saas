const COS_SDK_VERSION = '1.10.1'
const COS_SDK_URL = `https://cdn.jsdelivr.net/npm/cos-js-sdk-v5@${COS_SDK_VERSION}/dist/cos-js-sdk-v5.min.js`
let sdkPromise = null

/**
 * 腾讯官方浏览器 SDK 单例加载器。
 * 固定版本，禁止业务页面自行拼 CDN 地址；阶段 10 有可用制品通道后迁移为同源静态文件。
 */
export function loadCosBrowserSdk() {
  if (typeof window === 'undefined') return Promise.reject(new Error('COS SDK 仅支持浏览器环境'))
  if (window.COS) return Promise.resolve(window.COS)
  if (sdkPromise) return sdkPromise
  sdkPromise = new Promise((resolve, reject) => {
    const existing = document.querySelector(`script[data-cos-sdk-version="${COS_SDK_VERSION}"]`)
    const script = existing || document.createElement('script')
    const done = () => {
      if (window.COS) resolve(window.COS)
      else reject(new Error('腾讯云 COS SDK 加载完成但未暴露 COS 构造器'))
    }
    script.addEventListener('load', done, { once: true })
    script.addEventListener('error', () => reject(new Error('腾讯云 COS SDK 加载失败，请检查网络或 CSP')), { once: true })
    if (!existing) {
      script.src = COS_SDK_URL
      script.async = true
      script.crossOrigin = 'anonymous'
      script.dataset.cosSdkVersion = COS_SDK_VERSION
      document.head.appendChild(script)
    }
  }).catch((error) => {
    sdkPromise = null
    throw error
  })
  return sdkPromise
}

export { COS_SDK_URL, COS_SDK_VERSION }
