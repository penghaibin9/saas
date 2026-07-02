require('dotenv').config();
const tenancy = require('./tenancy');

/**
 * 数据库句柄（多租户感知代理）
 * ───────────────────────────────────────────────────────────
 * 历史上这里直接导出一个 mysql2 连接池，全项目 87 处以 `const pool = require('../config/db')`
 * 方式使用 pool.query / pool.getConnection。为支持 DB-per-tenant 又不改动这些调用，
 * 这里改为导出一个代理：每次属性访问都解析"当前请求所属租户"的连接池并转发。
 *   · single 模式：永远是默认库 → 行为与改造前完全一致
 *   · multi  模式：按 AsyncLocalStorage 中的租户落到各自独立库（事务也在同一租户库）
 */
function bindPool(pool, prop) {
  const value = pool[prop];
  return typeof value === 'function' ? value.bind(pool) : value;
}

// 只读副本代理（V2 读写分离）：读多写少的大屏/统计可 `require('../config/db').read.query(...)`，
// 路由到只读副本分担主库；未配置 DB_READ_HOST 时与主库完全一致，行为无差。
const readProxy = new Proxy(function () {}, {
  get(_t, prop) { return bindPool(tenancy.getReadPoolForCurrentRequest(), prop); },
});

const dbProxy = new Proxy(function () {}, {
  get(_target, prop) {
    if (prop === 'testConnection') return tenancy.testConnection;
    if (prop === 'read') return readProxy; // 只读副本句柄
    return bindPool(tenancy.getPoolForCurrentRequest(), prop);
  },
});

module.exports = dbProxy;
