/**
 * 幂等迁移 Runner（带版本表）
 * ───────────────────────────────────────────────────────────
 * 解决原 `migrate:all` 用 && 串 20 个脚本、无版本记录、每次全量重跑的问题：
 *   · 在 t_migration 表记录每个迁移的执行情况；已执行的自动跳过；
 *   · 顺序执行未应用的迁移；任一失败立即中止（不记录该条），便于定位与续跑；
 *   · 子进程隔离运行各迁移脚本（沿用现有脚本，零改动），退出码决定成败。
 *
 * 用法：
 *   node scripts/migrate.js          # 应用所有未执行的迁移（幂等，可反复运行）
 *   node scripts/migrate.js status   # 仅查看每个迁移的应用状态
 *
 * 注：仅作用于默认库（私有化单库 / SaaS 控制面默认库）。SaaS 各租户库的初始化由
 *     scripts/provision-tenant.js 负责。
 */
require('dotenv').config();
const path = require('path');
const { spawn } = require('child_process');
const tenancy = require('../config/tenancy');

// 迁移顺序（与原 migrate:all 完全一致；新增迁移往末尾追加即可）
const MIGRATIONS = [
  'migrate-base-tables.js',
  'migrate-reconcile-base.js',
  'migrate-add-must-change-password.js',
  'migrate-intern-core.js',
  'migrate-intern-logs.js',
  'migrate-gd-core.js',
  'migrate-gd-thesis.js',
  'migrate-gd-quality.js',
  'migrate-province.js',
  'migrate-insurance.js',
  'migrate-gd-guidance.js',
  'migrate-teacher-record.js',
  'migrate-satisfaction.js',
  'migrate-audit.js',
  'migrate-enterprise-portal.js',
  'migrate-complaint-safety.js',
  'migrate-commercial-wave2.js',
  'migrate-sales-phase1.js',
  'migrate-commercial-benchmark.js',
  'migrate-ent-pos-commercial.js',
  'migrate-commercial-wave-ai.js',
];

const pool = tenancy.getDefaultPool();

async function ensureTable() {
  await pool.query(`CREATE TABLE IF NOT EXISTS t_migration (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(150) NOT NULL UNIQUE,
    applied_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    duration_ms INT DEFAULT 0
  ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT '迁移版本记录'`);
}

async function appliedSet() {
  const [rows] = await pool.query('SELECT name FROM t_migration');
  return new Set(rows.map((r) => r.name));
}

function runScript(file) {
  return new Promise((resolve) => {
    const start = Date.now();
    const child = spawn(process.execPath, [path.join(__dirname, file)], {
      stdio: 'inherit',
      env: process.env,
    });
    child.on('close', (code) => resolve({ code, durationMs: Date.now() - start }));
    child.on('error', () => resolve({ code: 1, durationMs: Date.now() - start }));
  });
}

async function status() {
  await ensureTable();
  const applied = await appliedSet();
  console.log('迁移状态：');
  for (const m of MIGRATIONS) {
    console.log(`  ${applied.has(m) ? '✅ 已应用' : '⬜ 待应用'}  ${m}`);
  }
}

async function up() {
  await ensureTable();
  const applied = await appliedSet();
  const pending = MIGRATIONS.filter((m) => !applied.has(m));

  if (!pending.length) {
    console.log('✅ 无待执行迁移，数据库已是最新');
    return;
  }
  console.log(`📦 待执行迁移 ${pending.length} 个：`);

  for (const file of pending) {
    console.log(`\n──▶ 执行 ${file}`);
    const { code, durationMs } = await runScript(file);
    if (code !== 0) {
      console.error(`❌ 迁移失败：${file}（退出码 ${code}），已停止。修复后重跑本命令将从此处续跑。`);
      process.exitCode = 1;
      return;
    }
    await pool.query('INSERT INTO t_migration (name, duration_ms) VALUES (?, ?)', [file, durationMs]);
    console.log(`✅ 完成 ${file}（${durationMs}ms）`);
  }
  console.log('\n🎉 全部迁移执行完成');
}

(async () => {
  try {
    if (process.argv[2] === 'status') await status();
    else await up();
  } catch (e) {
    console.error('迁移 Runner 出错：', e.message);
    process.exitCode = 1;
  } finally {
    await tenancy.closeAllPools();
  }
})();
