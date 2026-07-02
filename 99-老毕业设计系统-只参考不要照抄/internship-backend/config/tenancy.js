require('dotenv').config();
const mysql = require('mysql2/promise');
const { AsyncLocalStorage } = require('async_hooks');

/**
 * 多租户内核（DB-per-tenant）
 * ───────────────────────────────────────────────────────────
 * 设计目标：同一套代码两用
 *   · TENANCY_MODE=single（默认/私有化部署）：永远使用默认库，行为与改造前完全一致
 *   · TENANCY_MODE=multi（SaaS）：每个请求按"学校(租户)"解析到各自独立的数据库
 *
 * 请求级隔离用 AsyncLocalStorage 承载当前租户，配合 config/db.js 的代理，
 * 40 个 model 无需任何改动即自动落到正确的租户库；事务(getConnection)亦然。
 */

const als = new AsyncLocalStorage();

const MODE = (process.env.TENANCY_MODE || 'single').toLowerCase() === 'multi' ? 'multi' : 'single';
const DEFAULT_DB = process.env.DB_NAME || 'internship_management';
// 租户注册表所在库（控制面）。默认与业务库同库，私有化无需额外建库；
// SaaS 建议单独建一个 master 库（MASTER_DB_NAME）集中管理租户。
const MASTER_DB = process.env.MASTER_DB_NAME || DEFAULT_DB;
// 默认租户标识（私有化单租户 / 多租户兜底）
const DEFAULT_TENANT_CODE = process.env.DEFAULT_TENANT_CODE || 'default';

const baseCfg = {
  host: process.env.DB_HOST || 'localhost',
  user: process.env.DB_USER || 'root',
  password: process.env.DB_PASSWORD || '',
  charset: 'utf8mb4',
  waitForConnections: true,
  // 单库连接数可配；30+ 校时建议下调（如 5），避免连接总数压垮 MySQL
  connectionLimit: Number(process.env.DB_POOL_LIMIT || 10),
  queueLimit: 0,
};

// ── 连接池治理（防 30+ 校连接池线性膨胀）──
// 策略：空闲回收。租户库连接池在空闲超过 POOL_IDLE_MS 后被关闭释放，
// 只回收"长时间未用"的池（不会杀掉正持有活跃事务的池，避免事务中断）。
const POOL_IDLE_MS = Number(process.env.POOL_IDLE_MS || 5 * 60 * 1000); // 默认 5 分钟
const POOL_SWEEP_MS = Number(process.env.POOL_SWEEP_MS || 60 * 1000);   // 每分钟扫一次

// ── 读写分离 / 租户分片（V2 · 规模化）──
// · DB_READ_HOST 配置后，只读查询可路由到只读副本，分担主库压力（未配置即回主库，零行为变化）。
// · 分片：每租户可带 db_host（落到不同 MySQL 实例），poolFor 接受 host 形成独立池；
//   db_name 全局唯一，故仍按 db_name 作缓存键，空闲回收逻辑不变。
const DB_READ_HOST = process.env.DB_READ_HOST || '';

const pools = new Map();     // dbName -> 主库 mysql pool（按需懒创建并缓存）
const readPools = new Map(); // dbName -> 只读副本 pool（仅 DB_READ_HOST 配置时）
const lastUsed = new Map();  // dbName -> 最近使用时间戳

function poolFor(dbName, host) {
  lastUsed.set(dbName, Date.now());
  if (!pools.has(dbName)) {
    // host 预留：分片到不同实例时按租户 db_host 建池；缺省用主库 host
    pools.set(dbName, mysql.createPool({ ...baseCfg, host: host || baseCfg.host, database: dbName }));
  }
  return pools.get(dbName);
}

// 只读副本池：未配置 DB_READ_HOST 则回退主库（调用方无需感知是否启用读写分离）
function readPoolFor(dbName) {
  if (!DB_READ_HOST) return poolFor(dbName);
  lastUsed.set(dbName, Date.now());
  if (!readPools.has(dbName)) {
    readPools.set(dbName, mysql.createPool({ ...baseCfg, host: DB_READ_HOST, database: dbName }));
  }
  return readPools.get(dbName);
}

// 空闲池回收：master 与默认库常驻不回收；其余租户库空闲超时则关闭释放
function sweepIdlePools() {
  const now = Date.now();
  for (const [dbName, pool] of pools) {
    if (dbName === MASTER_DB || dbName === DEFAULT_DB) continue;
    if (now - (lastUsed.get(dbName) || 0) > POOL_IDLE_MS) {
      pools.delete(dbName); lastUsed.delete(dbName);
      pool.end().catch(() => {}); // 排空在途连接后关闭
    }
  }
}
const _sweepTimer = setInterval(sweepIdlePools, POOL_SWEEP_MS);
if (typeof _sweepTimer.unref === 'function') _sweepTimer.unref();

// 当前缓存的连接池统计（监控/排障用）
function poolStats() {
  return { cached: pools.size, dbs: [...pools.keys()], connectionLimit: baseCfg.connectionLimit, idleMs: POOL_IDLE_MS, readReplica: DB_READ_HOST ? true : false, readPools: readPools.size };
}

// 控制面连接（不受租户上下文影响），用于读写租户注册表
function masterPool() {
  return poolFor(MASTER_DB);
}

// ── 租户注册表内存缓存（code -> tenant 行）──
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
    // 注册表不存在时（如尚未跑迁移），多租户解析将回退为按需查询/默认租户
  }
  return tenantCache;
}

async function resolveTenant(code) {
  if (!code) return null;
  if (code === DEFAULT_TENANT_CODE) return defaultTenant;
  if (tenantCache.has(code)) return tenantCache.get(code);
  // 缓存未命中则即时查一次（容忍运行期新开通租户）
  try {
    const [rows] = await masterPool().query(
      'SELECT id, code, name, db_name, status FROM t_tenant WHERE code = ? AND is_deleted = 0 LIMIT 1',
      [code]
    );
    if (rows.length) { tenantCache.set(code, rows[0]); return rows[0]; }
  } catch (_) {}
  return null;
}

// ── 请求级上下文 ──
function runWithTenant(tenant, fn) {
  return als.run({ tenant }, fn);
}
function currentTenant() {
  const store = als.getStore();
  return store ? store.tenant : null;
}

// 活跃租户列表（启用 + 未删除 + 未到期）。用于跨租户任务/迁移编排。
async function allActiveTenants() {
  if (MODE === 'single') return [defaultTenant];
  try {
    const [rows] = await masterPool().query(
      `SELECT id, code, name, db_name, status FROM t_tenant
       WHERE is_deleted = 0 AND status = 1 AND (expire_date IS NULL OR expire_date >= CURDATE())`
    );
    return rows.length ? rows : [defaultTenant];
  } catch (_) {
    return [defaultTenant]; // 注册表不存在/异常时兜底默认库
  }
}

/**
 * 按租户迭代执行（跨租户全局任务的统一入口）。
 * single 模式：仅在默认库上下文执行一次；
 * multi 模式：对每个活跃租户切到其库上下文依次执行，单租户失败不影响其余。
 * @param {(tenant)=>Promise<any>} fn
 * @returns {Promise<Array<{tenant:string, ok:boolean, result?:any, error?:string}>>}
 */
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

// config/db.js 代理调用：解析"当前请求所属租户"的连接池
function getPoolForCurrentRequest() {
  if (MODE === 'single') return poolFor(DEFAULT_DB);
  const t = currentTenant();
  if (!t || !t.db_name) return poolFor(DEFAULT_DB); // 上下文缺失（脚本/启动期）兜底默认库
  return poolFor(t.db_name, t.db_host); // db_host 预留：租户分片到不同实例时生效
}

// 只读副本句柄（读多写少的大屏/统计可选用）。未配置 DB_READ_HOST 时与主库一致。
function getReadPoolForCurrentRequest() {
  if (MODE === 'single') return readPoolFor(DEFAULT_DB);
  const t = currentTenant();
  if (!t || !t.db_name) return readPoolFor(DEFAULT_DB);
  return readPoolFor(t.db_name);
}

function getDefaultPool() {
  return poolFor(DEFAULT_DB);
}

// 优雅退出：停止空闲扫描 + 排空并关闭所有已创建的租户/控制面连接池
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
  MODE,
  DEFAULT_DB,
  MASTER_DB,
  DEFAULT_TENANT_CODE,
  baseCfg,
  poolFor,
  readPoolFor,
  getReadPoolForCurrentRequest,
  DB_READ_HOST,
  masterPool,
  loadTenants,
  resolveTenant,
  defaultTenant: () => defaultTenant,
  runWithTenant,
  currentTenant,
  allActiveTenants,
  forEachTenant,
  getPoolForCurrentRequest,
  getDefaultPool,
  testConnection,
  closeAllPools,
  poolStats,
};
