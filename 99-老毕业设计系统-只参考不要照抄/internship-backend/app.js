require('dotenv').config();

const express = require('express');
const cors = require('cors');
const multer = require('multer');
const path = require('path');
const fs = require('fs');

const { testConnection } = require('./config/db');
const tenancy = require('./config/tenancy');
const { tenantMiddleware } = require('./middlewares/tenant');
const { authMiddleware } = require('./middlewares/auth');
const { requestContext } = require('./middlewares/requestContext');
const logger = require('./utils/logger');
const metrics = require('./utils/metrics');
const sentry = require('./utils/sentry');
sentry.init();
const apiRoutes = require('./routes');

const app = express();
const PORT = process.env.PORT || 3000;

// 反向代理后(如 Nginx)能正确识别客户端 IP，限流才准确
app.set('trust proxy', 1);

// 请求上下文：分配 requestId + 访问日志（尽早挂载，使全链路日志可串联）
app.use(requestContext);
// 指标采集（Prometheus）
app.use(metrics.middleware);

// /metrics 暴露给 Prometheus 抓取（可用 METRICS_TOKEN 做简单保护）
app.get('/metrics', (req, res) => {
  if (process.env.METRICS_TOKEN && req.query.token !== process.env.METRICS_TOKEN) {
    return res.status(401).send('unauthorized');
  }
  res.setHeader('Content-Type', 'text/plain; version=0.0.4; charset=utf-8');
  res.send(metrics.render());
});

// CORS：通过 CORS_ORIGIN 配置允许的来源（逗号分隔）；未配置时开发环境放开
const allowedOrigins = (process.env.CORS_ORIGIN || '')
  .split(',')
  .map((s) => s.trim())
  .filter(Boolean);
app.use(cors({
  origin: allowedOrigins.length ? allowedOrigins : true,
  credentials: true
}));

// 基础安全响应头（零依赖，等价于 helmet 的核心项）
app.use((req, res, next) => {
  res.setHeader('X-Content-Type-Options', 'nosniff');
  res.setHeader('X-Frame-Options', 'DENY');
  res.setHeader('Referrer-Policy', 'no-referrer');
  // 内容安全策略：XSS 纵深防御。页面为同源单文件 + 内联脚本/样式，故放开 'unsafe-inline'；
  // 但限制脚本仅来自本站，禁止外部脚本注入与 <base>/对象嵌入，缩小 innerHTML 型 XSS 的爆炸半径。
  res.setHeader(
    'Content-Security-Policy',
    "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; connect-src 'self'; font-src 'self' data:; object-src 'none'; base-uri 'self'; frame-ancestors 'none'"
  );
  res.removeHeader('X-Powered-By');
  next();
});

// 限制请求体大小，缓解超大 JSON 造成的内存压力
app.use(express.json({ limit: '1mb' }));
app.use(express.urlencoded({ extended: true, limit: '1mb' }));

const uploadsDir = path.join(__dirname, 'uploads');
if (!fs.existsSync(uploadsDir)) {
  fs.mkdirSync(uploadsDir);
}

const frontendDir = path.join(__dirname, 'frontend');
const hasFrontend = fs.existsSync(path.join(frontendDir, 'index.html'));

// 根路径：统一跳转到唯一管理端入口 /admin（web/管理平台.html）
app.get('/', (req, res) => res.redirect('/admin'));

// 同源托管 web/ 目录管理端页面：管理平台 / 迎检大屏 / 演示UI。
// 这样从浏览器以 http://localhost:3000/... 访问，避免 file:// 打开时的跨域、弹窗拦截等问题。
const rootDir = path.join(__dirname, '..', 'web');
const ROOT_PAGES = {
  '/admin': '管理平台.html',     '/管理平台.html': '管理平台.html',
  '/screen': '数据大屏.html',    '/数据大屏.html': '数据大屏.html',
  '/demo': '演示UI.html',        '/演示UI.html': '演示UI.html',
  '/flow': '业务流程演练.html',  '/业务流程演练.html': '业务流程演练.html',
  '/platform': '平台运营.html',  '/平台运营.html': '平台运营.html',
};
app.use((req, res, next) => {
  if (req.method !== 'GET') return next();
  let p;
  try { p = decodeURIComponent(req.path); } catch { p = req.path; }
  const file = ROOT_PAGES[p];
  if (file) {
    const fp = path.join(rootDir, file);
    if (fs.existsSync(fp)) return res.sendFile(fp);
  }
  next();
});

// 手机端 H5（学生/教师/企业移动页面），同源托管于 web/m
const mobileDir = path.join(rootDir, 'm');
if (fs.existsSync(mobileDir)) app.use('/m', express.static(mobileDir));

// 上传材料可能包含行踪照片、知情书、鉴定表等敏感信息，禁止匿名静态访问。
// 前端必须携带 Bearer token 下载；记录级归属校验由后续统一文件网关继续收紧。
app.use('/uploads', tenantMiddleware, authMiddleware, express.static(uploadsDir, {
  fallthrough: true,
  setHeaders(res) {
    res.setHeader('Cache-Control', 'private, no-store');
    res.setHeader('Content-Disposition', 'inline');
  }
}));
const docsDir = path.join(__dirname, 'docs');
if (fs.existsSync(docsDir)) app.use('/docs', express.static(docsDir));
if (fs.existsSync(frontendDir)) {
  app.use((req, res, next) => {
    if (req.method === 'GET' && /\.html?$/.test(req.path)) {
      res.setHeader('Cache-Control', 'no-store, no-cache, must-revalidate');
      res.setHeader('Pragma', 'no-cache');
    }
    next();
  });
  app.use(express.static(frontendDir));
}
// SaaS 平台运营控制台（跨租户，不经租户路由；凭 PLATFORM_ADMIN_TOKEN）。
// 必须在 /api 租户路由之前注册，使 /api/platform/* 优先命中且不被租户中间件拦截。
const { requirePlatformAdmin } = require('./middlewares/platformAuth');
app.use('/api/platform', requirePlatformAdmin, require('./routes/platformRoutes'));

// OpenAPI 契约 + Swagger UI（招投标/对接交付）。须在 /api 租户路由前注册，避免被租户中间件吞掉。
app.get('/api/openapi.json', (req, res) => {
  const base = `${req.get('x-forwarded-proto') || req.protocol}://${req.get('host')}`;
  res.json(require('./openapi/spec')(base));
});
app.get('/api/docs', (req, res) => {
  res.setHeader('Content-Type', 'text/html; charset=utf-8');
  res.send(`<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8"><title>API 文档 · 实习管理平台</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="stylesheet" href="https://unpkg.com/swagger-ui-dist@5/swagger-ui.css"></head>
<body><div id="swagger-ui"></div>
<script src="https://unpkg.com/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
<script>window.ui=SwaggerUIBundle({url:'/api/openapi.json',dom_id:'#swagger-ui',persistAuthorization:true});</script>
</body></html>`);
});

// 租户解析：single 模式恒为默认库（零行为变化）；multi 模式按学校路由到独立库
// API 版本化：/api/v1 为规范版本；/api 旧路径并存过渡（带弃用响应头），未来不兼容变更走 /api/v2
const deprecationNotice = (req, res, next) => {
  // 注意：HTTP 头值须为 latin1，不能含中文
  res.setHeader('Deprecation', 'true');
  res.setHeader('Warning', '299 - "Deprecated: use /api/v1 instead of /api"');
  res.setHeader('Link', '</api/v1>; rel="successor-version"');
  next();
};
app.use('/api/v1', tenantMiddleware, apiRoutes);
app.use('/api', deprecationNotice, tenantMiddleware, apiRoutes);

// SPA 前端路由兜底（Express 5 下避免使用 '*' 通配路由）
if (fs.existsSync(frontendDir)) {
  app.use((req, res, next) => {
    if (req.method !== 'GET' || req.path.startsWith('/api') || req.path.startsWith('/uploads')) {
      return next();
    }
    const indexFile = path.join(frontendDir, 'index.html');
    if (fs.existsSync(indexFile)) {
      res.setHeader('Cache-Control', 'no-store, no-cache, must-revalidate');
      res.setHeader('Pragma', 'no-cache');
      return res.sendFile(indexFile);
    }
    next();
  });
}

app.use((req, res) => {
  res.status(404).json({
    success: false,
    message: '接口不存在',
    code: 404
  });
});

// 全局错误处理：业务异常(AppError)按其状态返回；上传错误 400；其余在生产不泄露细节
app.use((err, req, res, next) => {
  // 业务异常：Service/Domain 抛出的 AppError，按状态码统一出格式（属预期错误，记 warn 不报警）
  if (err && err.isAppError) {
    logger.warn('app_error', { code: err.code, msg: err.message, path: req.originalUrl });
    return res.status(err.status || 400).json({ success: false, code: err.code, message: err.message, data: err.data || undefined });
  }
  logger.error('unhandled_error', { msg: err && err.message, stack: err && err.stack, path: req.originalUrl });
  sentry.capture(err, { path: req.originalUrl, method: req.method });
  if (err instanceof multer.MulterError) {
    return res.status(400).json({ success: false, message: '文件上传失败：' + err.message, code: 400 });
  }
  if (err && typeof err.message === 'string' &&
      (err.message.includes('仅支持') || err.message.includes('不支持的文件格式') || err.message.includes('格式'))) {
    return res.status(400).json({ success: false, message: err.message, code: 400 });
  }
  const message = process.env.NODE_ENV === 'production'
    ? '服务器内部错误'
    : (err.message || '服务器内部错误');
  res.status(500).json({ success: false, message, code: 500 });
});

const server = app.listen(PORT, async () => {
  await testConnection();
  // 兜底确保审计日志表存在（即使未单独跑迁移脚本也能记录），失败不阻断启动
  try {
    await require('./models/auditLogModel').ensureTable();
    await require('./models/systemConfigModel').ensureTable();
    await require('./models/workflowConfigModel').ensureTable();
    await require('./models/filingModel').ensureTable();
    await require('./models/benchmarkModel').ensureTables();
    // 新增商业化功能表（实习报酬台账 / 家长在线签署），失败不阻断启动
    await require('./models/stipendModel').ensureTable();
    await require('./models/guardianModel').ensureTable();
    await require('./models/aiUsageModel').ensureTable();
    await require('./models/checkinModel').ensureAntiCheatColumns();
    await require('./models/permModel').ensureTables();
    await require('./models/workflowModel').ensureTables();
    // SaaS 租户注册表 + 控制面表（套餐/用量/事件，master 库）+ 预热租户缓存；single 模式下无副作用
    await require('./models/tenantModel').ensureTable();
    await tenancy.loadTenants();
  } catch (e) {
    console.warn('⚠️  审计日志表初始化失败（不影响服务启动）:', e.message);
  }
  console.log(`🏷️  租户模式：${tenancy.MODE}（single=私有化单库 / multi=SaaS多库）`);
  // 启动定时任务（保险到期/未投保每日扫描），失败不阻断启动
  try {
    require('./utils/scheduler').start();
  } catch (e) {
    console.warn('⚠️  定时任务启动失败（不影响服务启动）:', e.message);
  }
  console.log(`🚀 服务器运行在 http://localhost:${PORT}`);
});

// 优雅退出：收到 PM2/Docker 的停止信号时，先停收新请求，排空在途请求，
// 再关闭数据库连接池与定时任务，最后退出。避免重启/部署时硬杀导致请求中断、连接泄漏。
let shuttingDown = false;
async function gracefulShutdown(signal) {
  if (shuttingDown) return;
  shuttingDown = true;
  console.log(`\n📴 收到 ${signal}，开始优雅退出…`);

  // 兜底：若 10s 内未能正常关闭则强制退出，防止挂起
  const forceTimer = setTimeout(() => {
    console.error('⏱️  优雅退出超时，强制结束进程');
    process.exit(1);
  }, 10000);
  if (typeof forceTimer.unref === 'function') forceTimer.unref();

  try {
    try { require('./utils/scheduler').stop?.(); } catch (_) {}
    await new Promise((resolve) => server.close(resolve)); // 停止接收新连接并等待在途请求完成
    await tenancy.closeAllPools();                          // 排空所有租户/控制面连接池
    clearTimeout(forceTimer);
    console.log('✅ 已优雅退出');
    process.exit(0);
  } catch (e) {
    console.error('优雅退出过程中出错：', e.message);
    process.exit(1);
  }
}
['SIGTERM', 'SIGINT'].forEach((sig) => process.on(sig, () => gracefulShutdown(sig)));

// 兜底记录未捕获异常/未处理的 Promise 拒绝，避免静默崩溃，便于线上排障
process.on('unhandledRejection', (reason) => {
  logger.error('unhandled_rejection', { reason: reason && (reason.stack || reason.message || String(reason)) });
  sentry.capture(reason instanceof Error ? reason : new Error(String(reason)));
});
process.on('uncaughtException', (err) => {
  logger.error('uncaught_exception', { msg: err && err.message, stack: err && err.stack });
  sentry.capture(err);
});

module.exports = { app, server };
