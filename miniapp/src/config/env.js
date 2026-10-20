/**
 * 运行环境开关。正式小程序和日常沙箱都只允许真实后端数据。
 * 网络、权限或字段错误必须如实展示可重试错误，不能回落成 mock 数据冒充成功。
 *
 * apiBaseUrl 只接受构建期环境变量 VITE_API_BASE_URL（只填源，勿带 /api）。
 * 生产构建没有显式 API 地址时直接失败，禁止把 localhost 开发地址编进正式包。
 * 本地真实后端联调请在 miniapp/.env 显式设置 VITE_API_BASE_URL。
 * 微信小程序无同源概念，正式环境必须使用可达的 HTTPS 绝对地址。
 */
const BUILD_PROD = import.meta.env.PROD
const BUILD_DEV = import.meta.env.DEV
const BUILD_API_BASE_URL = import.meta.env.VITE_API_BASE_URL
const BUILD_USE_MOCK = import.meta.env.VITE_USE_MOCK
const BUILD_PRIVACY_URL = import.meta.env.VITE_PRIVACY_URL
const BUILD_TERMS_URL = import.meta.env.VITE_TERMS_URL
const BUILD_HELP_CENTER_URL = import.meta.env.VITE_HELP_CENTER_URL

function resolveApiBaseUrl() {
  const v = BUILD_API_BASE_URL
  if (v) {
    let url = String(v).replace(/\/+$/, '')
    // 兼容误配：VITE 只填源，勿带 /api；若运维误填 .../api/v1 则剥离避免双前缀
    url = url.replace(/\/api\/v1$/i, '')
    // 生产构建强制 HTTPS：微信小程序正式环境禁止 http 明文请求，且明文会暴露 Bearer 令牌与
    // 全部 PII。非本机地址若误配为 http:// 一律升级为 https://（后端须挂 TLS/反代）。
    if (BUILD_PROD && /^http:\/\//i.test(url) && !/^http:\/\/(localhost|127\.0\.0\.1)(:|\/|$)/i.test(url)) {
      url = url.replace(/^http:\/\//i, 'https://')
    }
    // H5 本地开发通过 Vite /api 反代访问本机后端，保持浏览器会话、
    // HttpOnly Cookie 与 JSON 响应都在同源边界内。微信开发构建没有
    // window，仍保留显式绝对地址，不改变原生小程序网络契约。
    if (BUILD_DEV && typeof window !== 'undefined' && /^http:\/\/(localhost|127\.0\.0\.1)(:\d+)?$/i.test(url)) {
      return ''
    }
    return url
  }

  if (BUILD_PROD) {
    throw new Error('VITE_API_BASE_URL is required for production miniapp builds')
  }
  // 纯 mock 本地开发不需要 API；真实后端联调必须通过 .env 显式声明地址。
  return ''
}

/**
 * 保留 VITE_USE_MOCK 仅用于识别并拒绝过期配置，不能让正式页面离开真实 API。
 * 开发联调同样需要明确 VITE_API_BASE_URL 并启动日常沙箱；没有后端时显示错误态。
 */
function resolveUseMock() {
  // 生产构建的数据真实性是硬约束；日常沙箱也禁止任何演示成功路径。
  // 显式读取变量以便旧 .env 配置不再被静默忽略，但不允许它重新打开 mock。
  void BUILD_USE_MOCK
  return false
}

/**
 * 用户协议 / 隐私政策 / 统一帮助中心页面地址。
 * 协议正文仓库当前不存在公开路由，默认留空；帮助中心不硬编码 SaaS 域名，
 * 由 VITE_HELP_CENTER_URL 注入。生产环境的非本机 http 地址自动升级为 https。
 */
function resolveDocUrl(value) {
  try {
    if (!value) return ''
    let url = String(value).trim()
    if (BUILD_PROD && /^http:\/\//i.test(url) && !/^http:\/\/(localhost|127\.0\.0\.1)(:|\/|$)/i.test(url)) {
      url = url.replace(/^http:\/\//i, 'https://')
    }
    return url
  } catch (e) { return '' }
}

export const ENV = {
  // 始终 false：正式页面仅使用真实 API。
  useMock: resolveUseMock(),
  privacyUrl: resolveDocUrl(BUILD_PRIVACY_URL),
  termsUrl: resolveDocUrl(BUILD_TERMS_URL),
  // 小程序“帮助与反馈”唯一正文入口。正式环境配置 HTTPS /help 地址，并在微信公众平台登记对应业务域名。
  helpCenterUrl: resolveDocUrl(BUILD_HELP_CENTER_URL),
  // 不允许把网络、权限或后端错误伪装成演示成功。
  allowMockFallback: false,
  apiBaseUrl: resolveApiBaseUrl(),
  apiPrefix: '/api/v1',
  requestTimeout: 8000, // 校园弱网下 4s 偏紧；8s 内无响应按网络失败处理（读兜底/写明确报错）
  mockLatency: 260
}

export default ENV
