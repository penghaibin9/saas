/**
 * 分布式锁（基于数据库行锁，跨进程/多实例安全）
 * ───────────────────────────────────────────────────────────
 * 解决「PM2 cluster / 多实例下 setInterval 定时任务每个进程都跑一遍」的问题：
 * 同一时刻只有抢到锁的实例执行，避免重复扫描/重复发通知。
 *
 * 用 t_scheduler_lock 行 + 过期时间实现：每次执行前 tryAcquire，
 * 抢到才跑；锁带 TTL，持锁实例崩溃后到期自动释放，其他实例可接管。
 * 不依赖 Redis；锁落在默认库（控制面），与定时任务运行库一致。
 */
const tenancy = require('../config/tenancy');
const os = require('os');

const OWNER = `${os.hostname()}#${process.pid}`;
let _ensured = false;

async function ensureTable(pool) {
  if (_ensured) return;
  await pool.query(`
    CREATE TABLE IF NOT EXISTS t_scheduler_lock (
      name VARCHAR(64) PRIMARY KEY,
      owner VARCHAR(128) NULL,
      locked_until DATETIME NULL,
      update_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='分布式定时任务锁'
  `);
  _ensured = true;
}

/**
 * 尝试获取锁。抢到返回 true。
 * @param {string} name 锁名
 * @param {number} ttlSec 持锁有效期（秒），到期自动失效
 */
async function tryAcquire(name, ttlSec = 300) {
  const pool = tenancy.getDefaultPool();
  await ensureTable(pool);
  // 确保行存在（首次）
  await pool.query('INSERT IGNORE INTO t_scheduler_lock (name, owner, locked_until) VALUES (?, ?, NOW())', [name, OWNER]);
  // 仅当锁已过期（或无主）时才能抢到：原子 UPDATE，affectedRows=1 即成功
  const [r] = await pool.query(
    `UPDATE t_scheduler_lock SET owner = ?, locked_until = DATE_ADD(NOW(), INTERVAL ? SECOND)
     WHERE name = ? AND (locked_until IS NULL OR locked_until < NOW())`,
    [OWNER, ttlSec, name]
  );
  return r.affectedRows === 1;
}

/** 主动释放（仅释放自己持有的锁）。 */
async function release(name) {
  try {
    const pool = tenancy.getDefaultPool();
    await pool.query('UPDATE t_scheduler_lock SET locked_until = NOW() WHERE name = ? AND owner = ?', [name, OWNER]);
  } catch (_) { /* 释放失败靠 TTL 兜底 */ }
}

/**
 * 加锁执行：抢到锁才运行 fn，否则跳过（返回 false）。
 * fn 执行完不立即释放——靠 TTL 自然过期，避免「跑完立刻被其他实例重复抢跑」。
 */
async function withLock(name, ttlSec, fn) {
  let got = false;
  try { got = await tryAcquire(name, ttlSec); } catch (e) {
    // 锁机制异常时，为不丢任务，单实例场景下放行；多实例可能偶发重复（可接受）
    console.warn('分布式锁获取异常，降级执行：', e.message);
    got = true;
  }
  if (!got) return false;
  await fn();
  return true;
}

module.exports = { tryAcquire, release, withLock, OWNER };
