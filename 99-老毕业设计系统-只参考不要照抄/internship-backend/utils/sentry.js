/**
 * Sentry 错误采集适配（可选）
 * 配置 SENTRY_DSN 且安装了 @sentry/node 时启用；否则 capture 为空操作，不阻断。
 */
let _sentry = null;
let _inited = false;

function init() {
  if (_inited) return _sentry;
  _inited = true;
  if (!process.env.SENTRY_DSN) return null;
  try {
    const Sentry = require('@sentry/node');
    Sentry.init({
      dsn: process.env.SENTRY_DSN,
      environment: process.env.NODE_ENV || 'development',
      tracesSampleRate: Number(process.env.SENTRY_TRACES_RATE || 0),
    });
    _sentry = Sentry;
    console.log('🛰️  Sentry 已启用');
  } catch (e) {
    console.warn('⚠️  配置了 SENTRY_DSN 但未安装 @sentry/node，错误采集降级关闭：', e.message);
  }
  return _sentry;
}

function capture(err, context) {
  if (!_sentry) return;
  try {
    if (context) _sentry.captureException(err, { extra: context });
    else _sentry.captureException(err);
  } catch (_) { /* 采集失败不影响主流程 */ }
}

function configured() { return !!_sentry; }

module.exports = { init, capture, configured };
