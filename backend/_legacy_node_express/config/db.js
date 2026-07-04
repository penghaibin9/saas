require('dotenv').config();
const tenancy = require('./tenancy');

/**
 * 数据库句柄（多租户感知代理）— 移植自旧系统
 * ───────────────────────────────────────────────────────────
 * 导出一个代理：每次属性访问都解析"当前请求所属租户"的连接池并转发。
 * 全项目 model 以 `const pool = require('../config/db')` 使用 pool.query / pool.getConnection。
 *   · single 模式：永远默认库
 *   · multi  模式：按 AsyncLocalStorage 中的租户落到各自独立库（事务同租户库）
 */
function bindPool(pool, prop) {
  const value = pool[prop];
  return typeof value === 'function' ? value.bind(pool) : value;
}

const readProxy = new Proxy(function () {}, {
  get(_t, prop) { return bindPool(tenancy.getReadPoolForCurrentRequest(), prop); },
});

const dbProxy = new Proxy(function () {}, {
  get(_target, prop) {
    if (prop === 'testConnection') return tenancy.testConnection;
    if (prop === 'read') return readProxy;
    return bindPool(tenancy.getPoolForCurrentRequest(), prop);
  },
});

module.exports = dbProxy;
