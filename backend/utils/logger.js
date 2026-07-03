/**
 * 轻量结构化日志（零依赖）— 移植自旧系统
 * ───────────────────────────────────────────────────────────
 * - 生产环境输出单行 JSON，便于 ELK/Loki/CloudWatch 采集；
 * - 开发环境输出带颜色文本；
 * - 通过 AsyncLocalStorage 自动带上当前请求 requestId，串联一次请求内所有日志。
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

function emit(level, msg, meta) {
  if (LEVELS[level] < MIN_LEVEL) return;
  const requestId = currentRequestId();
  const time = new Date().toISOString();

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
