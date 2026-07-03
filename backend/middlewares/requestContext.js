/**
 * 请求上下文中间件：为每个请求分配 requestId 并记录访问日志 — 移植自旧系统
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
