import COS from 'cos-js-sdk-v5'

const COS_SDK_VERSION = '1.10.1'

/**
 * 腾讯官方浏览器 SDK 单例加载器。
 * SDK 由 npm lockfile 固定并随管理 PC 制品构建，不再在运行时注入第三方 CDN 脚本。
 */
export function loadCosBrowserSdk() {
  if (typeof window === 'undefined') return Promise.reject(new Error('COS SDK 仅支持浏览器环境'))
  if (typeof COS !== 'function') return Promise.reject(new Error('腾讯云 COS SDK 构造器不可用'))
  return Promise.resolve(COS)
}

export { COS_SDK_VERSION }
