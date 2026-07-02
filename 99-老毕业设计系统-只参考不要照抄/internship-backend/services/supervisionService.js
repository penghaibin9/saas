/**
 * 监管局版·跨校驾驶舱 Service（V2 · 教育局/督导口径）
 * ───────────────────────────────────────────────────────────
 * 单校大屏是「校长视角」；本服务是「监管局视角」——跨所有在用学校聚合：
 *   · 各校实习规模（在册实习生/活跃岗位）
 *   · 各校多维风险（复用 bigscreenModel.riskRadar，逐校切库统计）
 *   · 全局风险总账 + 风险最高学校榜（督导排序、约谈依据）
 * 经 tenancy.forEachTenant 逐校切上下文聚合，单校失败不影响整体（标 ok=false）。
 * 仅平台/监管管理员可调（挂 requirePlatformAdmin）。
 */
const tenancy = require('../config/tenancy');
const bigscreenModel = require('../models/bigscreenModel');
const pool = require('../config/db');

// 监管聚合是典型读多写少：走只读副本（未配置 DB_READ_HOST 时自动回主库）
async function safeCount(sql, params = []) {
  try { const [[r]] = await pool.read.query(sql, params); return Number(r.c) || 0; } catch (_) { return 0; }
}

// 单校画像（运行在该校库上下文内）
async function schoolProfile() {
  const interns = await safeCount('SELECT COUNT(*) c FROM t_user WHERE role=4 AND is_deleted=0');
  const active = await safeCount('SELECT COUNT(DISTINCT student_id) c FROM t_assignment WHERE is_deleted=0 AND status=1');
  const radar = await bigscreenModel.riskRadar();
  const riskTotal = radar.reduce((s, d) => s + (d.value || 0), 0);
  return { interns, active_interns: active, risk_total: riskTotal, radar };
}

const supervisionService = {
  schoolProfile,

  // 跨校聚合驾驶舱
  async dashboard() {
    const per = await tenancy.forEachTenant(async (t) => ({ name: t.name, ...(await schoolProfile()) }));
    const schools = per.map((r) => ({
      code: r.tenant, ok: r.ok,
      ...(r.ok ? r.result : { error: r.error, interns: 0, active_interns: 0, risk_total: 0, radar: [] }),
    }));

    // 全局总账：学校数/实习生总数 + 各风险维度跨校求和
    const radarTotals = {};
    let interns = 0, active = 0, riskTotal = 0;
    for (const s of schools) {
      interns += s.interns || 0; active += s.active_interns || 0; riskTotal += s.risk_total || 0;
      for (const d of s.radar || []) {
        if (!radarTotals[d.key]) radarTotals[d.key] = { key: d.key, label: d.label, value: 0 };
        radarTotals[d.key].value += d.value || 0;
      }
    }
    // 风险最高学校榜（督导约谈优先级）
    const ranking = [...schools].filter((s) => s.ok)
      .sort((a, b) => (b.risk_total || 0) - (a.risk_total || 0))
      .slice(0, 10)
      .map((s) => ({ code: s.code, name: s.name, interns: s.interns, risk_total: s.risk_total }));

    return {
      generated_at: new Date().toISOString(),
      totals: { schools: schools.length, ok: schools.filter((s) => s.ok).length, interns, active_interns: active, risk_total: riskTotal },
      radar: Object.values(radarTotals),
      ranking,
      schools,
    };
  },
};

module.exports = supervisionService;
