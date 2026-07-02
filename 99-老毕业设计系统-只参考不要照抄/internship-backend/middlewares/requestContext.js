/**
 * 请求上下文中间件：为每个请求分配 requestId 并记录访问日志。
 * - requestId 取自上游 X-Request-Id（反代/网关透传）或自动生成，并回写到响应头，便于全链路排查；
 * - 在 AsyncLocalStorage 中承载，使该请求生命周期内的所有 logger 调用自动带上同一 requestId；
 * - 响应结束后输出一条访问日志（方法/路径/状态码/耗时/IP/用户），不阻塞业务。
 */
const crypto = require('crypto');
const logger = require('../utils/logger');

function requestContext(req, res, next) {
  const requestId = (req.headers['x-request-id'] || '').toString().slice(0, 64) || crypto.randomBytes(8).toString('hex');
  res.setHeader('X-Request-Id', requestId);

  const start = process.hrtime.bigint();
  res.on('finish', () => {
    const ms = Number(process.hrtime.bigint() - start) / 1e6;
    const level = res.statusCode >= 500 ? 'error' : res.statusCode >= 400 ? 'warn' : 'info';
    logger[level]('http_access', {
      method: req.method,
      path: req.originalUrl || req.url,
      status: res.statusCode,
      durationMs: Math.round(ms),
      ip: req.ip,
      userId: req.user && req.user.id,
    });
  });

  logger.reqStore.run({ requestId }, next);
}

module.exports = { requestContext };
