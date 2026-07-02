/**
 * 限流中间件
 * ───────────────────────────────────────────────────────────
 * · 默认：单进程内存计数（零依赖，适合单实例/演示）。
 * · 配置 REDIS_URL 且安装了 ioredis 时：自动切换为 Redis 计数，
 *   多实例/PM2 cluster 下共享配额，登录暴力破解阈值不会被进程数放大。
 *   Redis 异常时回退放行（fail-open，不因缓存故障拖垮业务），并告警。
 *
 * 环境变量：
 *   REDIS_URL   形如 redis://127.0.0.1:6379（缺省即内存模式）
 */

let _redis = null;
let _redisTried = false;
function getRedis() {
  if (!process.env.REDIS_URL) return null;
  if (_redisTried) return _redis;
  _redisTried = true;
  try {
    const Redis = require('ioredis');
    _redis = new Redis(process.env.REDIS_URL, { maxRetriesPerRequest: 2, lazyConnect: false });
    _redis.on('error', (e) => console.warn('⚠️  Redis 限流连接异常（将回退内存/放行）:', e.message));
    console.log('🧮 限流后端：Redis（多实例共享配额）');
    return _redis;
  } catch (e) {
    console.warn('⚠️  未安装 ioredis，限流回退内存模式：', e.message);
    return null;
  }
}

let _seq = 0;

function rateLimit({ windowMs = 15 * 60 * 1000, max = 20, message = '请求过于频繁，请稍后再试', keyPrefix } = {}) {
  const prefix = keyPrefix || `rl:${max}:${windowMs}:${++_seq}`;

  // —— 内存后端 ——
  const hits = new Map(); // ip -> { count, resetAt }
  const timer = setInterval(() => {
    const now = Date.now();
    for (const [key, rec] of hits) if (rec.resetAt <= now) hits.delete(key);
  }, windowMs);
  if (typeof timer.unref === 'function') timer.unref();

  function deny(res, retryAfterMs) {
    res.setHeader('Retry-After', Math.ceil(retryAfterMs / 1000));
    return res.status(429).json({ success: false, message, code: 429 });
  }

  return async (req, res, next) => {
    const ip = req.ip || req.socket?.remoteAddress || 'unknown';
    const redis = getRedis();

    if (redis) {
      try {
        const key = `${prefix}:${ip}`;
        const n = await redis.incr(key);
        if (n === 1) await redis.pexpire(key, windowMs);
        if (n > max) {
          let ttl = await redis.pttl(key);
          if (!(ttl > 0)) ttl = windowMs;
          return deny(res, ttl);
        }
        return next();
      } catch (e) {
        // Redis 故障：回退放行，避免缓存层拖垮主流程
        console.warn('限流(Redis)异常，本次放行:', e.message);
        return next();
      }
    }

    // —— 内存后端 ——
    const now = Date.now();
    let rec = hits.get(ip);
    if (!rec || rec.resetAt <= now) { rec = { count: 0, resetAt: now + windowMs }; hits.set(ip, rec); }
    rec.count += 1;
    if (rec.count > max) return deny(res, rec.resetAt - now);
    next();
  };
}

module.exports = rateLimit;
