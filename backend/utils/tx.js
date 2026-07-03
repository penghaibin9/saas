/**
 * 事务助手（多租户感知）— 移植自旧系统
 * ───────────────────────────────────────────────────────────
 * config/db 代理按当前请求租户解析连接池，getConnection 亦在同一租户库。
 *   await withTransaction(async (conn) => { ... });
 * 出错自动回滚并抛出，正常自动提交，连接保证释放。
 */
const pool = require('../config/db');

async function withTransaction(fn) {
  const conn = await pool.getConnection();
  try {
    await conn.beginTransaction();
    const result = await fn(conn);
    await conn.commit();
    return result;
  } catch (e) {
    try { await conn.rollback(); } catch (_) {}
    throw e;
  } finally {
    conn.release();
  }
}

module.exports = { withTransaction };
