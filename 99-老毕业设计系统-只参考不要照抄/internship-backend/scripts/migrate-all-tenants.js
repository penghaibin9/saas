/**
 * 全租户迁移编排（SaaS 升级必备）
 * ───────────────────────────────────────────────────────────
 * 解决"30 校升级 = 30 次迁移、易 schema 漂移"的问题：
 *   遍历 master 注册表的活跃租户，对每个独立库执行幂等迁移 runner（migrate.js），
 *   再逐库读 t_migration 版本，输出"各校 schema 版本一致性对账报告"。
 * single 模式下仅迁移默认库（等价 npm run migrate:up）。
 *
 * 用法：node scripts/migrate-all-tenants.js
 */
require('dotenv').config();
const { spawn } = require('child_process');
const path = require('path');
const tenancy = require('../config/tenancy');
const tenantModel = require('../models/tenantModel');

function runMigrate(dbName) {
  return new Promise((resolve) => {
    const c = spawn(process.execPath, [path.join(__dirname, 'migrate.js')], {
      env: { ...process.env, DB_NAME: dbName }, stdio: 'inherit',
    });
    c.on('close', (code) => resolve(code));
    c.on('error', () => resolve(1));
  });
}

async function head(dbName) {
  try {
    const [[r]] = await tenancy.poolFor(dbName).query('SELECT COUNT(*) AS c, MAX(name) AS last FROM t_migration');
    return { applied: Number(r.c), last: r.last };
  } catch (e) { return { applied: null, last: null, error: e.message }; }
}

(async () => {
  try {
    await tenantModel.ensureTable().catch(() => {});
    const tenants = await tenancy.allActiveTenants();
    console.log(`📦 全租户迁移：${tenancy.MODE} 模式，目标库 ${tenants.length} 个\n`);

    const report = [];
    for (const t of tenants) {
      console.log(`──▶ [${t.code}] ${t.db_name}`);
      const exit = await runMigrate(t.db_name);
      report.push({ tenant: t.code, db: t.db_name, exit, ...(await head(t.db_name)) });
    }

    console.log('\n=== 迁移版本对账报告 ===');
    for (const r of report) {
      console.log(`${r.exit === 0 ? '✅' : '❌'} ${String(r.tenant).padEnd(14)} 已应用 ${r.applied ?? '-'} 个迁移  最近: ${r.last || '-'}${r.error ? '  ERR:' + r.error : ''}`);
    }
    const appliedSet = new Set(report.filter((r) => r.applied != null).map((r) => r.applied));
    const allOk = report.every((r) => r.exit === 0);
    console.log(appliedSet.size <= 1 && allOk
      ? '\n✔ 各校 schema 版本一致，全部迁移成功'
      : `\n⚠ 存在不一致或失败（应用数种类 ${appliedSet.size}，失败 ${report.filter((r) => r.exit !== 0).length} 校），请排查上方 ❌ 项`);
    if (!allOk) process.exitCode = 1;
  } catch (e) {
    console.error('全租户迁移出错：', e.message);
    process.exitCode = 1;
  } finally {
    await tenancy.closeAllPools();
  }
})();
