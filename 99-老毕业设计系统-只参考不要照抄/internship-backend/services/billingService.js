/**
 * 计费对账 Service（V2 · 规模化运营）
 * ───────────────────────────────────────────────────────────
 * 解决「30+ 校用量靠人工核对、超配额无台账」：
 *   · 用量聚合：遍历各租户库统计学生数/AI 调用，写回控制面 t_tenant_usage（按月）。
 *   · 对账报告：用量 vs 套餐配额，标出超限项 + 利用率，并按套餐年费汇总 ARR/MRR。
 * 纯对账逻辑 reconcileUsage 抽为可单测函数（不依赖 DB）。
 */
const tenancy = require('../config/tenancy');
const tenantModel = require('../models/tenantModel');

function curMonth() { return new Date().toISOString().slice(0, 7); }

/**
 * 纯对账：用量 vs 配额 → 超限标记 + 利用率。无 IO，可单测。
 * @param {{max_students?:number,max_storage_mb?:number,ai_monthly_quota?:number}} quota
 * @param {{students?:number,storage_mb?:number,ai_calls?:number}} usage
 */
function reconcileUsage(quota = {}, usage = {}) {
  const u = { students: usage.students || 0, storage_mb: usage.storage_mb || 0, ai_calls: usage.ai_calls || 0 };
  const pct = (used, cap) => (cap > 0 ? Math.round((used / cap) * 1000) / 10 : 0); // 利用率%（一位小数）
  const dims = {
    students: { used: u.students, cap: quota.max_students || 0, pct: pct(u.students, quota.max_students || 0), over: !!quota.max_students && u.students > quota.max_students },
    storage:  { used: u.storage_mb, cap: quota.max_storage_mb || 0, pct: pct(u.storage_mb, quota.max_storage_mb || 0), over: !!quota.max_storage_mb && u.storage_mb > quota.max_storage_mb },
    ai:       { used: u.ai_calls, cap: quota.ai_monthly_quota || 0, pct: pct(u.ai_calls, quota.ai_monthly_quota || 0), over: !!quota.ai_monthly_quota && u.ai_calls > quota.ai_monthly_quota },
  };
  const overDims = Object.entries(dims).filter(([, d]) => d.over).map(([k]) => k);
  // 状态：超限 over / 临界 warn(任一维度≥90%) / 正常 ok
  let status = 'ok';
  if (overDims.length) status = 'over';
  else if (Object.values(dims).some((d) => d.cap > 0 && d.pct >= 90)) status = 'warn';
  return { status, overDims, dims };
}

const billingService = {
  reconcileUsage,

  // 聚合单校实时用量并写回计量表（直连其库统计）
  async refreshOne(t) {
    const pool = tenancy.poolFor(t.db_name);
    let students = 0, ai_calls = 0;
    try { const [[r]] = await pool.query('SELECT COUNT(*) c FROM t_user WHERE role=4 AND is_deleted=0'); students = Number(r.c) || 0; } catch (_) {}
    try { const [[r]] = await pool.query('SELECT calls FROM t_ai_usage WHERE period=? LIMIT 1', [curMonth()]); ai_calls = r ? Number(r.calls) : 0; } catch (_) {}
    await tenantModel.upsertUsage(t.code, curMonth(), { students, ai_calls, storage_mb: 0 });
    return { code: t.code, students, ai_calls };
  },

  // 全租户用量聚合（计费对账前置）。单校失败不影响其余。
  async refreshAll() {
    const tenants = await tenantModel.list();
    const period = curMonth();
    const results = [];
    for (const t of tenants) {
      try { results.push({ ...(await billingService.refreshOne(t)), ok: true }); }
      catch (e) { results.push({ code: t.code, ok: false, error: e.message }); }
    }
    return { period, count: results.length, results };
  },

  // 计费对账报告：用量 vs 配额 + 套餐年费汇总（ARR/MRR、超限校清单）
  async report(period) {
    const p = period || curMonth();
    const tenants = await tenantModel.list();
    const plans = await tenantModel.listPlans();
    const planMap = Object.fromEntries(plans.map((x) => [x.code, x]));
    const rows = [];
    let arr = 0, overCount = 0;
    for (const t of tenants) {
      const usage = (await tenantModel.getUsage(t.code, p).catch(() => null)) || {};
      const rec = reconcileUsage(t, usage);
      const plan = planMap[t.plan] || {};
      const price = Number(plan.price_year || 0);
      if (t.status === 1) arr += price;            // 仅在用学校计入年经常性收入
      if (rec.status === 'over') overCount += 1;
      rows.push({
        code: t.code, name: t.name, plan: t.plan, price_year: price,
        status: t.status, expire_date: t.expire_date,
        expired: t.expire_date ? new Date(t.expire_date) < new Date() : false,
        reconcile: rec,
      });
    }
    return {
      period: p,
      summary: { tenants: tenants.length, active: tenants.filter((t) => t.status === 1).length, over_quota: overCount, arr, mrr: Math.round((arr / 12) * 100) / 100 },
      rows,
    };
  },
};

module.exports = billingService;
