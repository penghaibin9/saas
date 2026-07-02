/**
 * 查重 / AIGC 检测对接层（可插拔）
 *
 * 设计目标：避免"假功能冒充真功能"。
 *  - 若在 .env 配置了第三方查重服务（知网/维普/PaperPass 等代理网关），则真实调用；
 *  - 未配置时返回明确标记 is_demo=1 的演示结果，绝不伪装成权威检测数据。
 *
 * 环境变量：
 *   PLAGIARISM_API_URL   第三方检测网关地址（POST，接收 { fileUrl }，返回 { similarity, aigc, reportUrl }）
 *   PLAGIARISM_API_KEY   鉴权密钥（作为 Bearer Token）
 *   PLAGIARISM_TIMEOUT   超时毫秒，默认 20000
 */

function isConfigured() {
  return !!process.env.PLAGIARISM_API_URL;
}

async function callProvider(fileUrl) {
  const url = process.env.PLAGIARISM_API_URL;
  const timeout = Number(process.env.PLAGIARISM_TIMEOUT || 20000);
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeout);
  try {
    const res = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(process.env.PLAGIARISM_API_KEY ? { Authorization: 'Bearer ' + process.env.PLAGIARISM_API_KEY } : {})
      },
      body: JSON.stringify({ fileUrl }),
      signal: controller.signal
    });
    if (!res.ok) throw new Error('查重服务返回 HTTP ' + res.status);
    const data = await res.json();
    const similarity = Number(data.similarity);
    const aigc = data.aigc != null ? Number(data.aigc) : null;
    if (Number.isNaN(similarity)) throw new Error('查重服务返回数据格式不正确');
    return {
      similarity,
      aigc,
      reportUrl: data.reportUrl || data.report_url || null,
      provider: data.provider || 'external',
      isDemo: false
    };
  } finally {
    clearTimeout(timer);
  }
}

/**
 * 运行检测。返回 { similarity, aigc, reportUrl, provider, isDemo }
 * - 真实模式：调用第三方；失败则抛错（由上层决定是否降级）。
 * - 演示模式：返回随机区间结果但 isDemo=true，调用方需如实展示"演示数据"。
 */
async function detect(fileUrl) {
  if (isConfigured()) {
    return callProvider(fileUrl);
  }
  // 演示模式：明确标记，不冒充真实检测
  return {
    similarity: Math.round(5 + Math.random() * 25),
    aigc: Math.round(Math.random() * 15),
    reportUrl: null,
    provider: 'demo',
    isDemo: true
  };
}

module.exports = { detect, isConfigured };
