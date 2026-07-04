/**
 * 运行环境开关。V1 固定使用 mock，不接真实后端、不连数据库。
 */
export const ENV = {
  useMock: true, // 是否使用 mock 数据（V1 恒为 true）
  apiBaseUrl: '', // 预留：真实后端地址
  mockLatency: 260 // mock 模拟网络延迟(ms)
}

export default ENV
