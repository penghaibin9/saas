/**
 * 运行环境开关。P3：真实后端优先（失败自动回退 mock，不白屏）。
 * useMock=true 可整体回到纯 mock 演示模式。
 */
export const ENV = {
  useMock: false, // false=优先真实后端，失败回退 mock；true=纯 mock
  apiBaseUrl: 'http://localhost:8000', // 后端地址（mp-weixin 真机联调改为局域网 IP）
  apiPrefix: '/api/v1',
  requestTimeout: 4000,
  mockLatency: 260
}

export default ENV
