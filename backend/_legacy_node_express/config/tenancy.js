require('dotenv').config();
const mysql = require('mysql2/promise');
const { AsyncLocalStorage } = require('async_hooks');

/**
 * 多租户内核（DB-per-tenant）— 移植自旧系统，行为不变
 * ───────────────────────────────────────────────────────────
 * 同一套代码两用：
 *   · TENANCY_MODE=single（默认/私有化部署）：永远使用默认库
 *   · TENANCY_MODE=multi（SaaS）：每个请求按"学校(租户)"解析到各自独立数据库
 * 请求级隔离用 AsyncLocalStorage 承载当前租户，配合 config/db.js 的代理，
 * 所有 model 无需改动即自动落到正确的租户库；事务(getConnection)亦然。
 */

const als = new AsyncLocalStorage();

const MODE = (process.env.TENANCY_MODE || 'single').toLowerCase() === 'multi' ? 'multi' : 'single';
const DEFAULT_DB = process.env.DB_NAME || 'school_lifecycle';
const MASTER_DB = process.env.MASTER_DB_NAME || DEFAULT_DB;
const DEFAULT_TENANT_CODE = process.env.DEFAULT_TENANT_CODE || 'default';

const baseCfg = {
  host: process.env.DB_HOST || 'localhost',
  user: process.env.DB_USER || 'root',
  password: process.env.DB_PASSWORD || '',
  charset: 'utf8mb4',
  waitForConnections: true,
  connectionLimit: Number(process.env.DB_POOL_LIMIT || 10),
  queueLimit: 0,
};

// 连接池治理：空闲回收（防 30+ 校连接池线性膨胀）
const POOL_IDLE_MS = Number(process.env.POOL_IDLE_MS || 5 * 60 * 1000);
const POOL_SWEEP_MS = Number(process.env.POOL_SWEEP_MS || 60 * 1000);
const DB_READ_HOST = process.env.DB_READ_HOST || '';

const pools = new Map();
const readPools = new Map();
const lastUsed = new Map();

function poolFor(dbName, host) {
  lastUsed.set(dbName, Date.now());
  if (!pools.has(dbName)) {
    pools.set(dbName, mysql.createPool({ ...baseCfg, host: host || baseCfg.host, database: dbName }));
  }
  return pools.get(dbName);
}

function readPoolFor(dbName) {
  if (!DB_READ_HOST) return poolFor(dbName);
  lastUsed.set(dbName, Date.now());
  if (!readPools.has(dbName)) {
    readPools.set(dbName, mysql.createPool({ ...baseCfg, host: DB_READ_HOST, database: dbName }));
  }
  return readPools.get(dbName);
}

function sweepIdlePools() {
  const now = Date.now();
  for (const [dbName, pool] of pools) {
    if (dbName === MASTER_DB || dbName === DEFAULT_DB) continue;
    if (now - (lastUsed.get(dbName) || 0) > POOL_IDLE_MS) {
      pools.delete(dbName); lastUsed.delete(dbName);
      pool.end().catch(() => {});
    }
  }
}
const _sweepTimer = setInterval(sweepIdlePools, POOL_SWEEP_MS);
if (typeof _sweepTimer.unref === 'function') _sweepTimer.unref();

function poolStats() {
  return { cached: pools.size, dbs: [...pools.keys()], connectionLimit: baseCfg.connectionLimit, idleMs: POOL_IDLE_MS, readReplica: DB_READ_HOST ? true : false, readPools: readPools.size };
}

function masterPool() {
  return poolFor(MASTER_DB);
}

const tenantCache = new Map();
const defaultTenant = { id: 0, code: DEFAULT_TENANT_CODE, name: '默认租户', db_name: DEFAULT_DB, status: 1 };

async function loadTenants() {
  tenantCache.clear();
  try {
    const [rows] = await masterPool().query(
      'SELECT id, code, name, db_name, status FROM t_tenant WHERE is_deleted = 0'
    );
    for (const r of rows) tenantCache.set(r.code, r);
  } catch (e) {
    // 注册表不存在时（尚未迁移）回退默认租户
  }
  return tenantCache;
}

async function resolveTenant(code) {
  if (!code) return null;
  if (code === DEFAULT_TENANT_CODE) return defaultTenant;
  if (tenantCache.has(code)) return tenantCache.get(code);
  try {
    const [rows] = await masterPool().query(
      'SELECT id, code, name, db_name, status FROM t_tenant WHERE code = ? AND is_deleted = 0 LIMIT 1',
      [code]
    );
    if (rows.length) { tenantCache.set(code, rows[0]); return rows[0]; }
  } catch (_) {}
  return null;
}

function runWithTenant(tenant, fn) {
  return als.run({ tenant }, fn);
}
function currentTenant() {
  const store = als.getStore();
  return store ? store.tenant : null;
}

async function allActiveTenants() {
  if (MODE === 'single') return [defaultTenant];
  try {
    const [rows] = await masterPool().query(
      `SELECT id, code, name, db_name, status FROM t_tenant
       WHERE is_deleted = 0 AND status = 1 AND (expire_date IS NULL OR expire_date >= CURDATE())`
    );
    return rows.length ? rows : [defaultTenant];
  } catch (_) {
    return [defaultTenant];
  }
}

async function forEachTenant(fn) {
  const list = await allActiveTenants();
  const out = [];
  for (const t of list) {
    try {
      const result = await runWithTenant(t, () => fn(t));
      out.push({ tenant: t.code, ok: true, result });
    } catch (e) {
      out.push({ tenant: t.code, ok: false, error: e.message });
    }
  }
  return out;
}

function getPoolForCurrentRequest() {
  if (MODE === 'single') return poolFor(DEFAULT_DB);
  const t = currentTenant();
  if (!t || !t.db_name) return poolFor(DEFAULT_DB);
  return poolFor(t.db_name, t.db_host);
}

function getReadPoolForCurrentRequest() {
  if (MODE === 'single') return readPoolFor(DEFAULT_DB);
  const t = currentTenant();
  if (!t || !t.db_name) return readPoolFor(DEFAULT_DB);
  return readPoolFor(t.db_name);
}

function getDefaultPool() {
  return poolFor(DEFAULT_DB);
}

async function closeAllPools() {
  clearInterval(_sweepTimer);
  const all = [...pools.values(), ...readPools.values()];
  pools.clear(); readPools.clear(); lastUsed.clear();
  await Promise.allSettled(all.map((p) => p.end()));
}

async function testConnection() {
  try {
    const conn = await getDefaultPool().getConnection();
    console.log('✅ 数据库连接成功！');
    conn.release();
    return true;
  } catch (err) {
    console.error('❌ 数据库连接失败：', err.message);
    console.error('   请检查 .env 中的 MySQL 配置，并确认默认数据库已创建');
    return false;
  }
}

module.exports = {
  MODE, DEFAULT_DB, MASTER_DB, DEFAULT_TENANT_CODE, baseCfg,
  poolFor, readPoolFor, getReadPoolForCurrentRequest, DB_READ_HOST,
  masterPool, loadTenants, resolveTenant,
  defaultTenant: () => defaultTenant,
  runWithTenant, currentTenant, allActiveTenants, forEachTenant,
  getPoolForCurrentRequest, getDefaultPool, testConnection, closeAllPools, poolStats,
};
