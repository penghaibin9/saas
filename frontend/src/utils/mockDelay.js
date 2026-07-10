/**
 * Mock 响应延迟：开发环境为 0（跟手）；生产构建保留极短延迟以示加载态。
 * 各模块 API 的 ok()/fail() 统一引用，禁止各文件散落 DELAY = 120。
 */
export const MOCK_DELAY_MS =
  typeof import.meta !== 'undefined' && import.meta.env && import.meta.env.DEV ? 0 : 120
