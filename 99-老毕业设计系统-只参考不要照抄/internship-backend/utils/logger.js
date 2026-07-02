/**
 * 轻量结构化日志（零依赖）
 * ───────────────────────────────────────────────────────────
 * - 生产环境(NODE_ENV=production)输出单行 JSON，便于被 ELK/Loki/CloudWatch 采集与检索；
 * - 开发环境输出带颜色的可读文本，方便本地排障。
 * - 通过 AsyncLocalStorage 自动带上当前请求的 requestId，串联一次请求内的所有日志。
 *
 * 用法：
 *   const logger = require('./utils/logger');
 *   logger.info('用户登录', { userId: 12 });
 *   logger.error('下载失败', { err: e.message });
 */
const { AsyncLocalStorage } = require('async_hooks');

const reqStore = new AsyncLocalStorage();

const LEVELS = { debug: 10, info: 20, warn: 30, error: 40 };
const MIN_LEVEL = LEVELS[(process.env.LOG_LEVEL || 'info').toLowerCase()] || LEVELS.info;
const IS_PROD = process.env.NODE_ENV === 'production';

const COLORS = { debug: '\x1b[90m', info: '\x1b[36m', warn: '\x1b[33m', error: '\x1b[31m', reset: '\x1b[0m' };

function currentRequestId() {
  const s = reqStore.getStore();
  return s ? s.requestId : undefined;
}

// 错误告警节流：避免错误风暴刷爆群机器人（默认全局每 60s 最多推一条）
let _lastAlertAt = 0;
const ALERT_MIN_GAP = Number(process.env.ALERT_MIN_GAP_MS || 60000);
function maybeAlert(msg, meta) {
  if (process.env.ALERT_ON_ERROR !== '1') return;
  const now = Date.now();
  if (now - _lastAlertAt < ALERT_MIN_GAP) return;
  _lastAlertAt = now;
  try {
    const gw = require('./groupWebhook');
    if (!gw.isConfigured()) return;
    const detail = meta && (meta.msg || meta.path || meta.reason) ? JSON.stringify(meta).slice(0, 300) : '';
    gw.push('🚨 系统错误告警', `${msg}${detail ? '\n' + detail : ''}\n时间：${new Date().toISOString()}`).catch(() => {});
  } catch (_) { /* 告警失败不影响日志 */ }
}

function emit(level, msg, meta) {
  if (LEVELS[level] < MIN_LEVEL) return;
  const requestId = currentRequestId();
  const time = new Date().toISOString();
  if (level === 'error') maybeAlert(msg, meta);

  if (IS_PROD) {
    const record = { time, level, msg, ...(requestId ? { requestId } : {}), ...(meta || {}) };
    const line = JSON.stringify(record);
    (level === 'error' ? process.stderr : process.stdout).write(line + '\n');
  } else {
    const rid = requestId ? ` \x1b[90m[${requestId}]\x1b[0m` : '';
    const extra = meta && Object.keys(meta).length ? ' ' + JSON.stringify(meta) : '';
    const out = `${COLORS[level]}${level.toUpperCase().padEnd(5)}${COLORS.reset}${rid} ${msg}${extra}`;
    (level === 'error' ? console.error : console.log)(out);
  }
}

module.exports = {
  reqStore,
  currentRequestId,
  debug: (msg, meta) => emit('debug', msg, meta),
  info: (msg, meta) => emit('info', msg, meta),
  warn: (msg, meta) => emit('warn', msg, meta),
  error: (msg, meta) => emit('error', msg, meta),
};
